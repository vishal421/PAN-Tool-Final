# Firewall Config Converter

**V13** — fixes 1:1 "static" NAT for Cisco ASA and Check Point so it's
actually bidirectional: both parsers previously emitted only a one-way
source translation for static NAT, meaning inbound traffic to the
published/translated address was never translated back to the real host.
Both now generate the destination-translation half (matching how
FortiGate/Juniper static NAT already worked), with a note about adding
the reverse (outbound) leg. See "What's new in V13"
below.

A local, deterministic converter that turns multi-vendor firewall configuration
exports into Palo Alto Networks CLI (`set` format). No cloud services, no AI
in the core conversion path — parsing and generation are rule-based and
auditable.

```
Vendor Config File → Parse → Interface Mapping (user-confirmed) → Generate PAN-OS CLI → Download
```

FortiGate and Cisco ASA are **interface-based**; Palo Alto is **zone-based**.
Rather than guess a zone mapping, this tool parses the config, shows you
every detected interface, and asks you to confirm the PAN-OS interface
name, zone, virtual router, and type for each one before anything is
generated. That confirmed mapping is then applied consistently across
interfaces, zones, virtual routers, security policies, NAT rules, and
static routes — no generated output ever references a raw source
interface name once mapping is confirmed.

## Build Status (phased delivery)

| Phase | Scope | Status |
|---|---|---|
| 1 | Project structure, backend, frontend, upload flow | ✅ Done |
| 2 | FortiGate parser | ✅ Done |
| 3 | Check Point parser | ✅ Done |
| 4 | Cisco ASA parser | ✅ Done |
| 5 | Sophos XG parser | ✅ Done |
| 6 | Full Palo Alto CLI generator (rules, NAT, routes, zones, VRs) | ✅ Done for all 4 vendors |
| 7 | Validation engine | ✅ Done (interface mapping validation) |
| 8 | Reports & UI polish | 🟡 Interface Mapping Wizard done; broader reporting still planned |

All four originally-scoped vendors (FortiGate, Check Point, Cisco ASA, Sophos
XG) are implemented and tested end-to-end.

**Interface Mapping Wizard** (`POST /api/parse` → `GET /api/jobs/{id}/summary` →
`POST /api/jobs/{id}/mapping`): parses the config, shows a full **Configuration
Summary** (object counts plus the actual addresses/groups/services/policies/
NAT rules in table form, exportable to Excel via `GET /api/jobs/{id}/export/excel`),
then requires an explicit user-confirmed interface mapping (PAN interface
name, zone, virtual router, interface type, IP, description, enabled)
before generation. Validation blocks generation on unmapped interfaces,
duplicate PAN interface assignments, invalid IPs, and similar errors;
dangling references from policies/NAT/routes are surfaced as warnings.
A lower-fidelity one-shot `POST /api/convert` endpoint still exists for
quick testing — it auto-assigns a default mapping instead of asking, and
says so in its response message.

FortiGate, Cisco ASA, Check Point, and Sophos XG configs all convert
end-to-end: addresses, address groups, services, service groups,
interfaces, zones, virtual routers, static routes, basic interface-based
NAT, and security policies generate real PAN-OS CLI using the confirmed
mapping. Anything the source config expresses that PAN-OS has no clean
equivalent for (IP pool-based NAT, port-forwarding VIPs, twice-NAT
destination translation edge cases, inline ACL ports with no named
service object, Check Point hide-NAT-behind-gateway with no resolvable
egress interface, wildcard FQDN/dns-domain objects, etc.) is flagged as a
`# TODO (UNSUPPORTED):` comment rather than guessed.

Sophos XG is the one vendor here parsed from XML rather than a line-based
CLI export - its real migration-relevant format is the system backup
(Backup & Firmware > Backup), so `app/parsers/sophos/parser.py` uses
`xml.etree.ElementTree` instead of a text tokenizer. Sophos also natively
assigns a Zone per interface (like Check Point's Security Zone objects,
unlike FortiGate/Cisco's implicit interface-based model) and lets SNAT
rules name a specific outbound interface - which the interface mapping
step resolves cleanly, unlike Check Point's hide-behind-gateway which has
no interface reference to resolve at all.

Check Point is architecturally different from FortiGate/Cisco in one
important way worth knowing: its Standard policy layer matches access
rules against address objects, not interfaces or zones, so a Check Point
rule doesn't inherently need a "from zone / to zone" the way a FortiGate
policy or Cisco ACL does. The parser reflects that honestly - Check Point
security rules generate with `from any to any` (correct, not a guess),
while the interface mapping step still applies fully to interfaces,
zones, virtual routers, and any NAT rule that references a specific
gateway interface.

**Explicitly out of scope for now:** VPN migration and HA support are not
implemented — both are substantial, separate parsing efforts (IPsec
phase1/phase2 negotiation parameters, HA pairing/failover config) that
don't have a partial-and-honest middle ground worth shipping yet. Cisco
Firepower has no parser (only Cisco ASA is supported under the "cisco"
vendor key).

## Architecture

- **`backend/app/parsers/`** — one subpackage per vendor, each implementing
  `BaseParser` (see `parsers/base.py`). Adding a vendor never touches the
  API, generator, or frontend.
- **`backend/app/normalizer/models.py`** — the vendor-neutral data model
  (`AddressObject`, `ServiceObject`, `Policy`, etc.) that is the only
  contract between parsers and the generator.
- **`backend/app/generators/paloalto/`** — the only code that knows PAN-OS
  CLI syntax. Consumes the normalized model exclusively.
- **`backend/app/api/`** — FastAPI routes: upload/convert, job status,
  artifact downloads.
- **`backend/app/models/database.py`** — SQLite job tracking via SQLAlchemy.
- **`frontend/`** — React + Vite, dark mode, single-page upload → results flow.

See `docs/ARCHITECTURE.md` for the full data-flow diagram and design notes.

## Quickstart (Docker)

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API docs (Swagger): http://localhost:8000/api/docs

## Quickstart (local, no Docker)

**Backend**
```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

Frontend dev server proxies `/api/*` to `http://localhost:8000` (see
`vite.config.js`).

## Running tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

## Project layout

```
converter/
  backend/
    app/
      parsers/          # one package per vendor + BaseParser + registry
      normalizer/        # vendor-neutral data model
      generators/paloalto/  # PAN-OS CLI generator
      models/            # SQLAlchemy models + Pydantic schemas
      api/                # FastAPI routes
      core/               # config, logging
    tests/
  frontend/
    src/
  docs/
  tests/
    samples/              # sample vendor configs for testing
  docker-compose.yml
```

## Design principles this project holds itself to

1. **No invented CLI syntax.** Every generated PAN-OS command maps to a
   documented `set` command. If there's no clean mapping, the generator
   emits a `# TODO (UNSUPPORTED):` comment and records a `ConversionIssue`
   — never a guess.
2. **Vendor logic never leaks past the normalizer.** The generator has zero
   `if vendor == "fortigate"` branches. If you ever need one, the
   abstraction has failed and should be fixed in the parser instead.
3. **Nothing is silently dropped.** Every unsupported field becomes a
   visible warning/error/unsupported issue, surfaced in the CLI output,
   the JSON export, and the UI.
