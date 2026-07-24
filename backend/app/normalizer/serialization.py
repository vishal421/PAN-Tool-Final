"""
NormalizedConfig <-> dict serialization.

The two-phase flow (parse now, confirm interface mapping later, generate
after that) needs the parsed config to survive between HTTP requests.
dataclasses.asdict() already gets us most of the way there for output;
this module adds the reverse direction plus enum-safe encode/decode, so
the interim state can round-trip through the job's JSON column.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from app.normalizer.models import (
    NormalizedConfig, AddressObject, AddressGroup, ServiceObject, ServiceGroup,
    Interface, Zone, Route, NATRule, Policy, ConversionIssue,
    AddressType, ServiceProtocol, PolicyAction, ObjectOrigin,
    LdapServerProfile, RadiusServerProfile, TacacsServerProfile,
    SnmpProfile, SnmpUser, SyslogServerProfile, NtpProfile, DnsProfile,
)


def config_to_dict(config: NormalizedConfig) -> dict:
    return {
        "addresses": [dataclasses.asdict(a) for a in config.addresses],
        "address_groups": [dataclasses.asdict(a) for a in config.address_groups],
        "services": [dataclasses.asdict(s) for s in config.services],
        "service_groups": [dataclasses.asdict(s) for s in config.service_groups],
        "interfaces": [dataclasses.asdict(i) for i in config.interfaces],
        "zones": [dataclasses.asdict(z) for z in config.zones],
        "routes": [dataclasses.asdict(r) for r in config.routes],
        "nat_rules": [dataclasses.asdict(n) for n in config.nat_rules],
        "policies": [dataclasses.asdict(p) for p in config.policies],
        "issues": [dataclasses.asdict(i) for i in config.issues],
        "log_forwarding_profiles": list(config.log_forwarding_profiles),
        "security_profile_groups": list(config.security_profile_groups),
        "ldap_profiles": [dataclasses.asdict(x) for x in config.ldap_profiles],
        "radius_profiles": [dataclasses.asdict(x) for x in config.radius_profiles],
        "tacacs_profiles": [dataclasses.asdict(x) for x in config.tacacs_profiles],
        "snmp_profiles": [dataclasses.asdict(x) for x in config.snmp_profiles],
        "syslog_profiles": [dataclasses.asdict(x) for x in config.syslog_profiles],
        "ntp_profiles": [dataclasses.asdict(x) for x in config.ntp_profiles],
        "dns_profiles": [dataclasses.asdict(x) for x in config.dns_profiles],
    }


def config_from_dict(data: dict) -> NormalizedConfig:
    config = NormalizedConfig()
    for a in data.get("addresses", []):
        a = dict(a); a["type"] = AddressType(a["type"])
        if a.get("origin"):
            a["origin"] = ObjectOrigin(a["origin"])
        config.addresses.append(AddressObject(**a))
    for g in data.get("address_groups", []):
        g = dict(g)
        if g.get("origin"):
            g["origin"] = ObjectOrigin(g["origin"])
        config.address_groups.append(AddressGroup(**g))
    for s in data.get("services", []):
        s = dict(s); s["protocol"] = ServiceProtocol(s["protocol"])
        if s.get("origin"):
            s["origin"] = ObjectOrigin(s["origin"])
        config.services.append(ServiceObject(**s))
    for sg in data.get("service_groups", []):
        sg = dict(sg)
        if sg.get("origin"):
            sg["origin"] = ObjectOrigin(sg["origin"])
        config.service_groups.append(ServiceGroup(**sg))
    for i in data.get("interfaces", []):
        i = dict(i)
        if i.get("origin"):
            i["origin"] = ObjectOrigin(i["origin"])
        config.interfaces.append(Interface(**i))
    for z in data.get("zones", []):
        z = dict(z)
        if z.get("origin"):
            z["origin"] = ObjectOrigin(z["origin"])
        config.zones.append(Zone(**z))
    for r in data.get("routes", []):
        r = dict(r)
        if r.get("origin"):
            r["origin"] = ObjectOrigin(r["origin"])
        config.routes.append(Route(**r))
    for n in data.get("nat_rules", []):
        n = dict(n)
        if n.get("origin"):
            n["origin"] = ObjectOrigin(n["origin"])
        config.nat_rules.append(NATRule(**n))
    for p in data.get("policies", []):
        p = dict(p); p["action"] = PolicyAction(p["action"])
        if p.get("origin"):
            p["origin"] = ObjectOrigin(p["origin"])
        config.policies.append(Policy(**p))
    for iss in data.get("issues", []):
        config.issues.append(ConversionIssue(**iss))
    config.log_forwarding_profiles = list(data.get("log_forwarding_profiles", []))
    config.security_profile_groups = list(data.get("security_profile_groups", []))

    for x in data.get("ldap_profiles", []):
        x = dict(x)
        if x.get("origin"):
            x["origin"] = ObjectOrigin(x["origin"])
        config.ldap_profiles.append(LdapServerProfile(**x))
    for x in data.get("radius_profiles", []):
        x = dict(x)
        if x.get("origin"):
            x["origin"] = ObjectOrigin(x["origin"])
        config.radius_profiles.append(RadiusServerProfile(**x))
    for x in data.get("tacacs_profiles", []):
        x = dict(x)
        if x.get("origin"):
            x["origin"] = ObjectOrigin(x["origin"])
        config.tacacs_profiles.append(TacacsServerProfile(**x))
    for x in data.get("snmp_profiles", []):
        x = dict(x)
        if x.get("origin"):
            x["origin"] = ObjectOrigin(x["origin"])
        x["users"] = [SnmpUser(**u) for u in x.get("users", [])]
        config.snmp_profiles.append(SnmpProfile(**x))
    for x in data.get("syslog_profiles", []):
        x = dict(x)
        if x.get("origin"):
            x["origin"] = ObjectOrigin(x["origin"])
        config.syslog_profiles.append(SyslogServerProfile(**x))
    for x in data.get("ntp_profiles", []):
        x = dict(x)
        if x.get("origin"):
            x["origin"] = ObjectOrigin(x["origin"])
        config.ntp_profiles.append(NtpProfile(**x))
    for x in data.get("dns_profiles", []):
        x = dict(x)
        if x.get("origin"):
            x["origin"] = ObjectOrigin(x["origin"])
        config.dns_profiles.append(DnsProfile(**x))

    return config


# --- Generic per-category access for the editable-grid endpoints -----------
# Lets the API expose/replace one object list (addresses, services, etc.) at
# a time without hand-writing a to-dict/from-dict pair per category. Built on
# the same dataclasses already defined in app.normalizer.models.

CATEGORY_MODELS: dict[str, type] = {
    "addresses": AddressObject,
    "address_groups": AddressGroup,
    "services": ServiceObject,
    "service_groups": ServiceGroup,
    "interfaces": Interface,
    "policies": Policy,
    "routes": Route,
    "zones": Zone,
    "nat_rules": NATRule,
    "ldap_profiles": LdapServerProfile,
    "radius_profiles": RadiusServerProfile,
    "tacacs_profiles": TacacsServerProfile,
    "snmp_profiles": SnmpProfile,
    "syslog_profiles": SyslogServerProfile,
    "ntp_profiles": NtpProfile,
    "dns_profiles": DnsProfile,
}

# Fields on each model that are enums, and the enum type to coerce string
# values into when rebuilding a dataclass instance from a plain dict (e.g.
# a row edited in the browser and posted back as JSON).
_ENUM_FIELDS: dict[type, dict[str, type]] = {
    AddressObject: {"type": AddressType},
    ServiceObject: {"protocol": ServiceProtocol},
    Policy: {"action": PolicyAction},
}


def get_category_rows(config: NormalizedConfig, category: str) -> list[dict]:
    if category not in CATEGORY_MODELS:
        raise KeyError(f"Unknown object category '{category}'")
    return [dataclasses.asdict(obj) for obj in getattr(config, category)]


# --- Zone <-> Interface synchronization -------------------------------------
# Zone.interfaces (edited on the Zones tab) and Interface.zone (edited on the
# Interfaces tab) describe the same relationship from two directions. Without
# an explicit sync step they silently drift apart - e.g. assigning an
# interface to a zone on the Zones tab previously had zero effect on the
# Interfaces grid, and vice versa. This keeps both views authoritative for
# the field the user just edited, and re-derives the other one from it.


def sync_zones_and_interfaces(config: NormalizedConfig, category: str) -> list[tuple[str, str]]:
    """
    Call this immediately after set_category_rows() for category in
    ("zones", "interfaces"). Returns a list of (interface_name, message)
    pairs (e.g. a zone removed from the Zones tab that an interface still
    references) for the caller to surface as ConversionIssue rows.
    """
    warnings: list[tuple[str, str]] = []

    if category == "zones":
        # The Zones tab is authoritative for what it just submitted -
        # push each zone's member-interface list onto the matching
        # Interface.zone field (matched by PAN-OS interface name first,
        # falling back to the source interface name).
        assigned: dict[str, str] = {}
        for zone in config.zones:
            for member in zone.interfaces:
                assigned[member] = zone.name

        zone_names_now = {z.name for z in config.zones}
        for iface in config.interfaces:
            key = iface.pan_name or iface.name
            if key in assigned:
                iface.zone = assigned[key]
            elif iface.zone and iface.zone not in zone_names_now:
                # This interface still points at a zone name that no
                # longer has a row on the Zones tab (deleted or renamed).
                # Its `set zone` command will still be generated from this
                # interface's own zone field, so warn rather than silently
                # dropping the assignment.
                warnings.append((
                    key,
                    f"Interface '{key}' is still assigned to zone '{iface.zone}', which no "
                    f"longer exists on the Zones tab - it will still be generated from the "
                    f"Interfaces tab. Update or clear it there if that's not intended.",
                ))

    elif category == "interfaces":
        # The Interfaces tab is authoritative for the live per-interface
        # zone field - rebuild the Zones tab list to mirror it, preserving
        # any existing zone description text.
        existing_desc = {z.name: z.description for z in config.zones}
        grouped: dict[str, list[str]] = {}
        for iface in config.interfaces:
            if iface.zone:
                key = iface.pan_name or iface.name
                grouped.setdefault(iface.zone, []).append(key)
        config.zones = [
            Zone(name=name, interfaces=members, description=existing_desc.get(name, ""))
            for name, members in grouped.items()
        ]

    return warnings


def set_category_rows(config: NormalizedConfig, category: str, rows: list[dict]) -> None:
    """
    Replaces the whole list for one category with the rows the client sent
    back (typically the full contents of an edited grid - simplest possible
    contract that still supports add/edit/delete/reorder in one call). Raises
    ValueError/TypeError if a row is missing a required field or has a bad
    enum value, so the route can turn that into a 400 instead of a 500.
    """
    if category not in CATEGORY_MODELS:
        raise KeyError(f"Unknown object category '{category}'")
    model = CATEGORY_MODELS[category]
    enum_fields = _ENUM_FIELDS.get(model, {})
    valid_field_names = {f.name for f in dataclasses.fields(model)}

    rebuilt: list[Any] = []
    for row in rows:
        row = {k: v for k, v in dict(row).items() if k in valid_field_names}
        for field_name, enum_type in enum_fields.items():
            if field_name in row and row[field_name] is not None:
                row[field_name] = enum_type(row[field_name])
        if row.get("origin"):
            row["origin"] = ObjectOrigin(row["origin"])
        rebuilt.append(model(**row))

    setattr(config, category, rebuilt)
