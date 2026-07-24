"""
Interface Mapping
==================
Cisco ASA and FortiGate are interface-based; PAN-OS is zone-based. Rather
than guess a zone mapping, this module applies a user-confirmed mapping
(one entry per source interface) across the whole NormalizedConfig:
interfaces, zones, virtual routers, security policies, NAT rules, and
static routes all get rewritten consistently from the same mapping table.

Nothing downstream of apply_mapping() should ever see a raw vendor
interface name again - that's the contract this module exists to
guarantee (see: "No generated configuration should reference the
original Cisco or FortiGate interface names once the mapping has been
completed").
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Optional

from app.normalizer.models import NormalizedConfig, Zone, ConversionIssue

VALID_INTERFACE_TYPES = ("layer3", "layer2", "vwire")


@dataclass
class InterfaceMappingEntry:
    source_interface: str            # must match an Interface.name in the parsed config
    pan_interface: str                # e.g. "ethernet1/1"
    zone: str                         # e.g. "LAN", "DMZ", or any custom value
    virtual_router: str = "default"
    interface_type: str = "layer3"
    ip_address: Optional[str] = None  # overrides the parsed value if provided
    netmask: Optional[str] = None
    description: str = ""
    enabled: bool = True


@dataclass
class MappingValidationResult:
    issues: list[ConversionIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ConversionIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ConversionIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def blocking(self) -> bool:
        """Generation should not proceed while there are unresolved errors."""
        return len(self.errors) > 0


def validate_mapping(config: NormalizedConfig, mappings: list[InterfaceMappingEntry]) -> MappingValidationResult:
    """
    Implements the validation checks: unmapped interface, missing zone,
    missing virtual router, duplicate PAN interface assignment, duplicate
    zone name across conflicting virtual routers, invalid IP address, and
    NAT/policy references to an interface with no mapping entry.

    Errors block generation; warnings don't.
    """
    result = MappingValidationResult()
    mapped_by_source = {m.source_interface: m for m in mappings}

    # --- unmapped interfaces --------------------------------------------
    for iface in config.interfaces:
        if iface.name not in mapped_by_source:
            result.issues.append(ConversionIssue(
                "error", "interface", iface.name,
                "No mapping entry provided for this interface - map it before generating.",
            ))

    # --- per-entry field checks ------------------------------------------
    seen_pan_interfaces: dict[str, str] = {}
    zone_to_vrs: dict[str, set[str]] = {}
    for m in mappings:
        if not m.zone or not m.zone.strip():
            result.issues.append(ConversionIssue(
                "error", "interface", m.source_interface, "Zone is required and cannot be blank.",
            ))
        if not m.virtual_router or not m.virtual_router.strip():
            result.issues.append(ConversionIssue(
                "error", "interface", m.source_interface, "Virtual router is required and cannot be blank.",
            ))
        if not m.pan_interface or not m.pan_interface.strip():
            result.issues.append(ConversionIssue(
                "error", "interface", m.source_interface, "PAN-OS interface name is required.",
            ))
        if m.interface_type not in VALID_INTERFACE_TYPES:
            result.issues.append(ConversionIssue(
                "error", "interface", m.source_interface,
                f"interface_type must be one of {VALID_INTERFACE_TYPES}, got '{m.interface_type}'",
            ))

        if m.pan_interface:
            prior = seen_pan_interfaces.get(m.pan_interface)
            if prior and prior != m.source_interface:
                result.issues.append(ConversionIssue(
                    "error", "interface", m.source_interface,
                    f"PAN-OS interface '{m.pan_interface}' is already assigned to source "
                    f"interface '{prior}' - each PAN-OS interface can only be used once.",
                ))
            seen_pan_interfaces[m.pan_interface] = m.source_interface

        if m.zone:
            zone_to_vrs.setdefault(m.zone, set()).add(m.virtual_router or "")

        if m.ip_address:
            try:
                ipaddress.ip_address(m.ip_address)
            except ValueError:
                result.issues.append(ConversionIssue(
                    "error", "interface", m.source_interface, f"Invalid IP address: '{m.ip_address}'",
                ))
        if m.netmask and not m.netmask.isdigit():
            try:
                ipaddress.ip_address(m.netmask)
            except ValueError:
                result.issues.append(ConversionIssue(
                    "error", "interface", m.source_interface, f"Invalid netmask/prefix: '{m.netmask}'",
                ))

    for zone_name, vrs in zone_to_vrs.items():
        if len(vrs) > 1:
            result.issues.append(ConversionIssue(
                "warning", "zone", zone_name,
                f"Zone '{zone_name}' is used with interfaces in different virtual routers "
                f"({sorted(vrs)}) - double check this is intentional.",
            ))

    # --- dangling references from policies/NAT/routes --------------------
    known_sources = set(mapped_by_source.keys()) | {"any"}
    for p in config.policies:
        for z in (p.source_zone or []):
            if z not in known_sources:
                result.issues.append(ConversionIssue(
                    "warning", "policy", p.name,
                    f"Source zone/interface '{z}' has no mapping entry - will pass through as a "
                    f"literal zone name; verify it's correct or add a mapping for it.",
                ))
        for z in (p.dest_zone or []):
            if z not in known_sources:
                result.issues.append(ConversionIssue(
                    "warning", "policy", p.name,
                    f"Destination zone/interface '{z}' has no mapping entry - will pass through as "
                    f"a literal zone name; verify it's correct or add a mapping for it.",
                ))
    for n in config.nat_rules:
        for z in (n.source_zone or []):
            if z not in known_sources:
                result.issues.append(ConversionIssue(
                    "warning", "nat", n.name,
                    f"NAT rule references unmapped source interface '{z}'.",
                ))
        if n.dest_zone and n.dest_zone not in known_sources:
            result.issues.append(ConversionIssue(
                "warning", "nat", n.name,
                f"NAT rule references unmapped destination interface '{n.dest_zone}'.",
            ))
    for r in config.routes:
        if r.interface and r.interface not in known_sources:
            result.issues.append(ConversionIssue(
                "warning", "route", r.name or r.destination,
                f"Route references unmapped interface '{r.interface}'.",
            ))

    return result


def apply_mapping(config: NormalizedConfig, mappings: list[InterfaceMappingEntry]) -> NormalizedConfig:
    """
    Rewrites the config in place using the confirmed mapping:
      - each Interface gets pan_name/zone/virtual_router/interface_type/
        ip_address/netmask/description/enabled from its mapping entry
      - config.zones is rebuilt from the distinct zones referenced by the
        mapping (Zone Creation step - only happens here, after confirmation)
      - Policy.source_zone/dest_zone are rewritten from raw interface names
        to their mapped zone names
      - NATRule.source_zone/dest_zone likewise, and translated_source
        'interface' markers are resolved to the mapped interface's actual
        IP address where known
      - Route.interface and Route.virtual_router are rewritten

    Entries with no matching interface in the mapping table are left as
    literal strings (already flagged as warnings by validate_mapping).
    """
    by_source = {m.source_interface: m for m in mappings}

    # Interfaces
    for iface in config.interfaces:
        m = by_source.get(iface.name)
        if not m:
            continue
        iface.pan_name = m.pan_interface
        iface.zone = m.zone
        iface.virtual_router = m.virtual_router
        iface.interface_type = m.interface_type
        iface.enabled = m.enabled
        if m.ip_address:
            iface.ip_address = m.ip_address
        if m.netmask:
            iface.netmask = m.netmask
        if m.description:
            iface.description = m.description

    # Zones - rebuilt fresh from the confirmed mapping (Zone Creation step).
    # Preserve any existing description/origin per zone name - this runs on
    # every Generate click (not just the first), and previously discarded
    # whatever the user had typed on the Zones tab each time.
    existing_zone_desc = {z.name: z.description for z in config.zones}
    existing_zone_origin = {z.name: z.origin for z in config.zones}
    zone_interfaces: dict[str, list[str]] = {}
    for m in mappings:
        zone_interfaces.setdefault(m.zone, []).append(m.pan_interface)
    config.zones = [
        Zone(name=z, interfaces=ifaces, description=existing_zone_desc.get(z, ""), origin=existing_zone_origin.get(z))
        for z, ifaces in zone_interfaces.items()
    ]

    def _translate(name: str) -> str:
        if name == "any":
            return "any"
        m = by_source.get(name)
        return m.zone if m else name

    # Policies
    for p in config.policies:
        p.source_zone = [_translate(z) for z in (p.source_zone or [])]
        p.dest_zone = [_translate(z) for z in (p.dest_zone or [])]

    # NAT rules
    for n in config.nat_rules:
        raw_dest = n.dest_zone
        if n.translated_source == "interface":
            # resolve to the mapped egress interface before the raw interface
            # name gets translated into a zone name below - PAN-OS still
            # requires naming the interface explicitly for this NAT sub-type,
            # so store the PAN interface name as a marker for the generator
            # to build 'interface-address interface <name>'.
            m = by_source.get(raw_dest) if raw_dest else None
            if m:
                n.translated_source = f"interface:{m.pan_interface}"

        n.source_zone = [_translate(z) for z in (n.source_zone or [])]
        if n.dest_zone:
            n.dest_zone = _translate(n.dest_zone)

    # Routes
    for r in config.routes:
        m = by_source.get(r.interface) if r.interface else None
        if m:
            r.interface = m.pan_interface
            r.virtual_router = m.virtual_router

    return config
