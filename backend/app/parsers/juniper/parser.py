"""
Juniper SRX Parser
==================
Parses a Junos "set"-style configuration export (`show configuration |
display set`), i.e. a flat list of fully-qualified `set ...` statements
rather than the nested `{ }` hierarchical format. This is the most
portable Junos export format and the one most migration tooling expects.

Covers:
  security address-book global address/address-set  -> AddressObject / AddressGroup
  applications application/application-set            -> ServiceObject / ServiceGroup
  interfaces <phys> unit <unit> family inet address    -> Interface
  security zones security-zone <zone> interfaces       -> Zone
  routing-options static route                          -> Route
  security policies from-zone/to-zone/policy             -> Policy
  security nat source/static/destination rule-sets        -> NATRule
  system radius-server / tacplus-server / access profile (ldap) / snmp /
  syslog host / ntp server / name-server / domain-name    -> system profiles

Anything outside the above (routing protocols, IPS/UTM policy, chassis
config, etc.) is out of scope for a firewall rule/object migration and is
not visited or flagged.
"""

from __future__ import annotations

from app.normalizer.models import (
    AddressObject, AddressGroup, AddressType,
    ServiceObject, ServiceGroup, ServiceProtocol,
    Interface, Zone, Route, NATRule, Policy, PolicyAction,
    ObjectOrigin,
    LdapServerProfile, RadiusServerProfile, TacacsServerProfile,
    SnmpProfile, SnmpUser, SyslogServerProfile, NtpProfile, DnsProfile,
)
from app.parsers.base import BaseParser
from app.parsers.juniper.tokenizer import strip_noise, set_lines, match_prefix

_PROTO_MAP = {"tcp": ServiceProtocol.TCP, "udp": ServiceProtocol.UDP, "sctp": ServiceProtocol.SCTP}


def _is_host_mask(mask: str) -> bool:
    return mask in ("32", "128")


class JuniperSRXParser(BaseParser):
    vendor_key = "juniper_srx"
    vendor_label = "Juniper SRX"

    def __init__(self, raw_text: str, filename: str = ""):
        super().__init__(raw_text, filename)
        self._lines = strip_noise(raw_text)
        self._set_lines = set_lines(self._lines)
        # A meaningful Junos "set"-style export is dominated by `set ...`
        # lines; if barely any are present this probably isn't a Junos set
        # export at all (e.g. someone uploaded the hierarchical/braces
        # format, or an unrelated file).
        if self._lines and len(self._set_lines) < max(1, len(self._lines) // 4):
            self.error(
                "document", filename or "<upload>",
                "This doesn't look like a Junos 'set'-style configuration export "
                "(expected mostly 'set ...' lines). Export with "
                "'show configuration | display set' and try again.",
            )

    # ---- Addresses --------------------------------------------------
    def parse_addresses(self) -> tuple[list[AddressObject], list[AddressGroup]]:
        addresses: dict[str, AddressObject] = {}
        groups: dict[str, AddressGroup] = {}
        group_members: dict[str, list[str]] = {}

        for toks in self._set_lines:
            rest = match_prefix(toks, ["security", "address-book", "global", "address-set"])
            if rest and len(rest) >= 3 and rest[1] == "address":
                gname, member = rest[0], rest[2]
                group_members.setdefault(gname, [])
                if member not in group_members[gname]:
                    group_members[gname].append(member)
                continue

            rest = match_prefix(toks, ["security", "address-book", "global", "address"])
            if rest and len(rest) >= 2:
                name, value = rest[0], rest[1]
                if name in addresses:
                    continue
                if rest[1] == "dns-name" and len(rest) >= 3:
                    addresses[name] = AddressObject(
                        name=name, type=AddressType.FQDN, value=rest[2], origin=ObjectOrigin.JUNIPER_SRX,
                    )
                elif "/" in value:
                    ip, mask = value.split("/", 1)
                    atype = AddressType.IP_NETMASK if not _is_host_mask(mask) else AddressType.IP_NETMASK
                    addresses[name] = AddressObject(
                        name=name, type=atype, value=value, origin=ObjectOrigin.JUNIPER_SRX,
                    )
                else:
                    self.unsupported("addresses", name, f"Unrecognized address value format: '{value}'")

        for gname, members in group_members.items():
            groups[gname] = AddressGroup(name=gname, members=members, origin=ObjectOrigin.JUNIPER_SRX)

        return list(addresses.values()), list(groups.values())

    # ---- Services ------------------------------------------------------
    def parse_services(self) -> tuple[list[ServiceObject], list[ServiceGroup]]:
        services: dict[str, dict] = {}
        groups: dict[str, list[str]] = {}

        for toks in self._set_lines:
            rest = match_prefix(toks, ["applications", "application-set"])
            if rest and len(rest) >= 3 and rest[1] == "application":
                gname, member = rest[0], rest[2]
                groups.setdefault(gname, [])
                if member not in groups[gname]:
                    groups[gname].append(member)
                continue

            rest = match_prefix(toks, ["applications", "application"])
            if rest and len(rest) >= 2:
                name = rest[0]
                svc = services.setdefault(name, {"protocol": None, "port": None})
                if rest[1] == "protocol" and len(rest) >= 3:
                    svc["protocol"] = rest[2].lower()
                elif rest[1] == "destination-port" and len(rest) >= 3:
                    svc["port"] = rest[2]

        service_objs: list[ServiceObject] = []
        for name, svc in services.items():
            proto = _PROTO_MAP.get(svc["protocol"] or "")
            if proto is None:
                self.unsupported("services", name, f"Unsupported/missing protocol '{svc['protocol']}' - skipped")
                continue
            service_objs.append(ServiceObject(
                name=name, protocol=proto, dest_port=svc["port"], origin=ObjectOrigin.JUNIPER_SRX,
            ))

        group_objs = [ServiceGroup(name=g, members=m, origin=ObjectOrigin.JUNIPER_SRX) for g, m in groups.items()]
        return service_objs, group_objs

    # ---- Interfaces & Zones --------------------------------------------
    def parse_interfaces(self) -> tuple[list[Interface], list[Zone]]:
        interfaces: dict[str, Interface] = {}
        zone_members: dict[str, list[str]] = {}

        for toks in self._set_lines:
            rest = match_prefix(toks, ["interfaces"])
            if rest and len(rest) >= 6 and rest[1] == "unit" and rest[3] == "family" and rest[4] == "inet" and rest[5] == "address":
                phys, unit, addr = rest[0], rest[2], rest[6] if len(rest) > 6 else None
                if not addr:
                    continue
                full_name = f"{phys}.{unit}"
                ip_part, _, mask_part = addr.partition("/")
                interfaces[full_name] = Interface(
                    name=full_name, ip_address=ip_part, netmask=mask_part or None,
                    origin=ObjectOrigin.JUNIPER_SRX,
                )
                continue

            rest = match_prefix(toks, ["security", "zones", "security-zone"])
            if rest and len(rest) >= 2 and rest[1] == "interfaces":
                zone, iface = rest[0], rest[2] if len(rest) > 2 else None
                if iface:
                    zone_members.setdefault(zone, [])
                    if iface not in zone_members[zone]:
                        zone_members[zone].append(iface)

        zones = [Zone(name=z, interfaces=members, origin=ObjectOrigin.JUNIPER_SRX) for z, members in zone_members.items()]
        # Interfaces inherit their zone from whichever zone claims them, purely as a mapping-step hint.
        for zone, members in zone_members.items():
            for m in members:
                if m in interfaces:
                    interfaces[m].zone = zone
        return list(interfaces.values()), zones

    # ---- Routes ----------------------------------------------------------
    def parse_routes(self) -> list[Route]:
        routes: list[Route] = []
        for toks in self._set_lines:
            rest = match_prefix(toks, ["routing-options", "static", "route"])
            if rest and len(rest) >= 3 and rest[1] == "next-hop":
                routes.append(Route(
                    name=None, destination=rest[0], next_hop=rest[2], origin=ObjectOrigin.JUNIPER_SRX,
                ))
        return routes

    # ---- Policies + NAT ----------------------------------------------------
    def parse_policies(self) -> tuple[list[Policy], list[NATRule]]:
        policies = self._parse_security_policies()
        nat_rules = self._parse_nat()
        return policies, nat_rules

    def _parse_security_policies(self) -> list[Policy]:
        # Keyed by (from_zone, to_zone, policy_name) so fields accumulate
        # across however many `set ... match/then ...` lines define them.
        raw: dict[tuple[str, str, str], dict] = {}
        order: list[tuple[str, str, str]] = []

        for toks in self._set_lines:
            rest = match_prefix(toks, ["security", "policies", "from-zone"])
            if not rest or len(rest) < 4 or rest[1] != "to-zone" or rest[3] != "policy":
                continue
            from_zone, to_zone, policy_name = rest[0], rest[2], rest[4]
            key = (from_zone, to_zone, policy_name)
            if key not in raw:
                raw[key] = {
                    "source_address": [], "dest_address": [], "application": [],
                    "action": None, "disabled": False, "logged": False,
                }
                order.append(key)
            p = raw[key]
            body = rest[5:]
            if not body:
                continue
            if body[0] == "match" and len(body) >= 3:
                field, value = body[1], body[2]
                if field == "source-address":
                    p["source_address"].append(value)
                elif field == "destination-address":
                    p["dest_address"].append(value)
                elif field == "application":
                    p["application"].append(value)
            elif body[0] == "then" and len(body) >= 2:
                if body[1] in ("permit", "deny", "reject"):
                    p["action"] = body[1]
                elif body[1] == "log":
                    p["logged"] = True
            elif body[0] == "deactivate":
                p["disabled"] = True

        policies: list[Policy] = []
        for key in order:
            from_zone, to_zone, name = key
            p = raw[key]
            action = {"permit": PolicyAction.ALLOW, "reject": PolicyAction.DENY}.get(p["action"], PolicyAction.DENY)
            policies.append(Policy(
                name=name,
                source_zone=[from_zone],
                dest_zone=[to_zone],
                source_address=p["source_address"] or ["any"],
                dest_address=p["dest_address"] or ["any"],
                application=p["application"] or ["any"],
                action=action,
                log_end=p["logged"],
                disabled=p["disabled"],
                origin=ObjectOrigin.JUNIPER_SRX,
            ))
        return policies

    def _parse_nat(self) -> list[NATRule]:
        source_pools: dict[str, str] = {}
        dest_pools: dict[str, tuple[str, str | None]] = {}
        source_rs: dict[str, dict] = {}
        static_rs: dict[str, dict] = {}
        dest_rs: dict[str, dict] = {}

        for toks in self._set_lines:
            # --- pools ---
            rest = match_prefix(toks, ["security", "nat", "source", "pool"])
            if rest and len(rest) >= 3 and rest[1] == "address":
                source_pools[rest[0]] = rest[2]
                continue
            rest = match_prefix(toks, ["security", "nat", "destination", "pool"])
            if rest and len(rest) >= 3 and rest[1] == "address":
                port = None
                if len(rest) >= 5 and rest[3] == "port":
                    port = rest[4]
                dest_pools[rest[0]] = (rest[2], port)
                continue

            # --- source NAT rule-set ---
            rest = match_prefix(toks, ["security", "nat", "source", "rule-set"])
            if rest:
                rs_name = rest[0]
                rs = source_rs.setdefault(rs_name, {"from_zone": None, "to_zone": None, "rules": {}})
                body = rest[1:]
                if len(body) >= 2 and body[0] == "from" and body[1] == "zone":
                    rs["from_zone"] = body[2] if len(body) > 2 else None
                elif len(body) >= 2 and body[0] == "to" and body[1] == "zone":
                    rs["to_zone"] = body[2] if len(body) > 2 else None
                elif body and body[0] == "rule" and len(body) >= 2:
                    rule_name = body[1]
                    rule = rs["rules"].setdefault(rule_name, {"match_src": [], "match_dst": [], "then": None})
                    rbody = body[2:]
                    if rbody and rbody[0] == "match" and len(rbody) >= 3:
                        if rbody[1] == "source-address":
                            rule["match_src"].append(rbody[2])
                        elif rbody[1] == "destination-address":
                            rule["match_dst"].append(rbody[2])
                    elif rbody and rbody[0] == "then" and len(rbody) >= 2 and rbody[1] == "source-nat":
                        if len(rbody) >= 3 and rbody[2] == "interface":
                            rule["then"] = "interface"
                        elif len(rbody) >= 4 and rbody[2] == "pool":
                            rule["then"] = f"pool:{rbody[3]}"
                continue

            # --- static NAT rule-set (Junos static-nat is inherently bidirectional/1:1) ---
            rest = match_prefix(toks, ["security", "nat", "static", "rule-set"])
            if rest:
                rs_name = rest[0]
                rs = static_rs.setdefault(rs_name, {"from_zone": None, "rules": {}})
                body = rest[1:]
                if len(body) >= 2 and body[0] == "from" and body[1] == "zone":
                    rs["from_zone"] = body[2] if len(body) > 2 else None
                elif body and body[0] == "rule" and len(body) >= 2:
                    rule_name = body[1]
                    rule = rs["rules"].setdefault(rule_name, {
                        "match_dst": None, "match_port": None, "prefix": None, "mapped_port": None,
                    })
                    rbody = body[2:]
                    if rbody and rbody[0] == "match" and len(rbody) >= 3:
                        if rbody[1] == "destination-address":
                            rule["match_dst"] = rbody[2]
                        elif rbody[1] == "destination-port":
                            rule["match_port"] = rbody[2]
                    elif rbody and rbody[0] == "then" and len(rbody) >= 3 and rbody[1] == "static-nat":
                        if rbody[2] == "prefix" and len(rbody) >= 4:
                            rule["prefix"] = rbody[3]
                            if len(rbody) >= 6 and rbody[4] == "mapped-port":
                                rule["mapped_port"] = rbody[5]
                continue

            # --- destination NAT rule-set ---
            rest = match_prefix(toks, ["security", "nat", "destination", "rule-set"])
            if rest:
                rs_name = rest[0]
                rs = dest_rs.setdefault(rs_name, {"from_zone": None, "rules": {}})
                body = rest[1:]
                if len(body) >= 2 and body[0] == "from" and body[1] == "zone":
                    rs["from_zone"] = body[2] if len(body) > 2 else None
                elif body and body[0] == "rule" and len(body) >= 2:
                    rule_name = body[1]
                    rule = rs["rules"].setdefault(rule_name, {"match_dst": None, "match_port": None, "pool": None})
                    rbody = body[2:]
                    if rbody and rbody[0] == "match" and len(rbody) >= 3:
                        if rbody[1] == "destination-address":
                            rule["match_dst"] = rbody[2]
                        elif rbody[1] == "destination-port":
                            rule["match_port"] = rbody[2]
                    elif rbody and rbody[0] == "then" and len(rbody) >= 3 and rbody[1] == "destination-nat" and rbody[2] == "pool":
                        rule["pool"] = rbody[3] if len(rbody) > 3 else None

        nat_rules: list[NATRule] = []

        # Source NAT (dynamic - interface PAT, or a translated pool = static-ip/dynamic-ip)
        for rs_name, rs in source_rs.items():
            for rule_name, rule in rs["rules"].items():
                if not rule["then"]:
                    self.unsupported("nat", rule_name, f"Source NAT rule '{rule_name}' in rule-set "
                                       f"'{rs_name}' has no 'then source-nat ...' action - skipped")
                    continue
                if rule["then"] == "interface":
                    nat_rules.append(NATRule(
                        name=rule_name,
                        source_zone=[rs["from_zone"]] if rs["from_zone"] else ["any"],
                        dest_zone=rs["to_zone"] or "any",
                        source_address=rule["match_src"] or ["any"],
                        dest_address=rule["match_dst"] or ["any"],
                        translated_source="interface",
                        nat_type="dynamic-ip-and-port",
                        nat_method="source",
                        interface_based=True,
                        origin=ObjectOrigin.JUNIPER_SRX,
                    ))
                else:
                    pool_name = rule["then"].split(":", 1)[1]
                    pool_addr = source_pools.get(pool_name)
                    if not pool_addr:
                        self.unsupported("nat", rule_name, f"Source NAT rule references pool "
                                           f"'{pool_name}' which was not found - skipped")
                        continue
                    nat_rules.append(NATRule(
                        name=rule_name,
                        source_zone=[rs["from_zone"]] if rs["from_zone"] else ["any"],
                        dest_zone=rs["to_zone"] or "any",
                        source_address=rule["match_src"] or ["any"],
                        dest_address=rule["match_dst"] or ["any"],
                        translated_source=pool_addr,
                        nat_type="dynamic-ip-and-port",
                        nat_method="source",
                        origin=ObjectOrigin.JUNIPER_SRX,
                    ))

        # Static NAT (1:1, bidirectional by nature in Junos)
        for rs_name, rs in static_rs.items():
            for rule_name, rule in rs["rules"].items():
                if not rule["match_dst"] or not rule["prefix"]:
                    self.unsupported("nat", rule_name, f"Static NAT rule '{rule_name}' in rule-set "
                                       f"'{rs_name}' is missing destination-address or translated prefix - skipped")
                    continue
                nat_rule = NATRule(
                    name=rule_name,
                    source_zone=["any"],
                    dest_zone=rs["from_zone"] or "any",
                    dest_address=[rule["match_dst"]],
                    translated_dest=rule["prefix"].split("/")[0],
                    nat_type="static",
                    nat_method="bidirectional",
                    bidirectional=True,
                    origin=ObjectOrigin.JUNIPER_SRX,
                )
                if rule["match_port"] and rule["mapped_port"]:
                    nat_rule.original_port = rule["match_port"]
                    nat_rule.translated_port = rule["mapped_port"]
                elif rule["match_port"] or rule["mapped_port"]:
                    self.unsupported("nat", rule_name, "Static NAT rule has a partial port-forwarding "
                                       "translation (only one of match/mapped port set) - review manually")
                nat_rules.append(nat_rule)

        # Destination NAT
        for rs_name, rs in dest_rs.items():
            for rule_name, rule in rs["rules"].items():
                if not rule["match_dst"] or not rule["pool"]:
                    self.unsupported("nat", rule_name, f"Destination NAT rule '{rule_name}' in rule-set "
                                       f"'{rs_name}' is missing destination-address match or a pool - skipped")
                    continue
                pool = dest_pools.get(rule["pool"])
                if not pool:
                    self.unsupported("nat", rule_name, f"Destination NAT rule references pool "
                                       f"'{rule['pool']}' which was not found - skipped")
                    continue
                pool_addr, pool_port = pool
                nat_rule = NATRule(
                    name=rule_name,
                    source_zone=["any"],
                    dest_zone=rs["from_zone"] or "any",
                    dest_address=[rule["match_dst"]],
                    translated_dest=pool_addr.split("/")[0],
                    nat_type="static",
                    nat_method="destination",
                    origin=ObjectOrigin.JUNIPER_SRX,
                )
                if rule["match_port"] and pool_port:
                    nat_rule.original_port = rule["match_port"]
                    nat_rule.translated_port = pool_port
                nat_rules.append(nat_rule)

        return nat_rules

    # ---- System / Auth / Logging Profiles --------------------------------
    def parse_system_profiles(self) -> dict:
        return {
            "ldap_profiles": self._parse_ldap(),
            "radius_profiles": self._parse_radius(),
            "tacacs_profiles": self._parse_tacacs(),
            "snmp_profiles": self._parse_snmp(),
            "syslog_profiles": self._parse_syslog(),
            "ntp_profiles": self._parse_ntp(),
            "dns_profiles": self._parse_dns(),
        }

    def _parse_ldap(self) -> list[LdapServerProfile]:
        profiles: dict[str, dict] = {}
        for toks in self._set_lines:
            rest = match_prefix(toks, ["access", "profile"])
            if not rest or len(rest) < 2:
                continue
            name, body = rest[0], rest[1:]
            p = profiles.setdefault(name, {"servers": [], "base_dn": ""})
            if body[0] == "ldap-server" and len(body) >= 2:
                p["servers"].append(body[1])
            elif body[0] == "ldap-options" and len(body) >= 3 and body[1] == "base-distinguished-name":
                p["base_dn"] = body[2]

        result = []
        for name, p in profiles.items():
            if not p["servers"]:
                continue
            result.append(LdapServerProfile(
                name=name, servers=p["servers"], base_dn=p["base_dn"],
                ssl_mode="none", origin=ObjectOrigin.JUNIPER_SRX,
            ))
        return result

    def _parse_radius(self) -> list[RadiusServerProfile]:
        servers: dict[str, dict] = {}
        for toks in self._set_lines:
            rest = match_prefix(toks, ["system", "radius-server"])
            if not rest or len(rest) < 2:
                continue
            ip, body = rest[0], rest[1:]
            s = servers.setdefault(ip, {"secret": None, "port": None, "timeout": None, "retries": None})
            if body[0] == "secret" and len(body) >= 2:
                s["secret"] = body[1]
            elif body[0] == "port" and len(body) >= 2:
                s["port"] = body[1]
            elif body[0] == "timeout" and len(body) >= 2:
                s["timeout"] = body[1]
            elif body[0] == "retry" and len(body) >= 2:
                s["retries"] = body[1]

        if not servers:
            return []
        # Junos configures RADIUS servers individually (not grouped into a
        # named profile) - represent them as one aggregate profile, similar
        # to how PAN-OS expects one server-profile with multiple servers.
        server_list = list(servers.keys())
        first = next(iter(servers.values()))
        return [RadiusServerProfile(
            name="radius-servers",
            servers=server_list,
            shared_secret="********" if first["secret"] else None,
            timeout=int(first["timeout"]) if first["timeout"] and first["timeout"].isdigit() else None,
            retries=int(first["retries"]) if first["retries"] and first["retries"].isdigit() else None,
            auth_port=int(first["port"]) if first["port"] and first["port"].isdigit() else None,
            origin=ObjectOrigin.JUNIPER_SRX,
        )]

    def _parse_tacacs(self) -> list[TacacsServerProfile]:
        servers: dict[str, dict] = {}
        for toks in self._set_lines:
            rest = match_prefix(toks, ["system", "tacplus-server"])
            if not rest or len(rest) < 2:
                continue
            ip, body = rest[0], rest[1:]
            s = servers.setdefault(ip, {"secret": None, "port": None, "timeout": None})
            if body[0] == "secret" and len(body) >= 2:
                s["secret"] = body[1]
            elif body[0] == "port" and len(body) >= 2:
                s["port"] = body[1]
            elif body[0] == "timeout" and len(body) >= 2:
                s["timeout"] = body[1]

        if not servers:
            return []
        server_list = list(servers.keys())
        first = next(iter(servers.values()))
        return [TacacsServerProfile(
            name="tacacs-servers",
            servers=server_list,
            shared_secret="********" if first["secret"] else None,
            timeout=int(first["timeout"]) if first["timeout"] and first["timeout"].isdigit() else None,
            origin=ObjectOrigin.JUNIPER_SRX,
        )]

    def _parse_snmp(self) -> list[SnmpProfile]:
        contact, location = "", ""
        community = None
        trap_targets: list[str] = []
        v3_users: dict[str, dict] = {}

        for toks in self._set_lines:
            rest = match_prefix(toks, ["snmp"])
            if not rest:
                continue
            if rest[0] == "contact" and len(rest) >= 2:
                contact = rest[1]
            elif rest[0] == "location" and len(rest) >= 2:
                location = rest[1]
            elif rest[0] == "community" and len(rest) >= 2:
                community = rest[1]
            elif rest[0] == "trap-group" and len(rest) >= 4 and rest[2] == "targets":
                trap_targets.append(rest[3])
            elif rest[0] == "v3" and len(rest) >= 6 and rest[1] == "usm" and rest[3] == "user":
                uname, ufield = rest[4], rest[5:]
                u = v3_users.setdefault(uname, {"auth": None, "priv": None})
                if ufield and ufield[0].startswith("authentication-"):
                    u["auth"] = ufield[0].replace("authentication-", "")
                elif ufield and ufield[0].startswith("privacy-"):
                    u["priv"] = ufield[0].replace("privacy-", "")

        profiles: list[SnmpProfile] = []
        if community:
            profiles.append(SnmpProfile(
                name="snmp-v2c", version="v2c", community="********",
                trap_destinations=trap_targets, contact=contact, location=location,
                origin=ObjectOrigin.JUNIPER_SRX,
            ))
        if v3_users:
            users = [SnmpUser(
                name=n, auth_protocol=u["auth"], auth_password="********" if u["auth"] else None,
                priv_protocol=u["priv"], priv_password="********" if u["priv"] else None,
            ) for n, u in v3_users.items()]
            profiles.append(SnmpProfile(
                name="snmp-v3", version="v3", users=users,
                trap_destinations=trap_targets if not community else [],
                contact=contact, location=location, origin=ObjectOrigin.JUNIPER_SRX,
            ))
        if not profiles and (contact or location):
            profiles.append(SnmpProfile(name="snmp-default", contact=contact, location=location, origin=ObjectOrigin.JUNIPER_SRX))
        return profiles

    def _parse_syslog(self) -> list[SyslogServerProfile]:
        hosts: dict[str, dict] = {}
        for toks in self._set_lines:
            rest = match_prefix(toks, ["system", "syslog", "host"])
            if not rest or len(rest) < 2:
                continue
            ip, body = rest[0], rest[1:]
            h = hosts.setdefault(ip, {"port": 514, "facility": "LOG_USER", "structured": False})
            if body[0] == "port" and len(body) >= 2:
                h["port"] = body[1]
            elif body[0] == "facility-override" and len(body) >= 2:
                h["facility"] = body[1]
            elif body[0] == "structured-data":
                h["structured"] = True

        profiles = []
        for ip, h in hosts.items():
            facility = h["facility"]
            facility = facility if facility.upper().startswith("LOG_") else f"LOG_{facility.upper()}"
            profiles.append(SyslogServerProfile(
                name=f"syslog-{ip.replace('.', '-')}",
                server=ip,
                port=int(h["port"]) if str(h["port"]).isdigit() else 514,
                transport="UDP",
                facility=facility,
                log_format="IETF" if h["structured"] else "BSD",
                origin=ObjectOrigin.JUNIPER_SRX,
            ))
        return profiles

    def _parse_ntp(self) -> list[NtpProfile]:
        servers: list[str] = []
        auth = False
        timezone = None
        for toks in self._set_lines:
            rest = match_prefix(toks, ["system", "ntp", "server"])
            if rest and rest[0] not in servers:
                servers.append(rest[0])
                continue
            rest = match_prefix(toks, ["system", "ntp", "authentication-key"])
            if rest:
                auth = True
                continue
            rest = match_prefix(toks, ["system", "time-zone"])
            if rest:
                timezone = rest[0]

        if not servers:
            return []
        return [NtpProfile(
            primary_server=servers[0],
            secondary_server=servers[1] if len(servers) > 1 else None,
            authentication=auth,
            timezone=timezone,
            origin=ObjectOrigin.JUNIPER_SRX,
        )]

    def _parse_dns(self) -> list[DnsProfile]:
        servers: list[str] = []
        domain = None
        search = None
        for toks in self._set_lines:
            rest = match_prefix(toks, ["system", "name-server"])
            if rest and rest[0] not in servers:
                servers.append(rest[0])
                continue
            rest = match_prefix(toks, ["system", "domain-name"])
            if rest:
                domain = rest[0]
                continue
            rest = match_prefix(toks, ["system", "domain-search"])
            if rest:
                search = rest[0]

        if not servers and not domain:
            return []
        return [DnsProfile(
            primary_dns=servers[0] if len(servers) > 0 else None,
            secondary_dns=servers[1] if len(servers) > 1 else None,
            domain_name=domain,
            search_domain=search,
            origin=ObjectOrigin.JUNIPER_SRX,
        )]
