"""
Sophos XG (SFOS) Parser
========================
Unlike FortiGate/Cisco/Check Point (line-oriented CLI exports), the
migration-relevant Sophos XG export is its XML system backup
(Backup & Firmware > Backup), a proper nested XML document. This module
parses it with xml.etree.ElementTree rather than any text tokenizer -
XML's own structure already gives us resilience to whitespace, comments,
and nesting, so there's no reason to reinvent that.

Covers:
  <IPHost>            -> AddressObject (HostType: IP / Network / IPRange / FQDNHost)
  <IPHostGroup>        -> AddressGroup
  <Services><Service>  -> ServiceObject (one per <ServiceDetail>)
  <ServiceGroup>        -> ServiceGroup
  <Interface>            -> Interface (Sophos natively assigns a Zone per
                            interface, unlike FortiGate/Cisco - still only
                            used as a mapping-step hint, never auto-applied)
  <StaticRoute>           -> Route
  <FirewallRule>           -> Policy (best-effort)
  <NATRule>                 -> NATRule (best-effort; Sophos lets SNAT name a
                              specific outbound interface, so this resolves
                              cleanly through the interface mapping step)

Sophos backups can contain many unrelated sections (IPS policies, web
filtering, admin settings, etc.) - anything outside the elements above is
simply not visited, not flagged, since it's out of scope for a firewall
rule/object migration rather than an unsupported construct within scope.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from app.normalizer.models import (
    AddressObject, AddressGroup, AddressType,
    ServiceObject, ServiceGroup, ServiceProtocol,
    Interface, Zone, Route, NATRule, Policy, PolicyAction,
    ObjectOrigin,
)
from app.parsers.base import BaseParser

_PROTO_MAP = {"TCP": ServiceProtocol.TCP, "UDP": ServiceProtocol.UDP, "SCTP": ServiceProtocol.SCTP}


def _text(elem: ET.Element | None, tag: str, default: str | None = None) -> str | None:
    if elem is None:
        return default
    child = elem.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _text_list(elem: ET.Element, container_tag: str, item_tag: str) -> list[str]:
    container = elem.find(container_tag)
    if container is None:
        return []
    return [c.text.strip() for c in container.findall(item_tag) if c.text]


class SophosXGParser(BaseParser):
    vendor_key = "sophos"
    vendor_label = "Sophos XG"

    def __init__(self, raw_text: str, filename: str = ""):
        super().__init__(raw_text, filename)
        try:
            self._root = ET.fromstring(raw_text)
        except ET.ParseError as exc:
            self._root = None
            self.error("document", filename or "<upload>", f"Could not parse XML: {exc}")

    def _findall(self, tag: str) -> list[ET.Element]:
        if self._root is None:
            return []
        # Sophos backups nest everything under a root <Configuration> (or
        # similar) element, sometimes with intermediate grouping elements
        # that vary by firmware version - search the whole tree rather than
        # assuming a fixed depth.
        return self._root.findall(f".//{tag}")

    # ---- Addresses ------------------------------------------------------
    def parse_addresses(self) -> tuple[list[AddressObject], list[AddressGroup]]:
        addresses: list[AddressObject] = []
        seen: set[str] = set()

        for host in self._findall("IPHost"):
            name = _text(host, "Name")
            if not name:
                self.unsupported("address", "<unnamed>", "IPHost element has no <Name>")
                continue
            if name in seen:
                self.warn("address", name, "Duplicate IPHost name - later definition used")
            seen.add(name)

            host_type = _text(host, "HostType", "IP")
            desc = _text(host, "Description", "") or ""

            if host_type == "IP":
                ip = _text(host, "IPAddress")
                if ip:
                    addresses.append(AddressObject(name=name, type=AddressType.IP_NETMASK, value=f"{ip}/32",
                                                     description=desc, origin=ObjectOrigin.SOPHOS_XG))
                else:
                    self.unsupported("address", name, "HostType=IP but missing <IPAddress>")
            elif host_type == "Network":
                subnet = _text(host, "IPAddress") or _text(host, "Subnet")
                netmask = _text(host, "Netmask")
                if subnet and netmask:
                    addresses.append(AddressObject(name=name, type=AddressType.IP_NETMASK,
                                                     value=f"{subnet}/{_mask_to_cidr(netmask)}",
                                                     description=desc, origin=ObjectOrigin.SOPHOS_XG))
                else:
                    self.unsupported("address", name, "HostType=Network missing IPAddress/Subnet or Netmask")
            elif host_type == "IPRange":
                start = _text(host, "StartIPAddress")
                end = _text(host, "EndIPAddress")
                if start and end:
                    addresses.append(AddressObject(name=name, type=AddressType.IP_RANGE, value=f"{start}-{end}",
                                                     description=desc, origin=ObjectOrigin.SOPHOS_XG))
                else:
                    self.unsupported("address", name, "HostType=IPRange missing StartIPAddress/EndIPAddress")
            elif host_type in ("FQDNHost", "DNS"):
                fqdn = _text(host, "FQDNHostName") or _text(host, "FQDN")
                name_type = _text(host, "FQDNHostNameType", "Exact")
                if not fqdn:
                    self.unsupported("address", name, f"HostType={host_type} missing FQDN hostname field")
                elif name_type == "Wildcard":
                    self.unsupported(
                        "address", name,
                        f"FQDN host '{fqdn}' is a wildcard match - PAN-OS FQDN address objects "
                        f"require an exact hostname. Recreate as an EDL or a specific FQDN object.",
                    )
                else:
                    addresses.append(AddressObject(name=name, type=AddressType.FQDN, value=fqdn,
                                                     description=desc, origin=ObjectOrigin.SOPHOS_XG))
            else:
                self.unsupported("address", name, f"Unrecognized HostType '{host_type}'")

        groups: list[AddressGroup] = []
        for grp in self._findall("IPHostGroup"):
            name = _text(grp, "Name")
            if not name:
                continue
            members = _text_list(grp, "HostList", "Host")
            desc = _text(grp, "Description", "") or ""
            groups.append(AddressGroup(name=name, members=members, description=desc,
                                        origin=ObjectOrigin.SOPHOS_XG))
        return addresses, groups

    # ---- Services -----------------------------------------------------
    def parse_services(self) -> tuple[list[ServiceObject], list[ServiceGroup]]:
        services: list[ServiceObject] = []
        for svc in self._findall("Service"):
            name = _text(svc, "Name")
            if not name:
                continue
            svc_type = _text(svc, "Type", "")
            details_container = svc.find("ServiceDetails")
            details = details_container.findall("ServiceDetail") if details_container is not None else []

            if not details:
                self.unsupported("service", name, "Service has no <ServiceDetail> entries - could not convert")
                continue

            for idx, detail in enumerate(details, start=1):
                proto = _text(detail, "Protocol", "")
                dest_port = _text(detail, "DestinationPort")
                src_port = _text(detail, "SourcePort")
                icmp_type = _text(detail, "ICMPType")
                icmp_code = _text(detail, "ICMPCode")
                # Multiple details under one Service name need distinct
                # ServiceObject names downstream - suffix only when needed.
                obj_name = name if len(details) == 1 else f"{name}_{idx}"

                if proto in _PROTO_MAP and dest_port:
                    services.append(ServiceObject(
                        name=obj_name, protocol=_PROTO_MAP[proto], dest_port=dest_port,
                        source_port=src_port, origin=ObjectOrigin.SOPHOS_XG,
                    ))
                elif proto == "ICMP":
                    services.append(ServiceObject(
                        name=obj_name, protocol=ServiceProtocol.ICMP,
                        icmp_type=int(icmp_type) if icmp_type and icmp_type.isdigit() else None,
                        icmp_code=int(icmp_code) if icmp_code and icmp_code.isdigit() else None,
                        origin=ObjectOrigin.SOPHOS_XG,
                    ))
                else:
                    self.unsupported("service", obj_name, f"Unrecognized/incomplete ServiceDetail "
                                      f"(Protocol={proto}, type={svc_type}) - could not convert")

        groups: list[ServiceGroup] = []
        for grp in self._findall("ServiceGroup"):
            name = _text(grp, "Name")
            if not name:
                continue
            members = _text_list(grp, "ServiceList", "Service")
            groups.append(ServiceGroup(name=name, members=members, origin=ObjectOrigin.SOPHOS_XG))
        return services, groups

    # ---- Interfaces -----------------------------------------------------
    def parse_interfaces(self) -> tuple[list[Interface], list[Zone]]:
        interfaces: list[Interface] = []
        for iface in self._findall("Interface"):
            name = _text(iface, "Name")
            if not name:
                continue
            ip = _text(iface, "IPAddress")
            netmask = _text(iface, "Netmask")
            zone = _text(iface, "Zone")
            mtu = _text(iface, "MTU")
            mode = _text(iface, "ConfigurationMethod", "Static")
            desc = _text(iface, "Description", "") or ""

            interfaces.append(Interface(
                name=name,
                description=desc,
                ip_address=ip,
                netmask=netmask,
                zone=zone,  # Sophos assigns a real Zone per interface natively - still only a hint here
                mtu=int(mtu) if mtu and mtu.isdigit() else None,
                dhcp_enabled=(mode == "DHCP"),
                origin=ObjectOrigin.SOPHOS_XG,
            ))
            if not zone:
                self.warn("interface", name, "No <Zone> set on this interface - assign one in the "
                          "interface mapping step before generating.")
        return interfaces, self.derive_zones_from_interfaces(interfaces)

    # ---- Routes -----------------------------------------------------------
    def parse_routes(self) -> list[Route]:
        routes: list[Route] = []
        for route in self._findall("StaticRoute"):
            name = _text(route, "Name")
            dest = _text(route, "Network") or _text(route, "Destination")
            netmask = _text(route, "Netmask")
            gateway = _text(route, "Gateway")
            interface = _text(route, "Interface")
            if not dest:
                self.unsupported("route", name or "<unnamed>", "StaticRoute missing <Network>/<Destination>")
                continue
            destination = f"{dest}/{_mask_to_cidr(netmask)}" if netmask else dest
            routes.append(Route(
                name=name, destination=destination, next_hop=gateway,
                interface=interface, origin=ObjectOrigin.SOPHOS_XG,
            ))
        return routes

    # ---- Policies + NAT (best-effort) -------------------------------------
    def parse_policies(self) -> tuple[list[Policy], list[NATRule]]:
        policies: list[Policy] = []
        for rule in self._findall("FirewallRule"):
            name = _text(rule, "Name")
            if not name:
                continue
            status = _text(rule, "Status", "Enable")
            action_raw = _text(rule, "Action", "Drop")
            log_raw = _text(rule, "LogTraffic", "Disable")
            desc = _text(rule, "Description", "") or ""

            src_zones = _normalize_any(_text_list(rule, "SourceZones", "Zone")) or ["any"]
            dst_zones = _normalize_any(_text_list(rule, "DestinationZones", "Zone")) or ["any"]
            src_nets = _normalize_any(_text_list(rule, "SourceNetworks", "Network")) or ["any"]
            dst_nets = _normalize_any(_text_list(rule, "DestinationNetworks", "Network")) or ["any"]
            services = _normalize_any(_text_list(rule, "Services", "Service")) or ["any"]

            policies.append(Policy(
                name=name,
                source_zone=src_zones, dest_zone=dst_zones,
                source_address=src_nets, dest_address=dst_nets, service=services,
                action=PolicyAction.ALLOW if action_raw == "Accept" else PolicyAction.DENY,
                log_end=log_raw == "Enable",
                description=desc,
                disabled=status != "Enable",
                origin=ObjectOrigin.SOPHOS_XG,
            ))

        nat_rules: list[NATRule] = []
        for nat in self._findall("NATRule"):
            name = _text(nat, "Name")
            if not name:
                continue
            orig_src = _normalize_any(_text_list(nat, "OriginalSourceNetworks", "Network")) or ["any"]
            translated_src = _text(nat, "TranslatedSource")
            outbound_ifaces = _text_list(nat, "OutboundInterfaces", "Interface")
            translated_dst = _text(nat, "TranslatedDestination")

            if translated_src in ("MASQ", "Interface"):
                # Sophos "masquerade" SNAT - unlike Check Point's hide-behind-
                # gateway, Sophos lets the rule name a specific outbound
                # interface, so this resolves cleanly through the mapping
                # step instead of falling back to a manual-review TODO.
                nat_rules.append(NATRule(
                    name=name, source_address=orig_src,
                    dest_zone=outbound_ifaces[0] if outbound_ifaces else None,
                    translated_source="interface", nat_type="dynamic-ip-and-port",
                    origin=ObjectOrigin.SOPHOS_XG,
                ))
            elif translated_src:
                nat_rules.append(NATRule(
                    name=name, source_address=orig_src,
                    translated_source=translated_src, nat_type="dynamic-ip-and-port",
                    origin=ObjectOrigin.SOPHOS_XG,
                ))
            elif translated_dst:
                nat_rules.append(NATRule(
                    name=name, source_address=orig_src,
                    translated_dest=translated_dst, nat_type="static",
                    origin=ObjectOrigin.SOPHOS_XG,
                ))
            else:
                self.unsupported("nat", name, "NATRule has neither TranslatedSource nor TranslatedDestination")

        return policies, nat_rules


def _normalize_any(values: list[str]) -> list[str]:
    """Sophos XML literally spells its wildcard placeholder 'Any' - normalize
    to the lowercase 'any' convention used everywhere else in this tool
    (FortiGate/Cisco/Check Point all use lowercase), so the interface
    mapping step's special-case for 'any' actually matches."""
    return ["any" if v.lower() == "any" else v for v in values]


def _mask_to_cidr(mask):
    if not mask:
        return "32"
    if mask.isdigit():
        return mask
    try:
        octets = [int(o) for o in mask.split(".")]
        return str(sum(bin(o).count("1") for o in octets))
    except (ValueError, AttributeError):
        return mask
