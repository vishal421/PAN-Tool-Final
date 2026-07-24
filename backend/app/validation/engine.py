"""
Live Validation Engine
=======================
Runs against the CURRENT state of a NormalizedConfig - including any edits
made through the object-grid endpoints - and returns a fresh list of
ConversionIssue rows. This is deliberately separate from the one-shot
parser-time issues (e.g. "this dns-domain wildcard has no PAN-OS
equivalent"): those describe translation limitations found while reading
the source vendor file, and are lost by design once a field is edited by
hand upstream of that check. This module instead re-derives structural
issues from whatever the objects currently look like, every time it runs,
so the Validation Center reflects the user's edits rather than a stale
parse-time snapshot.

Covers (see PROMPT.md "Validation Center" section for the full target
list): invalid/reserved characters in names, name length, duplicate names
within a category, missing address/service group members, malformed IP
values, missing zone/virtual-router on layer3 interfaces, and unknown
address/service references on security policies.
"""

from __future__ import annotations

import ipaddress
import re

from app.normalizer.models import ConversionIssue, NormalizedConfig, AddressType

# PAN-OS object names: letters, numbers, spaces, and _ . - ; capped at 63 chars.
_VALID_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-\s]+$")
# Interface identifiers are a special case: real PAN-OS interface names
# legitimately contain '/' (ethernet1/1, ethernet1/1.100), so the general
# object-name charset (no slashes) doesn't apply to them.
_VALID_INTERFACE_NAME_RE = re.compile(r"^[A-Za-z0-9_./\-\s]+$")
_MAX_NAME_LEN = 63

# Names PAN-OS reserves / that commonly collide with built-ins.
_RESERVED_NAMES = {"any", "all", "none", "default"}


def _check_interface_name(issues: list[ConversionIssue], name: str | None) -> None:
    """Like _check_name, but for interface identifiers - real PAN-OS interface
    names legitimately contain '/' (ethernet1/1), so that's allowed here."""
    if not name:
        issues.append(ConversionIssue("error", "interface", "<unnamed>", "Object has no name."))
        return
    if not _VALID_INTERFACE_NAME_RE.match(name):
        bad_chars = sorted(set(ch for ch in name if not _VALID_INTERFACE_NAME_RE.match(ch)))
        issues.append(ConversionIssue(
            "error", "interface", name,
            f"Invalid character(s) {''.join(bad_chars)!r} in interface name - PAN-OS interface "
            f"names may only contain letters, numbers, spaces, and _ . - /",
        ))
    if len(name) > _MAX_NAME_LEN:
        issues.append(ConversionIssue(
            "error", "interface", name,
            f"Name is {len(name)} characters - PAN-OS object names are capped at {_MAX_NAME_LEN}.",
        ))


def _check_name(issues: list[ConversionIssue], object_type: str, name: str | None) -> None:
    if not name:
        issues.append(ConversionIssue("error", object_type, "<unnamed>", "Object has no name."))
        return
    if not _VALID_NAME_RE.match(name):
        bad_chars = sorted(set(ch for ch in name if not _VALID_NAME_RE.match(ch)))
        issues.append(ConversionIssue(
            "error", object_type, name,
            f"Invalid character(s) {''.join(bad_chars)!r} in name - PAN-OS object names "
            f"may only contain letters, numbers, spaces, and _ . -",
        ))
    if len(name) > _MAX_NAME_LEN:
        issues.append(ConversionIssue(
            "error", object_type, name,
            f"Name is {len(name)} characters - PAN-OS object names are capped at {_MAX_NAME_LEN}.",
        ))
    if name.lower() in _RESERVED_NAMES:
        issues.append(ConversionIssue(
            "warning", object_type, name,
            f"'{name}' is a PAN-OS reserved word - it may be rejected or misinterpreted on import.",
        ))


def _check_duplicates(issues: list[ConversionIssue], object_type: str, names: list[str]) -> None:
    seen: dict[str, int] = {}
    for n in names:
        seen[n] = seen.get(n, 0) + 1
    for n, count in seen.items():
        if count > 1:
            issues.append(ConversionIssue(
                "error", object_type, n,
                f"Duplicate {object_type} name - defined {count} times. PAN-OS requires unique names per object type.",
            ))


def _check_ip_value(issues: list[ConversionIssue], name: str, addr_type: AddressType, value: str) -> None:
    if addr_type == AddressType.IP_NETMASK:
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError:
            issues.append(ConversionIssue("error", "address", name, f"Invalid IP/netmask value: '{value}'"))
    elif addr_type == AddressType.IP_RANGE:
        parts = value.split("-")
        if len(parts) != 2:
            issues.append(ConversionIssue("error", "address", name, f"Invalid IP range value: '{value}' (expected 'start-end')"))
        else:
            for part in parts:
                try:
                    ipaddress.ip_address(part.strip())
                except ValueError:
                    issues.append(ConversionIssue("error", "address", name, f"Invalid IP address '{part.strip()}' in range '{value}'"))


def _check_port(issues: list[ConversionIssue], object_type: str, name: str, label: str, port) -> None:
    if port is None:
        return
    try:
        p = int(port)
    except (TypeError, ValueError):
        issues.append(ConversionIssue("error", object_type, name, f"{label} '{port}' is not a valid port number."))
        return
    if not (1 <= p <= 65535):
        issues.append(ConversionIssue("error", object_type, name, f"{label} {p} is out of the valid 1-65535 range."))


def _check_host(issues: list[ConversionIssue], object_type: str, name: str, label: str, host: str) -> None:
    """Accepts a bare IP or 'host:port' pair, validates the IP part if present."""
    if not host:
        return
    ip_part = host.split(":", 1)[0]
    try:
        ipaddress.ip_address(ip_part)
    except ValueError:
        # Not every vendor server field is guaranteed to be a literal IP
        # (some accept hostnames) - only flag it as information, not an error.
        issues.append(ConversionIssue(
            "information", object_type, name,
            f"{label} '{host}' is not a literal IP address - if it's a hostname, verify it resolves "
            f"from the PAN-OS management/service-route context.",
        ))


def validate_config(config: NormalizedConfig) -> list[ConversionIssue]:
    issues: list[ConversionIssue] = []

    total_objects = (
        len(config.addresses) + len(config.address_groups) + len(config.services) + len(config.service_groups)
        + len(config.interfaces) + len(config.zones) + len(config.routes) + len(config.nat_rules)
        + len(config.policies) + len(config.ldap_profiles) + len(config.radius_profiles)
        + len(config.tacacs_profiles) + len(config.snmp_profiles) + len(config.syslog_profiles)
        + len(config.ntp_profiles) + len(config.dns_profiles)
    )
    if total_objects == 0:
        issues.append(ConversionIssue(
            "error", "config", "<empty>",
            "No objects were found anywhere in this configuration - check that the correct vendor "
            "was selected and that the uploaded file isn't empty or truncated.",
        ))

    address_names = {a.name for a in config.addresses}
    group_names = {g.name for g in config.address_groups}
    service_names = {s.name for s in config.services}
    svc_group_names = {g.name for g in config.service_groups}

    for a in config.addresses:
        _check_name(issues, "address", a.name)
        _check_ip_value(issues, a.name, a.type, a.value)
    _check_duplicates(issues, "address", [a.name for a in config.addresses])

    for g in config.address_groups:
        _check_name(issues, "address_group", g.name)
        for member in g.members:
            if member not in address_names and member not in group_names:
                issues.append(ConversionIssue(
                    "warning", "address_group", g.name,
                    f"Member '{member}' does not match any known address object or group - it will be "
                    f"emitted as-is, so make sure it exists on the target firewall (or rename it here).",
                ))
    _check_duplicates(issues, "address_group", [g.name for g in config.address_groups])

    for s in config.services:
        _check_name(issues, "service", s.name)
    _check_duplicates(issues, "service", [s.name for s in config.services])

    for sg in config.service_groups:
        _check_name(issues, "service_group", sg.name)
        for member in sg.members:
            if member not in service_names and member not in svc_group_names:
                issues.append(ConversionIssue(
                    "warning", "service_group", sg.name,
                    f"Member '{member}' does not match any known service object or group.",
                ))
    _check_duplicates(issues, "service_group", [sg.name for sg in config.service_groups])

    for i in config.interfaces:
        _check_interface_name(issues, i.name)
        if i.interface_type == "layer3":
            if not i.zone:
                issues.append(ConversionIssue("warning", "interface", i.name, "No security zone assigned."))
            if not i.virtual_router:
                issues.append(ConversionIssue("warning", "interface", i.name, "No virtual router assigned."))
    _check_duplicates(issues, "interface", [i.name for i in config.interfaces])

    known_addr_refs = address_names | group_names | {"any"}
    known_svc_refs = service_names | svc_group_names | {"any"}
    for p in config.policies:
        _check_name(issues, "policy", p.name)
        for addr in (p.source_address or []) + (p.dest_address or []):
            if addr not in known_addr_refs:
                issues.append(ConversionIssue(
                    "warning", "policy", p.name,
                    f"References unknown address object/group '{addr}'.",
                ))
        for svc in p.service or []:
            if svc not in known_svc_refs and "/" not in svc:
                issues.append(ConversionIssue(
                    "warning", "policy", p.name,
                    f"References unknown service object/group '{svc}'.",
                ))
    _check_duplicates(issues, "policy", [p.name for p in config.policies])

    # --- NAT Rules ---------------------------------------------------------
    for n in config.nat_rules:
        _check_name(issues, "nat", n.name)
        for addr in (n.source_address or []) + (n.dest_address or []):
            if addr not in known_addr_refs:
                issues.append(ConversionIssue(
                    "warning", "nat", n.name,
                    f"References unknown address object/group '{addr}'.",
                ))
        if not n.translated_source and not n.translated_dest:
            issues.append(ConversionIssue(
                "error", "nat", n.name,
                "NAT rule has no source or destination translation configured - it won't do anything.",
            ))
        if n.translated_dest:
            try:
                ipaddress.ip_address(n.translated_dest)
            except ValueError:
                issues.append(ConversionIssue("error", "nat", n.name, f"Invalid translated destination IP '{n.translated_dest}'."))
        if n.original_port:
            _check_port(issues, "nat", n.name, "Original port", n.original_port)
        if n.translated_port:
            _check_port(issues, "nat", n.name, "Translated port", n.translated_port)
        if (n.original_port and not n.translated_port) or (n.translated_port and not n.original_port):
            issues.append(ConversionIssue(
                "warning", "nat", n.name,
                "Port-forwarding NAT needs both an original and a translated port - only one is set.",
            ))
    _check_duplicates(issues, "nat", [n.name for n in config.nat_rules])

    # --- LDAP ---------------------------------------------------------------
    for p in config.ldap_profiles:
        _check_name(issues, "ldap", p.name)
        if not p.servers:
            issues.append(ConversionIssue("error", "ldap", p.name, "LDAP profile has no server address configured."))
        for s in p.servers:
            _check_host(issues, "ldap", p.name, "LDAP server", s)
        if not p.base_dn:
            issues.append(ConversionIssue("warning", "ldap", p.name, "No Base DN configured - most LDAP directory searches will fail without one."))
        if not p.bind_dn:
            issues.append(ConversionIssue("information", "ldap", p.name, "No Bind DN configured - profile will attempt an anonymous bind."))
    _check_duplicates(issues, "ldap", [p.name for p in config.ldap_profiles])

    # --- RADIUS ---------------------------------------------------------------
    for p in config.radius_profiles:
        _check_name(issues, "radius", p.name)
        if not p.servers:
            issues.append(ConversionIssue("error", "radius", p.name, "RADIUS profile has no server address configured."))
        for s in p.servers:
            _check_host(issues, "radius", p.name, "RADIUS server", s)
        if not p.shared_secret:
            issues.append(ConversionIssue("warning", "radius", p.name, "No shared secret found on the source config - one must be set manually before use."))
        _check_port(issues, "radius", p.name, "Authentication port", p.auth_port)
        _check_port(issues, "radius", p.name, "Accounting port", p.acct_port)
    _check_duplicates(issues, "radius", [p.name for p in config.radius_profiles])

    # --- TACACS+ -----------------------------------------------------------
    for p in config.tacacs_profiles:
        _check_name(issues, "tacacs", p.name)
        if not p.servers:
            issues.append(ConversionIssue("error", "tacacs", p.name, "TACACS+ profile has no server address configured."))
        for s in p.servers:
            _check_host(issues, "tacacs", p.name, "TACACS+ server", s)
        if not p.shared_secret:
            issues.append(ConversionIssue("warning", "tacacs", p.name, "No shared secret found on the source config - one must be set manually before use."))
    _check_duplicates(issues, "tacacs", [p.name for p in config.tacacs_profiles])

    # --- SNMP ----------------------------------------------------------------
    for p in config.snmp_profiles:
        _check_name(issues, "snmp", p.name)
        if p.version == "v2c" and not p.community:
            issues.append(ConversionIssue("warning", "snmp", p.name, "SNMPv2c profile has no community string configured."))
        if p.version == "v3" and not p.users:
            issues.append(ConversionIssue("warning", "snmp", p.name, "SNMPv3 profile has no users configured."))
        for u in p.users:
            if not u.auth_protocol or not u.priv_protocol:
                issues.append(ConversionIssue("information", "snmp", p.name, f"SNMPv3 user '{u.name}' is missing auth or privacy protocol - review before export."))
        for dest in p.trap_destinations:
            _check_host(issues, "snmp", p.name, "Trap destination", dest)
    _check_duplicates(issues, "snmp", [p.name for p in config.snmp_profiles])

    # --- Syslog --------------------------------------------------------------
    for p in config.syslog_profiles:
        _check_name(issues, "syslog", p.name)
        if not p.server:
            issues.append(ConversionIssue("error", "syslog", p.name, "Syslog profile has no server address configured."))
        else:
            _check_host(issues, "syslog", p.name, "Syslog server", p.server)
        _check_port(issues, "syslog", p.name, "Port", p.port)
    _check_duplicates(issues, "syslog", [p.name for p in config.syslog_profiles])

    # --- NTP -------------------------------------------------------------
    for p in config.ntp_profiles:
        if not p.primary_server and not p.secondary_server:
            issues.append(ConversionIssue("error", "ntp", p.name, "NTP is enabled but no server address was found."))
        if p.primary_server:
            _check_host(issues, "ntp", p.name, "Primary NTP server", p.primary_server)
        if p.secondary_server:
            _check_host(issues, "ntp", p.name, "Secondary NTP server", p.secondary_server)

    # --- DNS -------------------------------------------------------------
    for p in config.dns_profiles:
        if not p.primary_dns and not p.secondary_dns:
            issues.append(ConversionIssue("warning", "dns", p.name, "DNS configuration has no primary or secondary server address."))
        if p.primary_dns:
            _check_host(issues, "dns", p.name, "Primary DNS server", p.primary_dns)
        if p.secondary_dns:
            _check_host(issues, "dns", p.name, "Secondary DNS server", p.secondary_dns)

    return issues
