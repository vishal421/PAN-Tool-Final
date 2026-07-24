# Architecture

## Data flow

```
┌─────────────┐     ┌───────────────┐     ┌────────────────────┐     ┌──────────────────┐
│ Vendor file │ ──▶ │ Vendor Parser │ ──▶ │ NormalizedConfig    │ ──▶ │ PaloAltoGenerator │
│ (.conf/.xml)│     │ (BaseParser   │     │ (vendor-neutral     │     │ (only module that │
│             │     │  subclass)    │     │  dataclasses)       │     │  knows PAN-OS CLI)│
└─────────────┘     └───────────────┘     └────────────────────┘     └──────────────────┘
                                                     │
                                                     ▼
                                          ConversionIssue list
                                     (warning / error / unsupported)
                                                     │
                                                     ▼
                                  Surfaced in: CLI comments, JSON export,
                                  CSV summary, and the UI results panel.
```

## Why the normalizer boundary matters

The single biggest risk in a multi-vendor converter is vendor-specific
logic leaking into the generator ("if fortigate do X, if checkpoint do Y").
That produces an unmaintainable generator and makes adding vendor #5
require touching code that has nothing to do with vendor #5.

Instead:

- **Parsers** (`app/parsers/<vendor>/`) are the only code that understands
  vendor syntax. Their job is to produce `AddressObject`, `ServiceObject`,
  `Policy`, etc. — nothing vendor-specific escapes this layer.
- **The generator** (`app/generators/paloalto/generator.py`) is the only
  code that understands PAN-OS `set` command syntax. It never imports
  anything from `app/parsers/`.
- Adding a vendor = new parser subpackage + one line in
  `app/parsers/registry.py`. No other file changes.

## BaseParser contract

Every vendor parser subclasses `BaseParser` (`app/parsers/base.py`) and
implements:

```python
parse_addresses() -> (list[AddressObject], list[AddressGroup])
parse_services()  -> (list[ServiceObject], list[ServiceGroup])
parse_interfaces()-> (list[Interface], list[Zone])
parse_routes()    -> list[Route]
parse_policies()  -> (list[Policy], list[NATRule])
```

`BaseParser.parse()` orchestrates these five stages, catches per-stage
exceptions (one bad policy block doesn't kill the whole conversion), and
returns a single `NormalizedConfig`. Stage-level logging happens
automatically; parsers additionally call `self.warn()`, `self.error()`,
`self.unsupported()` for anything that couldn't be cleanly mapped.

## Never-guess policy

`generator.py` only emits a `set` command when there's a documented PAN-OS
CLI equivalent for the source construct. Anything without one (e.g. a
vendor's IP-wildcard address object, which PAN-OS has no native concept
of) becomes:

1. A `ConversionIssue(severity="unsupported", ...)` on the normalized config
2. A `# TODO (UNSUPPORTED): ...` comment at the point of use in the CLI output
3. A line item in the "Unsupported / Manual Review" summary at the end of
   the generated file
4. A count in the job's `unsupported` stat, shown in the UI

This is a hard rule for every phase of this project, including the
security-rule and NAT generation landing in Phase 6.

## Job lifecycle (backend)

`POST /api/convert` is currently synchronous: upload → parse → normalize →
generate → persist, all in one request/response cycle. The `ConversionJob`
SQLite row already has the `status` field (`pending|parsing|completed|failed`)
needed to move this to a background task queue later without changing the
API contract — the frontend already polls `GET /api/jobs/{id}` rather than
assuming the POST response is final state.

## Frontend

Single page, dark theme, three phases in one view:
1. Vendor select (tiles, disabled/labeled "Coming soon" for unregistered vendors)
2. Drag-and-drop upload + Convert button
3. Results: object-count tiles, issue badges (warnings/errors/unsupported),
   three download buttons (CLI / CSV / JSON) hitting
   `GET /api/jobs/{id}/download/{cli|csv|json}`.

No client-side parsing happens — the frontend is a thin client over the
FastAPI backend, which keeps the "deterministic parser, not an AI chat app"
guarantee easy to audit.
