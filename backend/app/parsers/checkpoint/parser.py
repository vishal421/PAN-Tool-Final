"""
Check Point Parser
===================
Covers:
  add host / add network / add address-range / add dns-domain -> AddressObject
  add group                                                    -> AddressGroup
  add service-tcp / add service-udp / add service-icmp          -> ServiceObject
  add service-group                                             -> ServiceGroup
  set interface (Gaia clish)                                    -> Interface
  set static-route (Gaia clish)                                 -> Route
  add access-rule                                                -> Policy (best-effort)
  add nat-rule                                                   -> NATRule (best-effort)

Important difference from FortiGate/Cisco: Check Point's Standard policy
layer matches access rules against address objects (host/network/group),
not interfaces or zones - a rule doesn't need to "belong" to an interface
the way a FortiGate policy or Cisco ACL does. So Policy.source_zone /
dest_zone are left as ["any"] here rather than populated with an
interface reference; the interface mapping step still applies to
interfaces/zones/virtual-routers and to NAT rules that reference a
gateway interface, just not to security-rule zone fields for this vendor.
If a site uses R81+ Security Zone objects as literal source/destination
values in a rule, that already comes through correctly as an address-list
entry (Check Point zone objects and network objects share the same
namespace in a rule's source/destination fields).
"""

from __future__ import annotations

from app.normalizer.models import (
    AddressObject, AddressGroup, AddressType,
    ServiceObject, ServiceGroup, ServiceProtocol,
    Interface, Zone, Route, NATRule, Policy, PolicyAction,
    ObjectOrigin,
)
from app.parsers.base import BaseParser
from app.parsers.checkpoint.tokenizer import (
    strip_noise, tokenize_line, parse_mgmt_cli_fields, split_member_list,
)


class CheckPointParser(BaseParser):
    vendor_key = "checkpoint"
    vendor_label = "Check Point"

    def __init__(self, raw_text: str, filename: str = ""):
        super().__init__(raw_text, filename)
        self._lines = strip_noise(raw_text)

    # ---- Addresses ------------------------------------------------------
    def parse_addresses(self) -> tuple[list[AddressObject], list[AddressGroup]]:
        addresses: list[AddressObject] = []
        seen: set[str] = set()

        for line in self._lines:
            tokens = tokenize_line(line)
            if len(tokens) < 2 or tokens[0] != "add":
                continue
            obj_type = tokens[1]
            if obj_type not in ("host", "network", "address-range", "dns-domain"):
                continue

            fields = parse_mgmt_cli_fields(tokens)
            name = (fields.get("name") or [None])[0]
            if not name:
                self.unsupported("address", "<unnamed>", f"'{obj_type}' object has no name field: '{line}'")
                continue
            if name in seen:
                self.warn("address", name, "Duplicate address object name - later definition used")
            seen.add(name)

            comment = (fields.get("comments") or [""])[0]

            if obj_type == "host":
                ip = (fields.get("ip-address") or [None])[0]
                if ip:
                    addresses.append(AddressObject(name=name, type=AddressType.IP_NETMASK, value=f"{ip}/32",
                                                     description=comment, origin=ObjectOrigin.CHECKPOINT))
                else:
                    self.unsupported("address", name, "host object missing ip-address")

            elif obj_type == "network":
                subnet = (fields.get("subnet") or [None])[0]
                mask_len = (fields.get("mask-length") or [None])[0]
                subnet_mask = (fields.get("subnet-mask") or [None])[0]
                if subnet and mask_len:
                    addresses.append(AddressObject(name=name, type=AddressType.IP_NETMASK, value=f"{subnet}/{mask_len}",
                                                     description=comment, origin=ObjectOrigin.CHECKPOINT))
                elif subnet and subnet_mask:
                    cidr = _mask_to_cidr(subnet_mask)
                    addresses.append(AddressObject(name=name, type=AddressType.IP_NETMASK, value=f"{subnet}/{cidr}",
                                                     description=comment, origin=ObjectOrigin.CHECKPOINT))
                else:
                    self.unsupported("address", name, "network object missing subnet/mask-length (or subnet-mask)")

            elif obj_type == "address-range":
                first = (fields.get("ip-address-first") or [None])[0]
                last = (fields.get("ip-address-last") or [None])[0]
                if first and last:
                    addresses.append(AddressObject(name=name, type=AddressType.IP_RANGE, value=f"{first}-{last}",
                                                     description=comment, origin=ObjectOrigin.CHECKPOINT))
                else:
                    self.unsupported("address", name, "address-range object missing ip-address-first/ip-address-last")

            elif obj_type == "dns-domain":
                domain = (fields.get("domain") or [None])[0]
                if not domain:
                    self.unsupported("address", name, "dns-domain object missing 'domain' field")
                elif domain.startswith("."):
                    self.unsupported(
                        "address", name,
                        f"dns-domain object '{domain}' is a wildcard sub-domain match - PAN-OS FQDN "
                        f"address objects require an exact hostname, not a wildcard domain. Recreate "
                        f"as an EDL or a specific FQDN object manually.",
                    )
                else:
                    addresses.append(AddressObject(name=name, type=AddressType.FQDN, value=domain,
                                                     description=comment, origin=ObjectOrigin.CHECKPOINT))

        groups: list[AddressGroup] = []
        for line in self._lines:
            tokens = tokenize_line(line)
            if len(tokens) < 2 or tokens[0] != "add" or tokens[1] != "group":
                continue
            fields = parse_mgmt_cli_fields(tokens)
            name = (fields.get("name") or [None])[0]
            if not name:
                continue
            members = split_member_list(fields.get("members", []))
            comment = (fields.get("comments") or [""])[0]
            groups.append(AddressGroup(name=name, members=members, description=comment,
                                        origin=ObjectOrigin.CHECKPOINT))
        return addresses, groups

    # ---- Services -----------------------------------------------------
    def parse_services(self) -> tuple[list[ServiceObject], list[ServiceGroup]]:
        services: list[ServiceObject] = []
        seen: set[str] = set()

        for line in self._lines:
            tokens = tokenize_line(line)
            if len(tokens) < 2 or tokens[0] != "add":
                continue
            obj_type = tokens[1]
            if obj_type not in ("service-tcp", "service-udp", "service-icmp", "service-sctp"):
                continue

            fields = parse_mgmt_cli_fields(tokens)
            name = (fields.get("name") or [None])[0]
            if not name:
                self.unsupported("service", "<unnamed>", f"'{obj_type}' object has no name field: '{line}'")
                continue
            if name in seen:
                self.warn("service", name, "Duplicate service object name - later definition used")
            seen.add(name)
            comment = (fields.get("comments") or [""])[0]

            if obj_type in ("service-tcp", "service-udp", "service-sctp"):
                proto = {"service-tcp": ServiceProtocol.TCP, "service-udp": ServiceProtocol.UDP,
                          "service-sctp": ServiceProtocol.SCTP}[obj_type]
                port = (fields.get("port") or [None])[0]
                if port:
                    services.append(ServiceObject(name=name, protocol=proto, dest_port=port,
                                                    description=comment, origin=ObjectOrigin.CHECKPOINT))
                else:
                    self.unsupported("service", name, f"{obj_type} object missing 'port' field")
            elif obj_type == "service-icmp":
                icmp_type = (fields.get("icmp-type") or [None])[0]
                services.append(ServiceObject(
                    name=name, protocol=ServiceProtocol.ICMP,
                    icmp_type=int(icmp_type) if icmp_type and icmp_type.isdigit() else None,
                    description=comment, origin=ObjectOrigin.CHECKPOINT,
                ))

        groups: list[ServiceGroup] = []
        for line in self._lines:
            tokens = tokenize_line(line)
            if len(tokens) < 2 or tokens[0] != "add" or tokens[1] != "service-group":
                continue
            fields = parse_mgmt_cli_fields(tokens)
            name = (fields.get("name") or [None])[0]
            if not name:
                continue
            members = split_member_list(fields.get("members", []))
            groups.append(ServiceGroup(name=name, members=members, origin=ObjectOrigin.CHECKPOINT))
        return services, groups

    # ---- Interfaces (Gaia clish) -------------------------------------------
    def parse_interfaces(self) -> tuple[list[Interface], list[Zone]]:
        iface_data: dict[str, dict] = {}

        for line in self._lines:
            tokens = tokenize_line(line)
            if len(tokens) < 3 or tokens[0] != "set" or tokens[1] != "interface":
                continue
            if_name = tokens[2]
            rest = tokens[3:]
            entry = iface_data.setdefault(if_name, {})

            i = 0
            while i < len(rest) - 1:
                key, value = rest[i], rest[i + 1]
                if key == "ipv4-address":
                    entry["ip"] = value
                elif key == "mask-length":
                    entry["mask_length"] = value
                elif key == "comments":
                    entry["comments"] = value
                elif key == "mtu":
                    entry["mtu"] = value
                elif key == "state":
                    entry["state"] = value
                elif key == "security-zone":
                    entry["zone"] = value
                else:
                    self.warn("interface", if_name, f"Unrecognized 'set interface' clause: '{key} {value}' in line: '{line}'")
                i += 2

        interfaces: list[Interface] = []
        for if_name, entry in iface_data.items():
            mask_len = entry.get("mask_length")
            interfaces.append(Interface(
                name=if_name,
                description=entry.get("comments", ""),
                ip_address=entry.get("ip"),
                netmask=mask_len,  # already a CIDR prefix length from Gaia clish - generator handles digit-form directly
                zone=entry.get("zone"),
                mtu=int(entry["mtu"]) if entry.get("mtu", "").isdigit() else None,
                enabled=entry.get("state", "on") != "off",
                origin=ObjectOrigin.CHECKPOINT,
            ))
            if not entry.get("zone"):
                self.warn(
                    "interface", if_name,
                    "No 'security-zone' set for this interface - Check Point's Standard policy "
                    "doesn't require one, so this is only a hint gap for the mapping step, not a "
                    "config error. Assign a zone in the interface mapping step before generating.",
                )
        return interfaces, self.derive_zones_from_interfaces(interfaces)

    # ---- Routes (Gaia clish) ------------------------------------------------
    def parse_routes(self) -> list[Route]:
        routes: list[Route] = []
        for line in self._lines:
            tokens = tokenize_line(line)
            # set static-route <dest>/<prefix> nexthop gateway address <ip> priority <n>
            if len(tokens) < 6 or tokens[0] != "set" or tokens[1] != "static-route":
                continue
            destination = tokens[2]
            try:
                nh_idx = tokens.index("address")
                nexthop = tokens[nh_idx + 1]
            except (ValueError, IndexError):
                self.unsupported("route", destination, f"Could not find nexthop address in: '{line}'")
                continue
            priority = None
            if "priority" in tokens:
                p_idx = tokens.index("priority")
                if p_idx + 1 < len(tokens) and tokens[p_idx + 1].isdigit():
                    priority = int(tokens[p_idx + 1])
            routes.append(Route(
                name=None, destination=destination, next_hop=nexthop,
                metric=priority, origin=ObjectOrigin.CHECKPOINT,
            ))
        return routes

    # ---- Policies + NAT (best-effort) -------------------------------------
    def parse_policies(self) -> tuple[list[Policy], list[NATRule]]:
        policies: list[Policy] = []
        seq = 0
        for line in self._lines:
            tokens = tokenize_line(line)
            if len(tokens) < 2 or tokens[0] != "add" or tokens[1] != "access-rule":
                continue
            fields = parse_mgmt_cli_fields(tokens)
            seq += 1
            name = (fields.get("name") or [f"Rule_{seq}"])[0]

            src = split_member_list(fields.get("source", ["Any"]))
            dst = split_member_list(fields.get("destination", ["Any"]))
            svc = split_member_list(fields.get("service", ["Any"]))
            action_raw = (fields.get("action") or ["Drop"])[0]
            track = (fields.get("track") or [""])[0]
            comment = (fields.get("comments") or [""])[0]
            enabled = (fields.get("enabled") or ["true"])[0].lower() != "false"

            if action_raw == "Accept":
                action = PolicyAction.ALLOW
            elif action_raw == "Reject":
                action = PolicyAction.RESET
            else:
                action = PolicyAction.DROP if action_raw == "Drop" else PolicyAction.DENY

            # See module docstring: Check Point Standard-layer rules match on
            # address objects, not interfaces/zones, so no zone translation
            # is needed here - "any" is correct, not a placeholder guess.
            policies.append(Policy(
                name=name,
                source_zone=["any"], dest_zone=["any"],
                source_address=src, dest_address=dst, service=svc,
                action=action,
                log_end=bool(track) and track != "None",
                description=comment,
                disabled=not enabled,
                origin=ObjectOrigin.CHECKPOINT,
            ))

        nat_rules: list[NATRule] = []
        n_seq = 0
        for line in self._lines:
            tokens = tokenize_line(line)
            if len(tokens) < 2 or tokens[0] != "add" or tokens[1] != "nat-rule":
                continue
            fields = parse_mgmt_cli_fields(tokens)
            n_seq += 1
            method = (fields.get("method") or [None])[0]
            orig_src = (fields.get("original-source") or ["Any"])[0]
            orig_dst = (fields.get("original-destination") or ["Any"])[0]
            translated_src = (fields.get("translated-source") or [None])[0]
            translated_dst = (fields.get("translated-destination") or [None])[0]
            hide_behind = (fields.get("hide-behind") or [None])[0]

            if method == "hide":
                if hide_behind == "gateway":
                    # Hide-NAT-behind-gateway auto-selects the outbound
                    # interface via routing - there's no explicit interface
                    # token to resolve through the mapping table, so this
                    # stays as the generic 'interface' marker (the generator
                    # already emits a manual-review TODO when it can't
                    # resolve a specific mapped interface for it).
                    nat_rules.append(NATRule(
                        name=f"nat_hide_{n_seq}", source_address=[orig_src], dest_address=[orig_dst],
                        translated_source="interface", nat_type="dynamic-ip-and-port",
                        origin=ObjectOrigin.CHECKPOINT,
                    ))
                elif hide_behind:
                    nat_rules.append(NATRule(
                        name=f"nat_hide_{n_seq}", source_address=[orig_src], dest_address=[orig_dst],
                        translated_source=hide_behind, nat_type="dynamic-ip-and-port",
                        origin=ObjectOrigin.CHECKPOINT,
                    ))
                else:
                    self.unsupported("nat", f"nat_hide_{n_seq}", f"hide NAT rule missing 'hide-behind': '{line}'")
            elif method == "static":
                if translated_src:
                    # Check Point static NAT is automatically bidirectional:
                    # the gateway both translates the host's outbound
                    # traffic to translated_src AND accepts inbound traffic
                    # addressed to translated_src, translating it back to
                    # the real host (orig_src) - same concept as a
                    # FortiGate VIP or Junos static-nat. Model this the same
                    # way as those vendors' 1:1 NAT - primarily as the
                    # destination-NAT half (the direction that actually
                    # lets new inbound sessions reach the host) with a NOTE
                    # for the reverse leg, rather than only emitting a
                    # one-way source translation, which left inbound
                    # traffic to translated_src completely untranslated.
                    nat_rules.append(NATRule(
                        name=f"nat_static_{n_seq}", dest_address=[translated_src],
                        translated_dest=orig_src, nat_type="static",
                        nat_method="bidirectional", bidirectional=True,
                        origin=ObjectOrigin.CHECKPOINT,
                    ))
                elif translated_dst:
                    nat_rules.append(NATRule(
                        name=f"nat_static_{n_seq}", source_address=[orig_src], dest_address=[orig_dst],
                        translated_dest=translated_dst, nat_type="static",
                        origin=ObjectOrigin.CHECKPOINT,
                    ))
                else:
                    self.unsupported("nat", f"nat_static_{n_seq}",
                                      f"static NAT rule has neither translated-source nor "
                                      f"translated-destination: '{line}'")
            else:
                self.unsupported("nat", f"nat_{n_seq}", f"Unrecognized NAT method '{method}': '{line}'")

        return policies, nat_rules


def _mask_to_cidr(mask: str) -> str:
    if mask.isdigit():
        return mask
    try:
        octets = [int(o) for o in mask.split(".")]
        return str(sum(bin(o).count("1") for o in octets))
    except (ValueError, AttributeError):
        return mask
