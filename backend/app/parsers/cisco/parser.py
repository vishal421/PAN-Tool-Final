"""
Cisco ASA Parser
================
Covers:
  object network ...            -> AddressObject (host/subnet/range/fqdn)
  object-group network ...      -> AddressGroup
  object service ...            -> ServiceObject (tcp/udp destination eq/range; icmp)
  object-group service ...      -> ServiceGroup
  interface ... / nameif / mtu  -> Interface
  route ...                     -> Route
  access-list extended ...      -> Policy (best-effort, paired with access-group
                                    bindings to approximate source/dest zone)

ASA's ACL grammar has many optional forms (source port AND dest port,
"object-group" as a protocol placeholder, icmp type/code, "log" trailing
keyword, remarks, etc). This parser handles the common permit/deny +
tcp/udp/icmp forms cleanly and reports anything else via
`self.unsupported(...)` rather than guessing at semantics.
"""

from __future__ import annotations

from app.normalizer.models import (
    AddressObject, AddressGroup, AddressType,
    ServiceObject, ServiceGroup, ServiceProtocol,
    Interface, Zone, Route, NATRule, Policy, PolicyAction,
    ObjectOrigin,
)
from app.parsers.base import BaseParser
from app.parsers.cisco.tokenizer import group_lines, tokens

_PROTO_MAP = {
    "tcp": ServiceProtocol.TCP,
    "udp": ServiceProtocol.UDP,
    "sctp": ServiceProtocol.SCTP,
}


class CiscoASAParser(BaseParser):
    vendor_key = "cisco"
    vendor_label = "Cisco ASA"

    def __init__(self, raw_text: str, filename: str = ""):
        super().__init__(raw_text, filename)
        self._groups = group_lines(raw_text)
        # nameif -> interface hardware name, and reverse, populated during parse_interfaces()
        self._nameif_to_ifname: dict[str, str] = {}
        # acl_name -> (direction "in"|"out", nameif), populated during parse_policies() pre-pass
        self._acl_bindings: dict[str, tuple[str, str]] = {}

    # ---- Addresses ------------------------------------------------------
    def parse_addresses(self) -> tuple[list[AddressObject], list[AddressGroup]]:
        addresses: list[AddressObject] = []
        object_names_seen: set[str] = set()

        for parent, children in self._groups:
            ptoks = tokens(parent)
            if len(ptoks) >= 3 and ptoks[0] == "object" and ptoks[1] == "network":
                name = ptoks[2]
                if name in object_names_seen:
                    self.warn("address", name, "Duplicate object network name - later definition used")
                object_names_seen.add(name)

                addr = self._parse_network_object_body(name, children)
                if addr:
                    addresses.append(addr)

        groups: list[AddressGroup] = []
        for parent, children in self._groups:
            ptoks = tokens(parent)
            if len(ptoks) >= 3 and ptoks[0] == "object-group" and ptoks[1] == "network":
                name = ptoks[2]
                members: list[str] = []
                inline_counter = 0
                for child in children:
                    ctoks = tokens(child)
                    if not ctoks:
                        continue
                    if ctoks[0] == "network-object" and len(ctoks) >= 2 and ctoks[1] == "object":
                        members.append(ctoks[2])
                    elif ctoks[0] == "network-object" and len(ctoks) >= 2 and ctoks[1] == "host":
                        # Inline host inside a group with no standalone object - synthesize
                        # an address object name so it can still be referenced as a group member.
                        inline_counter += 1
                        synth_name = f"{name}_host{inline_counter}"
                        addresses.append(AddressObject(
                            name=synth_name, type=AddressType.IP_NETMASK, value=f"{ctoks[2]}/32",
                            origin=ObjectOrigin.CISCO_ASA,
                            description="Inline network-object from object-group (synthesized name)",
                        ))
                        members.append(synth_name)
                    elif ctoks[0] == "network-object" and len(ctoks) >= 3:
                        inline_counter += 1
                        synth_name = f"{name}_net{inline_counter}"
                        cidr = _mask_to_cidr(ctoks[2])
                        addresses.append(AddressObject(
                            name=synth_name, type=AddressType.IP_NETMASK, value=f"{ctoks[1]}/{cidr}",
                            origin=ObjectOrigin.CISCO_ASA,
                            description="Inline network-object from object-group (synthesized name)",
                        ))
                        members.append(synth_name)
                    elif ctoks[0] == "group-object" and len(ctoks) >= 2:
                        members.append(ctoks[1])
                    else:
                        self.unsupported("address-group", name, f"Unrecognized group member line: '{child}'")
                groups.append(AddressGroup(name=name, members=members, origin=ObjectOrigin.CISCO_ASA))
        return addresses, groups

    def _parse_network_object_body(self, name: str, children: list[str]) -> AddressObject | None:
        for child in children:
            ctoks = tokens(child)
            if not ctoks:
                continue
            if ctoks[0] == "host" and len(ctoks) >= 2:
                return AddressObject(name=name, type=AddressType.IP_NETMASK, value=f"{ctoks[1]}/32",
                                      origin=ObjectOrigin.CISCO_ASA)
            if ctoks[0] == "subnet" and len(ctoks) >= 3:
                cidr = _mask_to_cidr(ctoks[2])
                return AddressObject(name=name, type=AddressType.IP_NETMASK, value=f"{ctoks[1]}/{cidr}",
                                      origin=ObjectOrigin.CISCO_ASA)
            if ctoks[0] == "range" and len(ctoks) >= 3:
                return AddressObject(name=name, type=AddressType.IP_RANGE, value=f"{ctoks[1]}-{ctoks[2]}",
                                      origin=ObjectOrigin.CISCO_ASA)
            if ctoks[0] == "fqdn":
                # `fqdn v4 example.com` or `fqdn example.com`
                fqdn_val = ctoks[2] if len(ctoks) >= 3 and ctoks[1] in ("v4", "v6") else (ctoks[1] if len(ctoks) >= 2 else None)
                if fqdn_val:
                    return AddressObject(name=name, type=AddressType.FQDN, value=fqdn_val,
                                          origin=ObjectOrigin.CISCO_ASA)
            if ctoks[0] == "description":
                continue  # picked up separately if needed; not fatal to skip
        self.unsupported("address", name, "object network body did not match a recognized host/subnet/range/fqdn form")
        return None

    # ---- Services ---------------------------------------------------------
    def parse_services(self) -> tuple[list[ServiceObject], list[ServiceGroup]]:
        services: list[ServiceObject] = []
        for parent, children in self._groups:
            ptoks = tokens(parent)
            if len(ptoks) >= 3 and ptoks[0] == "object" and ptoks[1] == "service":
                name = ptoks[2]
                svc = self._parse_service_object_body(name, children)
                if svc:
                    services.append(svc)

        groups: list[ServiceGroup] = []
        for parent, children in self._groups:
            ptoks = tokens(parent)
            if len(ptoks) >= 3 and ptoks[0] == "object-group" and ptoks[1] == "service":
                name = ptoks[2]
                header_proto = ptoks[3] if len(ptoks) >= 4 else None
                members: list[str] = []
                inline_counter = 0
                for child in children:
                    ctoks = tokens(child)
                    if not ctoks:
                        continue
                    if ctoks[0] == "group-object" and len(ctoks) >= 2:
                        members.append(ctoks[1])
                    elif ctoks[0] == "service-object" and len(ctoks) >= 2 and ctoks[1] == "object":
                        members.append(ctoks[2])
                    elif ctoks[0] == "service-object" and len(ctoks) >= 2 and ctoks[1] in _PROTO_MAP:
                        inline_counter += 1
                        synth_name = f"{name}_svc{inline_counter}"
                        svc = _parse_port_clause(ctoks[1], ctoks[2:], synth_name)
                        if svc:
                            services.append(svc)
                            members.append(synth_name)
                        else:
                            self.unsupported("service-group", name, f"Unrecognized service-object clause: '{child}'")
                    elif ctoks[0] == "port-object" and header_proto in _PROTO_MAP:
                        inline_counter += 1
                        synth_name = f"{name}_port{inline_counter}"
                        svc = _parse_port_clause(header_proto, ctoks[1:], synth_name)
                        if svc:
                            services.append(svc)
                            members.append(synth_name)
                        else:
                            self.unsupported("service-group", name, f"Unrecognized port-object clause: '{child}'")
                    else:
                        self.unsupported("service-group", name, f"Unrecognized group member line: '{child}'")
                groups.append(ServiceGroup(name=name, members=members, origin=ObjectOrigin.CISCO_ASA))
        return services, groups

    def _parse_service_object_body(self, name: str, children: list[str]) -> ServiceObject | None:
        for child in children:
            ctoks = tokens(child)
            if not ctoks:
                continue
            if ctoks[0] == "service" and len(ctoks) >= 2:
                proto = ctoks[1]
                if proto == "icmp":
                    return ServiceObject(name=name, protocol=ServiceProtocol.ICMP, origin=ObjectOrigin.CISCO_ASA)
                if proto in _PROTO_MAP:
                    svc = _parse_port_clause(proto, ctoks[2:], name)
                    if svc:
                        return svc
        self.unsupported("service", name, "object service body did not match a recognized tcp/udp/icmp form")
        return None

    # ---- Interfaces -----------------------------------------------------------
    def parse_interfaces(self) -> tuple[list[Interface], list[Zone]]:
        interfaces: list[Interface] = []
        mtu_by_nameif: dict[str, int] = {}

        for parent, children in self._groups:
            ptoks = tokens(parent)
            if ptoks and ptoks[0] == "mtu" and len(ptoks) >= 3:
                if ptoks[2].isdigit():
                    mtu_by_nameif[ptoks[1]] = int(ptoks[2])

        for parent, children in self._groups:
            ptoks = tokens(parent)
            if ptoks and ptoks[0] == "interface" and len(ptoks) >= 2:
                hw_name = ptoks[1]
                nameif = ip_addr = mask = description = None
                enabled = True
                for child in children:
                    ctoks = tokens(child)
                    if not ctoks:
                        continue
                    if ctoks[0] == "nameif" and len(ctoks) >= 2:
                        nameif = ctoks[1]
                    elif ctoks[0] == "ip" and len(ctoks) >= 4 and ctoks[1] == "address":
                        ip_addr, mask = ctoks[2], ctoks[3]
                    elif ctoks[0] == "description":
                        description = " ".join(ctoks[1:])
                    elif ctoks[0] == "shutdown":
                        enabled = False

                if nameif:
                    self._nameif_to_ifname[nameif] = hw_name
                else:
                    self.warn("interface", hw_name, "No 'nameif' configured - ACLs/routes can't reference "
                              "this interface by name; using the hardware name as a fallback identifier")

                # `name` is deliberately the nameif (or hw name as fallback) -
                # the SAME identifier ACLs and `route` commands use - so the
                # interface mapping step can rewrite policies/routes/NAT
                # consistently by matching on this field.
                interfaces.append(Interface(
                    name=nameif or hw_name,
                    hardware_name=hw_name,
                    description=description or "",
                    ip_address=ip_addr,
                    netmask=mask,
                    zone=nameif or hw_name,
                    enabled=enabled,
                    mtu=mtu_by_nameif.get(nameif) if nameif else None,
                    origin=ObjectOrigin.CISCO_ASA,
                ))
        return interfaces, self.derive_zones_from_interfaces(interfaces)

    # ---- Routes ------------------------------------------------------------
    def parse_routes(self) -> list[Route]:
        routes: list[Route] = []
        for parent, _children in self._groups:
            ptoks = tokens(parent)
            # route <nameif> <dest> <mask> <nexthop> [metric]
            if ptoks and ptoks[0] == "route" and len(ptoks) >= 5:
                nameif, dest, mask, nexthop = ptoks[1], ptoks[2], ptoks[3], ptoks[4]
                metric = ptoks[5] if len(ptoks) >= 6 and ptoks[5].isdigit() else None
                cidr = _mask_to_cidr(mask)
                routes.append(Route(
                    name=None,
                    destination=f"{dest}/{cidr}",
                    next_hop=nexthop,
                    interface=nameif,
                    metric=int(metric) if metric else None,
                    origin=ObjectOrigin.CISCO_ASA,
                ))
        return routes

    # ---- Policies (best-effort) -------------------------------------------
    def parse_policies(self) -> tuple[list[Policy], list[NATRule]]:
        # Pre-pass: access-group bindings, so ACL entries can approximate a zone.
        for parent, _children in self._groups:
            ptoks = tokens(parent)
            # access-group <acl-name> <in|out> interface <nameif>
            if ptoks and ptoks[0] == "access-group" and len(ptoks) >= 5 and ptoks[3] == "interface":
                self._acl_bindings[ptoks[1]] = (ptoks[2], ptoks[4])

        policies: list[Policy] = []
        nat_rules: list[NATRule] = []
        seq = 0
        for parent, _children in self._groups:
            ptoks = tokens(parent)
            if not (ptoks and ptoks[0] == "access-list" and len(ptoks) >= 4 and ptoks[2] == "extended"):
                continue
            acl_name = ptoks[1]
            action_raw = ptoks[3]
            if action_raw not in ("permit", "deny"):
                self.unsupported("policy", acl_name, f"Unrecognized access-list action '{action_raw}'")
                continue

            rest = ptoks[4:]
            if not rest:
                self.unsupported("policy", acl_name, "access-list line had no protocol/address fields")
                continue

            proto = rest[0]
            seq += 1
            policy_name = f"{acl_name}_{seq}"

            direction_zone = self._acl_bindings.get(acl_name)
            if direction_zone:
                direction, nameif = direction_zone
                src_zone = ["any"] if direction == "in" else [nameif]
                dst_zone = [nameif] if direction == "in" else ["any"]
            else:
                src_zone, dst_zone = ["any"], ["any"]
                self.warn("policy", policy_name,
                          f"No 'access-group' binding found for ACL '{acl_name}' - "
                          f"source/destination zone left as 'any', review manually")

            try:
                src_addr, src_port, dst_addr, dst_port, remainder = _parse_acl_addresses(proto, rest[1:])
            except ValueError as exc:
                self.unsupported("policy", policy_name, f"Could not parse ACL address/port fields: {exc}")
                continue

            service_desc = _service_descriptor(proto, dst_port)

            policies.append(Policy(
                name=policy_name,
                source_zone=src_zone,
                dest_zone=dst_zone,
                source_address=[src_addr],
                dest_address=[dst_addr],
                service=[service_desc],
                action=PolicyAction.ALLOW if action_raw == "permit" else PolicyAction.DENY,
                description=f"Converted from ACL '{acl_name}'",
                origin=ObjectOrigin.CISCO_ASA,
            ))
        # NAT: ASA models this two ways.
        #  1. "Object NAT" nested inside an `object network` block:
        #       object network SERVER01
        #        host 10.10.10.10
        #        nat (inside,outside) static 203.0.113.10
        #  2. "Manual/twice NAT" as a standalone top-level statement:
        #       nat (inside,outside) source dynamic INSIDE_NET interface
        # Both forms name real/mapped interfaces directly, so - same as
        # everything else here - the resulting NATRule keeps those raw
        # interface names for the mapping step to translate into zones.
        for parent, children in self._groups:
            ptoks = tokens(parent)
            if ptoks and ptoks[0] == "object" and len(ptoks) >= 3 and ptoks[1] == "network":
                nat_rule = self._parse_object_nat(ptoks[2], children)
                if nat_rule:
                    nat_rules.append(nat_rule)
            elif ptoks and ptoks[0] == "nat" and len(ptoks) >= 2 and ptoks[1].startswith("("):
                nat_rule = self._parse_manual_nat_line(ptoks)
                if nat_rule:
                    nat_rules.append(nat_rule)
                else:
                    self.unsupported("nat", ptoks[1], f"Unrecognized manual/twice-NAT statement: '{parent}'")
        return policies, nat_rules

    def _parse_object_nat(self, obj_name: str, children: list[str]) -> NATRule | None:
        for child in children:
            ctoks = tokens(child)
            if not ctoks or ctoks[0] != "nat":
                continue
            if len(ctoks) < 3 or not (ctoks[1].startswith("(") and ctoks[1].endswith(")")):
                self.unsupported("nat", obj_name, f"Unrecognized object NAT clause: '{child}'")
                continue
            real_if, mapped_if = ctoks[1][1:-1].split(",")
            kind = ctoks[2]
            if kind == "static" and len(ctoks) >= 4:
                # ASA object NAT `static` is a 1:1, bidirectional NAT (same
                # concept as a FortiGate VIP or Junos static-nat): the
                # mapped address must be reachable from the mapped
                # interface's side and translated back to the real host,
                # in addition to the real host's own outbound traffic being
                # translated to the mapped address. Model this the same
                # way those other vendors' 1:1 NAT is modeled - primarily
                # as the destination-NAT half (the direction that actually
                # lets new inbound sessions reach the host) with a NOTE for
                # the reverse leg - rather than only emitting a one-way
                # source translation, which left inbound traffic to the
                # mapped address completely untranslated (i.e. NAT that
                # looked configured but didn't actually work for anyone
                # trying to reach the published host).
                mapped_ip = ctoks[3]
                return NATRule(
                    name=f"{obj_name}_nat", source_zone=["any"], dest_zone=mapped_if,
                    dest_address=[mapped_ip], translated_dest=obj_name,
                    nat_type="static", nat_method="bidirectional", bidirectional=True,
                    origin=ObjectOrigin.CISCO_ASA,
                )
            if kind == "dynamic" and len(ctoks) >= 4:
                translated = "interface" if ctoks[3] == "interface" else ctoks[3]
                return NATRule(
                    name=f"{obj_name}_nat", source_zone=[real_if], dest_zone=mapped_if,
                    source_address=[obj_name], translated_source=translated,
                    nat_type="dynamic-ip-and-port", origin=ObjectOrigin.CISCO_ASA,
                )
            self.unsupported("nat", obj_name, f"Unrecognized object NAT clause: '{child}'")
        return None

    def _parse_manual_nat_line(self, ptoks: list[str]) -> NATRule | None:
        """`nat (real,mapped) source dynamic|static SRC_OBJ TRANSLATED [destination static DST_OBJ MAPPED]`"""
        if len(ptoks) < 5 or ptoks[2] != "source":
            return None
        real_if, mapped_if = ptoks[1][1:-1].split(",")
        kind, src_obj = ptoks[3], ptoks[4]
        translated = ptoks[5] if len(ptoks) > 5 else None
        if not translated:
            return None

        dest_addr: list[str] = []
        translated_dest = None
        if "destination" in ptoks:
            didx = ptoks.index("destination")
            dtoks = ptoks[didx + 1:]
            if len(dtoks) >= 3 and dtoks[0] == "static":
                dest_addr, translated_dest = [dtoks[1]], dtoks[2]
            else:
                self.unsupported("nat", src_obj, f"Twice-NAT destination clause not recognized: "
                                  f"'{' '.join(dtoks)}' - source NAT still converted, add destination "
                                  f"translation manually")

        if kind == "static" and not dest_addr:
            # Manual (non-twice) `nat ... source static SRC_OBJ TRANSLATED`
            # is, like ASA object NAT, a 1:1 bidirectional NAT - without an
            # explicit twice-NAT "destination static" clause it also
            # implicitly permits inbound traffic to TRANSLATED, translated
            # back to SRC_OBJ. Model it the same way as object NAT's static
            # case: primarily the destination-NAT half (so inbound access
            # to the mapped address is actually translated) plus a NOTE for
            # the reverse leg, instead of only a one-way source translation.
            return NATRule(
                name=f"manual_nat_{src_obj}",
                source_zone=["any"], dest_zone=mapped_if,
                dest_address=[translated], translated_dest=src_obj,
                nat_type="static", nat_method="bidirectional", bidirectional=True,
                origin=ObjectOrigin.CISCO_ASA,
            )

        return NATRule(
            name=f"manual_nat_{src_obj}",
            source_zone=[real_if], dest_zone=mapped_if,
            source_address=[src_obj], dest_address=dest_addr,
            translated_source="interface" if translated == "interface" else translated,
            translated_dest=translated_dest,
            nat_type="dynamic-ip-and-port" if kind == "dynamic" else "static",
            origin=ObjectOrigin.CISCO_ASA,
        )


# --- module-level helpers ------------------------------------------------
def _mask_to_cidr(mask: str) -> str:
    if mask.isdigit():
        return mask
    try:
        octets = [int(o) for o in mask.split(".")]
        return str(sum(bin(o).count("1") for o in octets))
    except (ValueError, AttributeError):
        return mask


def _parse_port_clause(proto: str, clause_tokens: list[str], name: str) -> ServiceObject | None:
    """
    Handles the common forms:
      destination eq 443
      destination range 1000 2000
      eq 443                 (port-object shorthand, no 'destination' keyword)
      range 1000 2000
    """
    t = clause_tokens
    if t and t[0] == "destination":
        t = t[1:]
    if len(t) >= 2 and t[0] == "eq":
        return ServiceObject(name=name, protocol=_PROTO_MAP[proto], dest_port=t[1], origin=ObjectOrigin.CISCO_ASA)
    if len(t) >= 3 and t[0] == "range":
        return ServiceObject(name=name, protocol=_PROTO_MAP[proto], dest_port=f"{t[1]}-{t[2]}", origin=ObjectOrigin.CISCO_ASA)
    return None


def _parse_acl_addresses(proto: str, rest: list[str]) -> tuple[str, str | None, str, str | None, list[str]]:
    """
    Parses the source/dest address (+ optional port) portion of an ACL entry.
    Returns (src_addr, src_port, dst_addr, dst_port, leftover_tokens).
    Raises ValueError on a form we don't recognize (caller converts to an
    'unsupported' issue rather than guessing).
    """
    def take_address(toks: list[str]) -> tuple[str, list[str]]:
        if not toks:
            raise ValueError("expected an address, got end of line")
        if toks[0] in ("any", "any4", "any6"):
            return "any", toks[1:]
        if toks[0] == "host" and len(toks) >= 2:
            return toks[1], toks[2:]
        if toks[0] == "object" and len(toks) >= 2:
            return toks[1], toks[2:]
        if toks[0] == "object-group" and len(toks) >= 2:
            return toks[1], toks[2:]
        if len(toks) >= 2 and _looks_like_ip(toks[0]) and _looks_like_ip(toks[1]):
            cidr = _mask_to_cidr(toks[1])
            return f"{toks[0]}/{cidr}", toks[2:]
        raise ValueError(f"unrecognized address token(s) starting at '{toks[0]}'")

    def take_port(toks: list[str]) -> tuple[str | None, list[str]]:
        if toks and toks[0] == "eq" and len(toks) >= 2:
            return toks[1], toks[2:]
        if toks and toks[0] == "range" and len(toks) >= 3:
            return f"{toks[1]}-{toks[2]}", toks[3:]
        return None, toks

    src_addr, rest = take_address(rest)
    src_port, rest = take_port(rest) if proto in _PROTO_MAP else (None, rest)
    dst_addr, rest = take_address(rest)
    dst_port, rest = take_port(rest) if proto in _PROTO_MAP else (None, rest)
    return src_addr, src_port, dst_addr, dst_port, rest


def _looks_like_ip(token: str) -> bool:
    parts = token.split(".")
    return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def _service_descriptor(proto: str, dst_port: str | None) -> str:
    if proto == "icmp":
        return "icmp"
    if dst_port:
        return f"{proto}/{dst_port}"
    return proto
