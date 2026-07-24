"""
FortiGate Parser
================
Covers:
  config firewall address        -> AddressObject
  config firewall addrgrp        -> AddressGroup
  config firewall service custom -> ServiceObject
  config firewall service group  -> ServiceGroup
  config system interface        -> Interface
  config system zone             -> Zone (+ interface->zone mapping)
  config router static            -> Route
  config firewall policy          -> Policy (best-effort)

Anything not covered by a known `type`/field combination is reported via
`self.unsupported(...)` rather than guessed at.
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
from app.parsers.fortigate.tokenizer import (
    strip_noise, extract_top_config_block, extract_edit_entries, extract_flat_fields,
)


class FortiGateParser(BaseParser):
    vendor_key = "fortigate"
    vendor_label = "FortiGate"

    def __init__(self, raw_text: str, filename: str = ""):
        super().__init__(raw_text, filename)
        self._lines = strip_noise(raw_text)
        self._seen_address_names: set[str] = set()
        self._seen_service_names: set[str] = set()
        # interface -> zone name, populated by parse_interfaces() and reused by parse_policies()
        self._iface_zone_map: dict[str, str] = {}

    # ---- Addresses ----------------------------------------------------
    def parse_addresses(self) -> tuple[list[AddressObject], list[AddressGroup]]:
        addresses: list[AddressObject] = []
        block = extract_top_config_block(self._lines, "firewall address")
        for name, fields, _nested in extract_edit_entries(block):
            if name in self._seen_address_names:
                self.warn("address", name, "Duplicate address object name - later definition used")
            self._seen_address_names.add(name)

            addr_type = (fields.get("type", ["ipmask"]) or ["ipmask"])[0]
            comment = " ".join(fields.get("comment", []))

            if addr_type in ("ipmask", "geography") and "subnet" in fields:
                # `set subnet <ip> <mask>` - FortiGate default address type
                subnet_vals = fields["subnet"]
                if len(subnet_vals) >= 2:
                    ip, mask = subnet_vals[0], subnet_vals[1]
                    addresses.append(AddressObject(
                        name=name, type=AddressType.IP_NETMASK,
                        value=f"{ip}/{_mask_to_cidr(mask)}",
                        description=comment, origin=ObjectOrigin.FORTIGATE,
                    ))
                else:
                    self.unsupported("address", name, "Malformed 'subnet' field - could not parse ip/mask")
            elif addr_type == "iprange":
                start = (fields.get("start-ip") or [None])[0]
                end = (fields.get("end-ip") or [None])[0]
                if start and end:
                    addresses.append(AddressObject(
                        name=name, type=AddressType.IP_RANGE, value=f"{start}-{end}",
                        description=comment, origin=ObjectOrigin.FORTIGATE,
                    ))
                else:
                    self.unsupported("address", name, "iprange type missing start-ip/end-ip")
            elif addr_type == "fqdn":
                fqdn = (fields.get("fqdn") or [None])[0]
                if fqdn:
                    addresses.append(AddressObject(
                        name=name, type=AddressType.FQDN, value=fqdn,
                        description=comment, origin=ObjectOrigin.FORTIGATE,
                    ))
                else:
                    self.unsupported("address", name, "fqdn type missing 'fqdn' field")
            elif addr_type == "wildcard":
                wc = fields.get("wildcard", [])
                self.unsupported(
                    "address", name,
                    f"FortiGate wildcard-mask address ({' '.join(wc) or 'no value'}) has no direct "
                    f"PAN-OS address-object equivalent - recreate manually if still needed",
                )
            else:
                self.unsupported("address", name, f"Unrecognized/unsupported address type '{addr_type}'")

        # Address groups
        groups: list[AddressGroup] = []
        grp_block = extract_top_config_block(self._lines, "firewall addrgrp")
        for name, fields, _nested in extract_edit_entries(grp_block):
            members = fields.get("member", [])
            comment = " ".join(fields.get("comment", []))
            groups.append(AddressGroup(
                name=name, members=members, description=comment,
                origin=ObjectOrigin.FORTIGATE,
            ))
        return addresses, groups

    # ---- Services -------------------------------------------------------
    def parse_services(self) -> tuple[list[ServiceObject], list[ServiceGroup]]:
        services: list[ServiceObject] = []
        block = extract_top_config_block(self._lines, "firewall service custom")
        for name, fields, _nested in extract_edit_entries(block):
            if name in self._seen_service_names:
                self.warn("service", name, "Duplicate service object name - later definition used")
            self._seen_service_names.add(name)

            comment = " ".join(fields.get("comment", []))
            protocol = (fields.get("protocol", ["TCP/UDP/SCTP"]) or ["TCP/UDP/SCTP"])[0]

            created_any = False
            if "tcp-portrange" in fields or protocol == "TCP/UDP/SCTP":
                for pr in fields.get("tcp-portrange", []):
                    dst, src = _split_portrange(pr)
                    services.append(ServiceObject(
                        name=name, protocol=ServiceProtocol.TCP, dest_port=dst,
                        source_port=src, description=comment, origin=ObjectOrigin.FORTIGATE,
                    ))
                    created_any = True
            if "udp-portrange" in fields:
                for pr in fields.get("udp-portrange", []):
                    dst, src = _split_portrange(pr)
                    services.append(ServiceObject(
                        name=name, protocol=ServiceProtocol.UDP, dest_port=dst,
                        source_port=src, description=comment, origin=ObjectOrigin.FORTIGATE,
                    ))
                    created_any = True
            if "sctp-portrange" in fields:
                for pr in fields.get("sctp-portrange", []):
                    dst, src = _split_portrange(pr)
                    services.append(ServiceObject(
                        name=name, protocol=ServiceProtocol.SCTP, dest_port=dst,
                        source_port=src, description=comment, origin=ObjectOrigin.FORTIGATE,
                    ))
                    created_any = True
            if protocol in ("ICMP", "ICMP6") and not created_any:
                icmp_type = (fields.get("icmptype") or [None])[0]
                icmp_code = (fields.get("icmpcode") or [None])[0]
                services.append(ServiceObject(
                    name=name,
                    protocol=ServiceProtocol.ICMP if protocol == "ICMP" else ServiceProtocol.ICMP6,
                    icmp_type=int(icmp_type) if icmp_type and icmp_type.isdigit() else None,
                    icmp_code=int(icmp_code) if icmp_code and icmp_code.isdigit() else None,
                    description=comment, origin=ObjectOrigin.FORTIGATE,
                ))
                created_any = True
            if not created_any:
                self.unsupported("service", name, f"Service protocol '{protocol}' has no port data - could not convert")

        groups: list[ServiceGroup] = []
        grp_block = extract_top_config_block(self._lines, "firewall service group")
        for name, fields, _nested in extract_edit_entries(grp_block):
            members = fields.get("member", [])
            comment = " ".join(fields.get("comment", []))
            groups.append(ServiceGroup(
                name=name, members=members, description=comment,
                origin=ObjectOrigin.FORTIGATE,
            ))
        return services, groups

    # ---- Interfaces & zones ---------------------------------------------
    def parse_interfaces(self) -> tuple[list[Interface], list[Zone]]:
        # Build zone -> [interfaces] first so interfaces can look up their zone.
        zones: list[Zone] = []
        zone_block = extract_top_config_block(self._lines, "system zone")
        for zname, zfields, _nested in extract_edit_entries(zone_block):
            members = zfields.get("interface", [])
            zones.append(Zone(name=zname, interfaces=members, origin=ObjectOrigin.FORTIGATE))
            for m in members:
                self._iface_zone_map[m] = zname

        interfaces: list[Interface] = []
        iface_block = extract_top_config_block(self._lines, "system interface")
        for name, fields, _nested in extract_edit_entries(iface_block):
            ip_fields = fields.get("ip", [])
            ip_addr = mask = None
            if len(ip_fields) >= 2:
                ip_addr, mask = ip_fields[0], ip_fields[1]

            vdom = (fields.get("vdom") or [None])[0]
            mtu_vals = fields.get("mtu")
            mtu = int(mtu_vals[0]) if mtu_vals and mtu_vals[0].isdigit() else None
            description = " ".join(fields.get("description", []) or fields.get("alias", []))
            dhcp = (fields.get("mode", [None])[0] == "dhcp") if fields.get("mode") else False

            # FortiGate has no native concept of a PAN-OS zone object list; if this
            # interface wasn't referenced by any `config system zone` block, the
            # interface name itself is often used as the informal "zone" concept
            # (e.g. policies reference srcintf/dstintf directly). We surface that
            # ambiguity rather than guessing a zone name.
            zone = self._iface_zone_map.get(name)
            if not zone:
                self.warn(
                    "interface", name,
                    "No matching 'config system zone' entry found - interface has no explicit "
                    "PAN-OS zone assignment. Policies referencing this interface directly will "
                    "use the interface name as the zone; review and assign a real zone.",
                )

            interfaces.append(Interface(
                name=name,
                description=description,
                ip_address=ip_addr,
                netmask=mask,
                zone=zone or name,
                virtual_router=vdom or "default",
                mtu=mtu,
                dhcp_enabled=dhcp,
                origin=ObjectOrigin.FORTIGATE,
            ))
        return interfaces, zones

    # ---- Routes -----------------------------------------------------------
    def parse_routes(self) -> list[Route]:
        routes: list[Route] = []
        block = extract_top_config_block(self._lines, "router static")
        for name, fields, _nested in extract_edit_entries(block):
            dst_fields = fields.get("dst", [])
            if len(dst_fields) >= 2:
                destination = f"{dst_fields[0]}/{_mask_to_cidr(dst_fields[1])}"
            elif len(dst_fields) == 1:
                destination = dst_fields[0]
            else:
                destination = "0.0.0.0/0"

            gateway = (fields.get("gateway") or [None])[0]
            device = (fields.get("device") or [None])[0]
            distance = (fields.get("distance") or [None])[0]

            routes.append(Route(
                name=name,
                destination=destination,
                next_hop=gateway,
                interface=device,
                metric=int(distance) if distance and distance.isdigit() else None,
                origin=ObjectOrigin.FORTIGATE,
            ))
        return routes

    # ---- Policies (best-effort) -------------------------------------------
    def parse_policies(self) -> tuple[list[Policy], list[NATRule]]:
        policies: list[Policy] = []
        nat_rules: list[NATRule] = []
        block = extract_top_config_block(self._lines, "firewall policy")
        for name, fields, _nested in extract_edit_entries(block):
            policy_name = (fields.get("name") or [name])[0]

            # NOTE: these are raw FortiGate interface names (srcintf/dstintf),
            # not PAN-OS zones. PAN-OS is zone-based while FortiGate policies
            # are interface-based, so this tool does not auto-assume a zone
            # mapping here - the interface mapping step (app/mapping/) is the
            # authoritative translator from these raw names to real zones,
            # confirmed by the user before generation.
            src_zones = fields.get("srcintf", ["any"])
            dst_zones = fields.get("dstintf", ["any"])
            src_addrs = fields.get("srcaddr", ["any"])
            dst_addrs = fields.get("dstaddr", ["any"])
            services = fields.get("service", ["ANY"])

            action_raw = (fields.get("action", ["deny"]) or ["deny"])[0]
            action = PolicyAction.ALLOW if action_raw == "accept" else PolicyAction.DENY

            status = (fields.get("status", ["enable"]) or ["enable"])[0]
            disabled = status == "disable"

            log_raw = (fields.get("logtraffic", ["disable"]) or ["disable"])[0]
            log_end = log_raw in ("all", "utm")

            comments = " ".join(fields.get("comments", []))
            schedule = (fields.get("schedule") or [None])[0]

            nat_enabled = (fields.get("nat", ["disable"]) or ["disable"])[0] == "enable"
            nat_rule = None
            if nat_enabled:
                # FortiGate policy-based SNAT: `set nat enable` with no ippool
                # means "use the egress (dstintf) interface's own IP" - PAN-OS
                # models this as source-translation type dynamic-ip-and-port
                # with an interface-address sub-type. Real IP pool references
                # (`set ippool enable` + `set poolname ...`) aren't parsed in
                # Version 1 and are flagged instead of guessed.
                if fields.get("ippool", ["disable"])[0] == "enable":
                    self.unsupported(
                        "nat", policy_name,
                        "Policy uses a FortiGate IP pool for SNAT (set ippool enable / poolname) - "
                        "not parsed in Version 1. Create the equivalent PAN-OS NAT rule with a "
                        "dynamic-ip(-and-port) translated address manually.",
                    )
                else:
                    nat_rule = NATRule(
                        name=f"{policy_name}_snat",
                        source_zone=src_zones,
                        dest_zone=dst_zones[0] if dst_zones else "any",
                        source_address=src_addrs,
                        dest_address=dst_addrs,
                        service=services[0] if services else None,
                        translated_source="interface",  # resolved to the mapped PAN interface's IP at generation time
                        nat_type="dynamic-ip-and-port",
                        nat_method="source",
                        interface_based=True,
                        disabled=disabled,
                        origin=ObjectOrigin.FORTIGATE,
                    )

            policies.append(Policy(
                name=policy_name,
                source_zone=src_zones,
                dest_zone=dst_zones,
                source_address=src_addrs,
                dest_address=dst_addrs,
                service=services,
                action=action,
                log_end=log_end,
                description=comments,
                disabled=disabled,
                schedule=schedule if schedule and schedule != "always" else None,
                origin=ObjectOrigin.FORTIGATE,
            ))
            if nat_rule:
                nat_rules.append(nat_rule)

        nat_rules.extend(self._parse_vip_nat())
        return policies, nat_rules

    def _parse_vip_nat(self) -> list[NATRule]:
        """
        `config firewall vip` defines static DNAT (external IP -> internal
        IP, optionally with port forwarding via extport/mappedport, and
        optionally bidirectional via `set portforward` off + `set
        arp-reply`... in practice FortiGate signals bidirectional/1:1 NAT
        via `set type static-nat` (the default) with no port fields set -
        this is modeled as a one-to-one static NAT rule that is also
        reflected as an implicit source translation for return traffic,
        matching how VIPs behave on FortiGate).
        """
        rules: list[NATRule] = []
        block = extract_top_config_block(self._lines, "firewall vip")
        for name, fields, _nested in extract_edit_entries(block):
            extip = (fields.get("extip") or [None])[0]
            mappedip = (fields.get("mappedip") or [None])[0]
            extintf = (fields.get("extintf") or ["any"])[0]
            extport = (fields.get("extport") or [None])[0]
            mappedport = (fields.get("mappedport") or [None])[0]
            portforward = (fields.get("portforward") or ["disable"])[0] == "enable"
            vip_type = (fields.get("type") or ["static-nat"])[0]

            if not extip or not mappedip:
                self.unsupported("nat", name, "VIP missing extip/mappedip - could not build a DNAT rule")
                continue

            # `set type static-nat` (the default) is FortiGate's 1:1,
            # bidirectional VIP - the same object handles inbound DNAT and
            # implicitly permits the matching outbound SNAT. PAN-OS models
            # both directions on a single NAT rule via source-translation +
            # destination-translation, so mark it bidirectional here; the
            # generator emits both translations from this one rule.
            is_static_nat = vip_type in ("static-nat", "")

            rule = NATRule(
                name=name,
                source_zone=["any"],
                dest_zone=extintf,
                dest_address=[extip],
                translated_dest=mappedip,
                nat_type="static",
                nat_method="bidirectional" if is_static_nat else "destination",
                bidirectional=is_static_nat,
                origin=ObjectOrigin.FORTIGATE,
            )

            if portforward and (extport or mappedport):
                if not extport or not mappedport:
                    self.unsupported(
                        "nat", name,
                        "VIP has port-forwarding enabled but is missing extport or mappedport - "
                        "generated without port translation, review manually.",
                    )
                else:
                    rule.original_port = extport
                    rule.translated_port = mappedport
            elif extport or mappedport:
                self.unsupported(
                    "nat", name,
                    f"VIP '{name}' has extport/mappedport set ({extport}->{mappedport}) but "
                    f"'set portforward enable' was not found - basic IP-only DNAT rule generated; "
                    f"verify whether port forwarding should apply.",
                )

            rules.append(rule)
        return rules

    # NAT (config firewall vip / policy-based NAT) is parsed separately by
    # parse_nat() below - kept out of parse_policies() so NAT-specific issues
    # are attributed to the right object_type.

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
        profiles: list[LdapServerProfile] = []
        block = extract_top_config_block(self._lines, "user ldap")
        for name, fields, _nested in extract_edit_entries(block):
            servers = []
            primary = (fields.get("server") or [None])[0]
            port = (fields.get("port") or [None])[0]
            if primary:
                servers.append(f"{primary}:{port}" if port else primary)
            secondary = (fields.get("secondary-server") or [None])[0]
            if secondary:
                servers.append(f"{secondary}:{port}" if port else secondary)
            tertiary = (fields.get("tertiary-server") or [None])[0]
            if tertiary:
                servers.append(f"{tertiary}:{port}" if port else tertiary)

            secure = (fields.get("secure") or ["disable"])[0]
            ssl_mode = {"ldaps": "ldaps", "starttls": "starttls"}.get(secure, "none")
            timeout_raw = (fields.get("timeout") or [None])[0]

            if not servers:
                self.unsupported("ldap", name, "LDAP profile has no server address - skipped")
                continue

            profiles.append(LdapServerProfile(
                name=name,
                servers=servers,
                base_dn=(fields.get("dn") or [""])[0],
                bind_dn=(fields.get("username") or [""])[0],
                bind_password="********" if fields.get("password") else None,
                ssl_mode=ssl_mode,
                timeout=int(timeout_raw) if timeout_raw and timeout_raw.isdigit() else None,
                origin=ObjectOrigin.FORTIGATE,
            ))
        return profiles

    def _parse_radius(self) -> list[RadiusServerProfile]:
        profiles: list[RadiusServerProfile] = []
        block = extract_top_config_block(self._lines, "user radius")
        for name, fields, _nested in extract_edit_entries(block):
            servers = []
            primary = (fields.get("server") or [None])[0]
            if primary:
                servers.append(primary)
            secondary = (fields.get("secondary-server") or [None])[0]
            if secondary:
                servers.append(secondary)
            tertiary = (fields.get("tertiary-server") or [None])[0]
            if tertiary:
                servers.append(tertiary)

            timeout_raw = (fields.get("timeout") or [None])[0]
            retries_raw = (fields.get("all-usergroup") or [None])[0]  # not a real retries field; kept
            auth_port_raw = (fields.get("auth-port") or [None])[0]

            if not servers:
                self.unsupported("radius", name, "RADIUS profile has no server address - skipped")
                continue

            profiles.append(RadiusServerProfile(
                name=name,
                servers=servers,
                shared_secret="********" if fields.get("secret") else None,
                timeout=int(timeout_raw) if timeout_raw and timeout_raw.isdigit() else None,
                auth_port=int(auth_port_raw) if auth_port_raw and auth_port_raw.isdigit() else None,
                origin=ObjectOrigin.FORTIGATE,
            ))
        return profiles

    def _parse_tacacs(self) -> list[TacacsServerProfile]:
        profiles: list[TacacsServerProfile] = []
        # FortiGate CLI key is "tacacs+" (a literal plus sign in the section name).
        block = extract_top_config_block(self._lines, "user tacacs+")
        for name, fields, _nested in extract_edit_entries(block):
            servers = []
            primary = (fields.get("server") or [None])[0]
            port = (fields.get("port") or [None])[0]
            if primary:
                servers.append(f"{primary}:{port}" if port else primary)

            if not servers:
                self.unsupported("tacacs", name, "TACACS+ profile has no server address - skipped")
                continue

            timeout_raw = (fields.get("authen-type") or [None])[0]  # placeholder if no numeric timeout present
            timeout_num = (fields.get("timeout") or [None])[0]

            profiles.append(TacacsServerProfile(
                name=name,
                servers=servers,
                shared_secret="********" if fields.get("key") else None,
                timeout=int(timeout_num) if timeout_num and timeout_num.isdigit() else None,
                origin=ObjectOrigin.FORTIGATE,
            ))
        return profiles

    def _parse_snmp(self) -> list[SnmpProfile]:
        sysinfo_block = extract_top_config_block(self._lines, "system snmp sysinfo")
        sysinfo = extract_flat_fields(sysinfo_block)
        if not sysinfo and not extract_top_config_block(self._lines, "system snmp community") \
                and not extract_top_config_block(self._lines, "system snmp user"):
            return []

        contact = (sysinfo.get("contact-info") or [""])[0]
        location = (sysinfo.get("location") or [""])[0]

        profiles: list[SnmpProfile] = []

        # SNMPv2 community strings -> one SnmpProfile per community
        community_block = extract_top_config_block(self._lines, "system snmp community")
        for cname, cfields, _nested in extract_edit_entries(community_block):
            community_name = (cfields.get("name") or [None])[0]
            if not community_name:
                self.unsupported("snmp", cname, "SNMP community entry has no 'name' value - skipped")
                continue
            hosts = cfields.get("hosts", [])
            profiles.append(SnmpProfile(
                name=f"snmp-v2c-{cname}",
                version="v2c",
                community="********",
                trap_destinations=hosts,
                contact=contact,
                location=location,
                origin=ObjectOrigin.FORTIGATE,
            ))

        # SNMPv3 users -> one SnmpProfile (v3) aggregating all users, since
        # PAN-OS SNMPv3 device config carries a list of users under one
        # profile rather than one profile per user.
        user_block = extract_top_config_block(self._lines, "system snmp user")
        v3_users: list[SnmpUser] = []
        v3_trap_hosts: list[str] = []
        for uname, ufields, _nested in extract_edit_entries(user_block):
            auth_proto = (ufields.get("auth-proto") or [None])[0]
            priv_proto = (ufields.get("priv-proto") or [None])[0]
            v3_users.append(SnmpUser(
                name=uname,
                auth_protocol=auth_proto,
                auth_password="********" if ufields.get("auth-pwd") else None,
                priv_protocol=priv_proto,
                priv_password="********" if ufields.get("priv-pwd") else None,
            ))
            v3_trap_hosts.extend(ufields.get("notify-hosts", []))
        if v3_users:
            profiles.append(SnmpProfile(
                name="snmp-v3",
                version="v3",
                users=v3_users,
                trap_destinations=v3_trap_hosts,
                contact=contact,
                location=location,
                origin=ObjectOrigin.FORTIGATE,
            ))

        if not profiles and (contact or location):
            # sysinfo set (contact/location) but no community/v3 users found -
            # still surface a device-level profile so contact/location aren't lost.
            profiles.append(SnmpProfile(name="snmp-default", contact=contact, location=location, origin=ObjectOrigin.FORTIGATE))

        return profiles

    def _parse_syslog(self) -> list[SyslogServerProfile]:
        profiles: list[SyslogServerProfile] = []
        # FortiGate supports up to 4 syslog server slots: syslogd..syslogd4.
        for slot in ("syslogd", "syslogd2", "syslogd3", "syslogd4"):
            block = extract_top_config_block(self._lines, f"log {slot} setting")
            fields = extract_flat_fields(block)
            if not fields:
                continue
            status = (fields.get("status") or ["disable"])[0]
            server = (fields.get("server") or [None])[0]
            if status != "enable" or not server:
                continue
            port_raw = (fields.get("port") or ["514"])[0]
            mode = (fields.get("mode") or ["udp"])[0]
            facility = (fields.get("facility") or ["local7"])[0]
            fmt = (fields.get("format") or ["default"])[0]
            source_ip = (fields.get("source-ip") or [None])[0]

            profiles.append(SyslogServerProfile(
                name=slot,
                server=server,
                port=int(port_raw) if port_raw.isdigit() else 514,
                transport="TCP" if mode == "reliable" else "UDP",
                facility=f"LOG_{facility.upper()}" if not facility.upper().startswith("LOG_") else facility.upper(),
                log_format="IETF" if fmt in ("rfc5424", "cef") else "BSD",
                source_interface=source_ip,
                origin=ObjectOrigin.FORTIGATE,
            ))
        return profiles

    def _parse_ntp(self) -> list[NtpProfile]:
        block = extract_top_config_block(self._lines, "system ntp")
        if not block:
            return []
        flat = extract_flat_fields(block)
        ntpsync = (flat.get("ntpsync") or ["disable"])[0]
        if ntpsync != "enable":
            return []

        server_block = extract_top_config_block(block, "ntpserver")
        entries = extract_edit_entries(server_block)
        servers = [(f.get("server") or [None])[0] for _n, f, _nested in entries]
        servers = [s for s in servers if s]
        if not servers:
            return []

        auth = (flat.get("authentication") or ["disable"])[0] == "enable"
        return [NtpProfile(
            primary_server=servers[0] if len(servers) > 0 else None,
            secondary_server=servers[1] if len(servers) > 1 else None,
            authentication=auth,
            origin=ObjectOrigin.FORTIGATE,
        )]

    def _parse_dns(self) -> list[DnsProfile]:
        block = extract_top_config_block(self._lines, "system dns")
        if not block:
            return []
        flat = extract_flat_fields(block)
        primary = (flat.get("primary") or [None])[0]
        secondary = (flat.get("secondary") or [None])[0]
        domain = (flat.get("domain") or [None])[0]
        if not primary and not secondary and not domain:
            return []
        return [DnsProfile(
            primary_dns=primary,
            secondary_dns=secondary,
            domain_name=domain,
            origin=ObjectOrigin.FORTIGATE,
        )]


def _mask_to_cidr(mask: str) -> str:
    if mask.isdigit():
        return mask
    try:
        octets = [int(o) for o in mask.split(".")]
        return str(sum(bin(o).count("1") for o in octets))
    except (ValueError, AttributeError):
        return mask


def _split_portrange(pr: str) -> tuple[str, str | None]:
    """FortiGate port-range format is 'dst[-dst_end][:src[-src_end]]'."""
    if ":" in pr:
        dst, src = pr.split(":", 1)
        return dst, src
    return pr, None
