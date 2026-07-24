"""
Palo Alto CLI Generator
========================
Consumes ONLY app.normalizer.models.NormalizedConfig - never touches
vendor-specific data. This keeps vendor logic and PAN-OS syntax
completely decoupled, per the plugin architecture.

CLI syntax here follows Palo Alto's documented `set` command hierarchy
(config > set address / set address-group / set service / etc.) as
published in the PAN-OS CLI Quick Start / Command Reference. Anything
that doesn't have a clean, documented PAN-OS equivalent is NOT guessed -
it is emitted as a `# TODO (UNSUPPORTED):` comment instead, and recorded
as a ConversionIssue with severity="unsupported" so it shows up in the
coverage report.

Phase 1 note: this module currently implements address / address-group
/ service / service-group / interface generation, which is enough for
the Version 1 conversion scope. generate_security_rules(), NAT, and
route generation are stubbed and will be completed in Phase 6 alongside
the validation engine, since rule generation needs the validation
engine's undefined-reference checks to be trustworthy.
"""

from __future__ import annotations

import logging

from app.normalizer.models import NormalizedConfig, AddressType, ServiceProtocol

logger = logging.getLogger("generator.paloalto")


def _quote_if_needed(name: str) -> str:
    """PAN-OS CLI requires double quotes around names containing spaces
    or other special characters."""
    if any(c.isspace() for c in name) or any(c in name for c in ["'", '"']):
        safe = name.replace('"', '\\"')
        return f'"{safe}"'
    return name


def _value_or_list(values: list[str]) -> str:
    """
    PAN-OS `set` syntax accepts a single bare value OR a bracketed list -
    brackets are only required once there's more than one member. Matches
    real exported configs (e.g. `... source any ...` for one value vs
    `... source [ a b ] ...` for several) rather than always bracketing,
    which is technically accepted but not what PAN-OS itself emits.
    """
    quoted = [_quote_if_needed(v) for v in values]
    if len(quoted) == 1:
        return quoted[0]
    return f"[ {' '.join(quoted)} ]"


class PaloAltoGenerator:
    def __init__(self, config: NormalizedConfig):
        self.config = config
        self.lines: list[str] = []

    def generate_all(self) -> str:
        self.lines = []
        self._header()
        self.lines.extend(self.generate_addresses())
        self.lines.extend(self.generate_address_groups())
        self.lines.extend(self.generate_services())
        self.lines.extend(self.generate_service_groups())
        self.lines.extend(self.generate_zones())
        self.lines.extend(self.generate_virtual_routers())
        self.lines.extend(self.generate_interfaces())
        self.lines.extend(self.generate_routes())
        self.lines.extend(self.generate_nat())
        self.lines.extend(self.generate_security_rules())
        self.lines.extend(self.generate_ldap_profiles())
        self.lines.extend(self.generate_radius_profiles())
        self.lines.extend(self.generate_tacacs_profiles())
        self.lines.extend(self.generate_snmp_profiles())
        self.lines.extend(self.generate_syslog_profiles())
        self.lines.extend(self.generate_ntp())
        self.lines.extend(self.generate_dns())
        self._unsupported_summary()
        return "\n".join(self.lines) + "\n"

    # Ordered section-key -> generator method, used by both generate_all()
    # (via the explicit calls above) and generate_selected() below. Keys are
    # what the frontend's export checklist sends back.
    SECTION_METHODS = {
        "addresses": "generate_addresses",
        "address_groups": "generate_address_groups",
        "services": "generate_services",
        "service_groups": "generate_service_groups",
        "zones": "generate_zones",
        "virtual_routers": "generate_virtual_routers",
        "interfaces": "generate_interfaces",
        "routes": "generate_routes",
        "nat_rules": "generate_nat",
        "security_rules": "generate_security_rules",
        "ldap_profiles": "generate_ldap_profiles",
        "radius_profiles": "generate_radius_profiles",
        "tacacs_profiles": "generate_tacacs_profiles",
        "snmp_profiles": "generate_snmp_profiles",
        "syslog_profiles": "generate_syslog_profiles",
        "ntp_profiles": "generate_ntp",
        "dns_profiles": "generate_dns",
    }

    def generate_selected(self, sections: list[str] | None) -> str:
        """
        Same output as generate_all(), but restricted to the section keys
        the caller asks for. sections=None (or empty/["all"]) means
        everything, matching the "Everything" checkbox in the export UI.
        """
        if not sections or "all" in sections:
            return self.generate_all()

        self.lines = []
        self._header()
        for key in self.SECTION_METHODS:  # fixed order regardless of checklist click order
            if key in sections:
                method = getattr(self, self.SECTION_METHODS[key])
                self.lines.extend(method())
        self._unsupported_summary()
        return "\n".join(self.lines) + "\n"

    def _header(self) -> None:
        self.lines.append("# Generated by Firewall Config Converter")
        self.lines.append("# Palo Alto Networks PAN-OS CLI ('set' format)")
        self.lines.append("# Review all TODO/UNSUPPORTED comments before committing this config.")
        self.lines.append("")

    # ---- Addresses --------------------------------------------------
    def generate_addresses(self) -> list[str]:
        out = ["# --- Address Objects ---"]
        for addr in self.config.addresses:
            name = _quote_if_needed(addr.name)
            if addr.type == AddressType.IP_NETMASK:
                out.append(f"set address {name} ip-netmask {addr.value}")
            elif addr.type == AddressType.IP_RANGE:
                out.append(f"set address {name} ip-range {addr.value}")
            elif addr.type == AddressType.FQDN:
                out.append(f"set address {name} fqdn {addr.value}")
            else:
                out.append(f"# TODO (UNSUPPORTED): address '{addr.name}' type "
                            f"'{addr.type}' has no direct PAN-OS equivalent - review manually")
                logger.warning("Unsupported address type for %s: %s", addr.name, addr.type)
            if addr.description:
                desc = addr.description.replace('"', '\\"')
                out.append(f'set address {name} description "{desc}"')
            for tag in addr.tags:
                out.append(f"set address {name} tag [ {_quote_if_needed(tag)} ]")
        out.append("")
        return out

    def generate_address_groups(self) -> list[str]:
        out = ["# --- Address Groups ---"]
        for grp in self.config.address_groups:
            name = _quote_if_needed(grp.name)
            if grp.dynamic_filter:
                out.append(f'set address-group {name} dynamic filter "{grp.dynamic_filter}"')
            elif grp.members:
                for member in grp.members:
                    out.append(f"set address-group {name} static {_quote_if_needed(member)}")
            else:
                out.append(f"# NOTE: address-group '{grp.name}' has no members - PAN-OS will reject "
                            f"an empty static group; add at least one member or remove it")
            if grp.description:
                desc = grp.description.replace('"', '\\"')
                out.append(f'set address-group {name} description "{desc}"')
        out.append("")
        return out

    # ---- Services -----------------------------------------------------
    def generate_services(self) -> list[str]:
        out = ["# --- Service Objects ---"]
        for svc in self.config.services:
            name = _quote_if_needed(svc.name)
            if svc.protocol in (ServiceProtocol.TCP, ServiceProtocol.UDP, ServiceProtocol.SCTP):
                port = svc.dest_port or "any"
                out.append(f"set service {name} protocol {svc.protocol.value} port {port}")
                if svc.source_port:
                    out.append(f"set service {name} protocol {svc.protocol.value} source-port {svc.source_port}")
            elif svc.protocol in (ServiceProtocol.ICMP, ServiceProtocol.ICMP6):
                # PAN-OS models ICMP as an application, not a `set service` protocol entry.
                out.append(
                    f"# NOTE: '{svc.name}' is ICMP - PAN-OS handles ICMP via the built-in "
                    f"'ping'/'icmp' application, not a custom service object. Map policy "
                    f"service reference to application 'ping' or a custom App-ID instead."
                )
            if svc.description:
                desc = svc.description.replace('"', '\\"')
                out.append(f'set service {name} description "{desc}"')
        out.append("")
        return out

    def generate_service_groups(self) -> list[str]:
        out = ["# --- Service Groups ---"]
        for grp in self.config.service_groups:
            name = _quote_if_needed(grp.name)
            if grp.members:
                for member in grp.members:
                    out.append(f"set service-group {name} members {_quote_if_needed(member)}")
            else:
                out.append(f"# NOTE: service-group '{grp.name}' has no members - PAN-OS will reject "
                            f"an empty group; add at least one member or remove it")
        out.append("")
        return out

    # ---- Interfaces -----------------------------------------------------
    def generate_interfaces(self) -> list[str]:
        out = ["# --- Interfaces ---"]
        for iface in self.config.interfaces:
            pan_name = iface.pan_name or iface.name
            itype = iface.interface_type if iface.interface_type in ("layer3", "layer2", "vwire") else "layer3"
            pan_itype = "virtual-wire" if itype == "vwire" else itype

            # Subinterface (e.g. "ethernet1/5.100"): PAN-OS models this as a
            # "unit" under its parent physical interface, tagged with the
            # 802.1Q VLAN ID - a fundamentally different CLI shape than a
            # plain physical interface, so it's handled as its own branch
            # rather than trying to reuse `base` below.
            if "." in pan_name and itype == "layer3":
                parent, _, unit_suffix = pan_name.partition(".")
                sub_base = f"set network interface ethernet {parent} layer3 units {pan_name}"
                if iface.ip_address and iface.netmask:
                    out.append(f"{sub_base} ip {iface.ip_address}/{_netmask_to_cidr(iface.netmask)}")
                elif iface.ip_address:
                    out.append(f"{sub_base} ip {iface.ip_address}")
                if iface.vlan:
                    out.append(f"{sub_base} tag {iface.vlan}")
                elif unit_suffix.isdigit():
                    # No explicit VLAN set - PAN-OS requires a tag on every
                    # subinterface, so fall back to the numeric suffix
                    # already in the name (ethernet1/5.100 -> tag 100).
                    out.append(f"{sub_base} tag {unit_suffix}")
                if iface.mtu:
                    out.append(f"{sub_base} mtu {iface.mtu}")
                continue

            base = f"set network interface ethernet {pan_name}"

            if itype == "layer3":
                if iface.ip_address and iface.netmask:
                    out.append(f"{base} layer3 ip {iface.ip_address}/{_netmask_to_cidr(iface.netmask)}")
                elif iface.ip_address:
                    out.append(f"{base} layer3 ip {iface.ip_address}")
                if iface.mtu:
                    out.append(f"{base} layer3 mtu {iface.mtu}")
                if iface.management_profile:
                    out.append(f"{base} layer3 interface-management-profile {iface.management_profile}")
                if iface.dhcp_enabled:
                    out.append(f"{base} layer3 dhcp-client enable yes")
            else:
                # layer2/virtual-wire interfaces don't carry an IP - flag if
                # the source config had one so it isn't silently dropped.
                if iface.ip_address:
                    out.append(f"# NOTE: '{pan_name}' is configured as {pan_itype} - source IP "
                                f"{iface.ip_address} was not applied (not valid for this interface type)")

            if not iface.enabled:
                out.append(f"# NOTE: '{pan_name}' was administratively disabled in the source config - "
                            f"PAN-OS has no direct 'shutdown' equivalent at this config level; leave "
                            f"unassigned from a zone/vsys or set link-state down manually if it should "
                            f"stay disabled")

            if iface.description:
                desc = iface.description.replace('"', '\\"')
                out.append(f'{base} comment "{desc}"')
        out.append("")
        return out

    def generate_zones(self) -> list[str]:
        """
        One `set zone <name> network <type> [ if1 if2 ... ]` per zone,
        derived live from each interface's current `zone` field - the same
        source of truth the Overview/Interfaces grid edits directly. (This
        used to depend on a separate config.zones list only built by the
        old standalone mapping wizard's "Zone Creation" step; deriving it
        here instead means zones stay correct no matter how the interface
        fields were set - old wizard or the merged Overview editor.)
        PAN-OS `set` replaces the whole member list, so one `set` per
        interface would silently drop all but the last interface in a
        multi-interface zone - hence building the full member list first.
        """
        zone_interfaces: dict[str, list[str]] = {}
        iface_type_by_zone: dict[str, str] = {}
        for iface in self.config.interfaces:
            if not iface.zone:
                continue
            pan_name = iface.pan_name or iface.name
            zone_interfaces.setdefault(iface.zone, []).append(pan_name)
            iface_type_by_zone.setdefault(iface.zone, iface.interface_type)

        if not zone_interfaces:
            return []
        out = ["# --- Zones ---"]
        for zone_name, members in zone_interfaces.items():
            zone_type = iface_type_by_zone.get(zone_name, "layer3")
            pan_type = "virtual-wire" if zone_type == "vwire" else zone_type
            member_str = " ".join(_quote_if_needed(i) for i in members)
            out.append(f"set zone {_quote_if_needed(zone_name)} network {pan_type} [ {member_str} ]")
        out.append("")
        return out

    def generate_virtual_routers(self) -> list[str]:
        """One aggregated `set network virtual-router <vr> interface [ ... ]` per VR - same overwrite-list reasoning as generate_zones()."""
        vr_interfaces: dict[str, list[str]] = {}
        for iface in self.config.interfaces:
            if iface.virtual_router and iface.interface_type == "layer3":
                pan_name = iface.pan_name or iface.name
                vr_interfaces.setdefault(iface.virtual_router, []).append(pan_name)
        if not vr_interfaces:
            return []
        out = ["# --- Virtual Routers ---"]
        for vr, ifaces in vr_interfaces.items():
            members = " ".join(_quote_if_needed(i) for i in ifaces)
            out.append(f"set network virtual-router {_quote_if_needed(vr)} interface [ {members} ]")
        out.append("")
        return out

    # ---- Stubs completed in Phase 6 ----------------------------------
    def generate_routes(self) -> list[str]:
        if not self.config.routes:
            return []
        out = ["# --- Static Routes ---"]
        for r in self.config.routes:
            vr = r.virtual_router or "default"
            name = _quote_if_needed(r.name or r.destination)
            line = f"set network virtual-router {vr} routing-table ip static-route {name} destination {r.destination}"
            if r.interface:
                line += f" interface {r.interface}"
            if r.next_hop:
                line += f" nexthop ip-address {r.next_hop}"
            if r.metric is not None:
                line += f" metric {r.metric}"
            out.append(line)
            if not r.interface:
                out.append(f"# NOTE: static route '{r.name or r.destination}' has no egress interface set - "
                            f"set one in the Routing tab (Network) so PAN-OS can resolve the next hop")
        out.append("")
        return out

    def generate_nat(self) -> list[str]:
        if not self.config.nat_rules:
            return []
        out = ["# --- NAT Rules ---"]
        for nat in self.config.nat_rules:
            name = _quote_if_needed(nat.name)
            base = f"set rulebase nat rules {name}"

            src_zone = _value_or_list(nat.source_zone or ["any"])
            dst_zone = _quote_if_needed(nat.dest_zone) if nat.dest_zone else "any"
            out.append(f"{base} from {src_zone}")
            out.append(f"{base} to {dst_zone}")

            src_addr = _value_or_list(nat.source_address or ["any"])
            dst_addr = _value_or_list(nat.dest_address or ["any"])
            out.append(f"{base} source {src_addr}")
            out.append(f"{base} destination {dst_addr}")

            if nat.service:
                out.append(f"{base} service {_quote_if_needed(nat.service)}")

            do_source = nat.nat_method in ("source", "bidirectional") or nat.bidirectional
            do_dest = nat.nat_method in ("destination", "bidirectional") or nat.bidirectional or nat.translated_dest

            if do_source and (nat.translated_source or nat.egress_interface):
                if nat.egress_interface:
                    # Explicit Egress Interface picked on the NAT Rules grid -
                    # always wins over the older translated_source
                    # 'interface[:<name>]' resolution path below, and never
                    # needs the TODO since the interface is known directly.
                    out.append(f"{base} source-translation dynamic-ip-and-port "
                                f"interface-address interface {nat.egress_interface}")
                elif nat.interface_based or (nat.translated_source or "").startswith("interface"):
                    if nat.translated_source.startswith("interface:"):
                        pan_iface = nat.translated_source.split(":", 1)[1]
                        out.append(f"{base} source-translation dynamic-ip-and-port "
                                    f"interface-address interface {pan_iface}")
                    else:
                        out.append(f"# TODO: SNAT rule '{nat.name}' wants to translate to the egress "
                                    f"interface's own IP, but that interface wasn't resolved during "
                                    f"mapping - re-run through the interface mapping step, or set "
                                    f"'source-translation dynamic-ip-and-port interface-address "
                                    f"interface <ethernetX/Y>' manually")
                elif nat.nat_type == "dynamic-ip-and-port":
                    out.append(f"{base} source-translation dynamic-ip-and-port "
                                f"translated-address [ {_quote_if_needed(nat.translated_source)} ]")
                elif nat.nat_type == "dynamic-ip":
                    out.append(f"{base} source-translation dynamic-ip "
                                f"translated-address [ {_quote_if_needed(nat.translated_source)} ]")
                else:
                    out.append(f"{base} source-translation static-ip translated-address "
                                f"{nat.translated_source}")

            if do_dest and nat.translated_dest:
                out.append(f"{base} destination-translation translated-address {nat.translated_dest}")
                if nat.original_port and nat.translated_port:
                    out.append(f"{base} destination-translation translated-port {nat.translated_port}")
                    out.append(f"# NOTE: original (pre-NAT) service port for '{nat.name}' was "
                                f"{nat.original_port} - create/verify a matching service object "
                                f"covering that port on the security rule using this NAT rule")
                elif nat.original_port or nat.translated_port:
                    out.append(f"# TODO: NAT rule '{nat.name}' has a partial port-forwarding "
                                f"translation (original={nat.original_port}, translated={nat.translated_port}) "
                                f"- both must be set for PAN-OS port translation; set the missing one manually")

            if nat.bidirectional and not (do_source and nat.translated_source):
                # FortiGate 1:1 static-nat VIPs implicitly permit the return
                # (outbound) direction using the same IP pair - PAN-OS needs
                # that made explicit via a source-translation using the
                # mapped (internal) address as the static NAT IP so hosts
                # behind mappedip appear as extip on the way out.
                if nat.translated_dest:
                    out.append(f"# NOTE: '{nat.name}' is a bidirectional/1:1 NAT - if the internal host "
                                f"({nat.translated_dest}) should also appear as {', '.join(nat.dest_address) or 'the external IP'} "
                                f"on outbound traffic, add a matching source-translation static-ip rule for that direction")

            if nat.disabled:
                out.append(f"{base} disabled yes")
        out.append("")
        return out

    def generate_security_rules(self) -> list[str]:
        if not self.config.policies:
            return []
        out = ["# --- Security Rules ---"]
        for p in self.config.policies:
            name = _quote_if_needed(p.name)
            base = f"set rulebase security rules {name}"

            src_zone = _value_or_list(p.source_zone or ["any"])
            dst_zone = _value_or_list(p.dest_zone or ["any"])
            src_addr = _value_or_list(p.source_address or ["any"])
            dst_addr = _value_or_list(p.dest_address or ["any"])
            service = _value_or_list(p.service or ["any"])
            application = _value_or_list(p.application or ["any"])

            # One consolidated line for the core match criteria - this is
            # the canonical PAN-OS `set` form (a single command against the
            # rule's path with multiple keyword arguments) rather than one
            # `set` per field; each keyword only needs brackets once it
            # carries more than one value.
            out.append(
                f"{base} from {src_zone} to {dst_zone} source {src_addr} destination {dst_addr} "
                f"application {application} service {service} action {p.action.value}"
            )

            if p.log_end:
                out.append(f"{base} log-end yes")
            if p.log_start:
                out.append(f"{base} log-start yes")
            if p.disabled:
                out.append(f"{base} disabled yes")
            if p.schedule:
                out.append(f"{base} schedule {_quote_if_needed(p.schedule)}")
            if p.tags:
                tag_list = " ".join(_quote_if_needed(t) for t in p.tags)
                out.append(f"{base} tag [ {tag_list} ]")
            if p.log_forwarding_profile:
                out.append(f"{base} log-setting {_quote_if_needed(p.log_forwarding_profile)}")
            if p.security_profile_group:
                out.append(f"{base} profile-setting group [ {_quote_if_needed(p.security_profile_group)} ]")
            if p.description:
                desc = p.description.replace('"', '\\"')
                out.append(f'{base} description "{desc}"')

            # Service strings like "tcp/443" coming from vendor ACLs are
            # descriptive, not real PAN-OS service-object names - flag so
            # the reviewer creates/binds the matching `set service` object.
            for s in (p.service or []):
                if "/" in s and s not in [svc.name for svc in self.config.services]:
                    out.append(f"# TODO: service reference '{s}' on rule '{p.name}' is a literal "
                                f"protocol/port, not a named PAN-OS service object - create one "
                                f"(e.g. 'set service {s.replace('/', '_')} protocol {s.split('/')[0]} "
                                f"port {s.split('/')[1] if '/' in s else ''}') and reference it here")
        out.append("")
        return out

    # ---- System / Auth / Logging Profiles --------------------------------
    def generate_ldap_profiles(self) -> list[str]:
        if not self.config.ldap_profiles:
            return []
        out = ["# --- LDAP Server Profiles ---"]
        for p in self.config.ldap_profiles:
            name = _quote_if_needed(p.name)
            for idx, server in enumerate(p.servers, start=1):
                host, _, port = server.partition(":")
                server_name = f"{p.name}-srv{idx}"
                out.append(f"set shared server-profile ldap {name} server {_quote_if_needed(server_name)} address {host}")
                out.append(f"set shared server-profile ldap {name} server {_quote_if_needed(server_name)} port {port or 389}")
            if p.base_dn:
                out.append(f'set shared server-profile ldap {name} base "{p.base_dn}"')
            if p.bind_dn:
                out.append(f'set shared server-profile ldap {name} bind-dn "{p.bind_dn}"')
            if p.bind_password:
                out.append(f"# TODO: set the bind password for LDAP profile '{p.name}' manually - "
                            f"secrets are never carried over from the source configuration")
            ssl = {"ldaps": "yes", "starttls": "yes"}.get(p.ssl_mode, "no")
            out.append(f"set shared server-profile ldap {name} ssl {ssl}")
            if p.timeout is not None:
                out.append(f"set shared server-profile ldap {name} timeout {p.timeout}")
        out.append("")
        return out

    def generate_radius_profiles(self) -> list[str]:
        if not self.config.radius_profiles:
            return []
        out = ["# --- RADIUS Server Profiles ---"]
        for p in self.config.radius_profiles:
            name = _quote_if_needed(p.name)
            for idx, server in enumerate(p.servers, start=1):
                server_name = f"{p.name}-srv{idx}"
                out.append(f"set shared server-profile radius {name} server {_quote_if_needed(server_name)} ip-address {server}")
                out.append(f"set shared server-profile radius {name} server {_quote_if_needed(server_name)} port {p.auth_port or 1812}")
                if p.shared_secret:
                    out.append(f"# TODO: set the shared secret for RADIUS profile '{p.name}' server "
                                f"'{server_name}' manually - secrets are never carried over")
            if p.timeout is not None:
                out.append(f"set shared server-profile radius {name} timeout {p.timeout}")
            if p.retries is not None:
                out.append(f"set shared server-profile radius {name} retries {p.retries}")
        out.append("")
        return out

    def generate_tacacs_profiles(self) -> list[str]:
        if not self.config.tacacs_profiles:
            return []
        out = ["# --- TACACS+ Server Profiles ---"]
        for p in self.config.tacacs_profiles:
            name = _quote_if_needed(p.name)
            for idx, server in enumerate(p.servers, start=1):
                host, _, port = server.partition(":")
                server_name = f"{p.name}-srv{idx}"
                out.append(f"set shared server-profile tacplus {name} server {_quote_if_needed(server_name)} ip-address {host}")
                out.append(f"set shared server-profile tacplus {name} server {_quote_if_needed(server_name)} port {port or 49}")
                if p.shared_secret:
                    out.append(f"# TODO: set the shared secret for TACACS+ profile '{p.name}' server "
                                f"'{server_name}' manually - secrets are never carried over")
            if p.timeout is not None:
                out.append(f"set shared server-profile tacplus {name} timeout {p.timeout}")
        out.append("")
        return out

    def generate_snmp_profiles(self) -> list[str]:
        if not self.config.snmp_profiles:
            return []
        out = ["# --- SNMP Configuration ---"]
        for p in self.config.snmp_profiles:
            if p.contact:
                out.append(f'set deviceconfig system snmp-setting contact "{p.contact}"')
            if p.location:
                out.append(f'set deviceconfig system snmp-setting location "{p.location}"')
            if p.version == "v2c" and p.community:
                out.append("# TODO: set the SNMPv2c community string manually - secrets/community "
                            "strings are never carried over from the source configuration")
                out.append(f"set deviceconfig system snmp-setting access-setting version v2c snmp-community-string <set-me>")
            elif p.version == "v3" and p.users:
                for user in p.users:
                    uname = _quote_if_needed(user.name)
                    out.append(f"set deviceconfig system snmp-setting access-setting version v3 users {uname} "
                                f"auth-pwd-type {user.auth_protocol or 'sha1'}")
                    out.append(f"set deviceconfig system snmp-setting access-setting version v3 users {uname} "
                                f"priv-pwd-type {user.priv_protocol or 'aes'}")
                    out.append(f"# TODO: set the auth/priv passwords for SNMPv3 user '{user.name}' manually")
            for idx, dest in enumerate(p.trap_destinations, start=1):
                host, _, port = dest.partition(":")
                trap_name = f"{p.name}-trap{idx}"
                out.append(f"set shared server-profile snmp {_quote_if_needed(trap_name)} version "
                            f"{p.version} server {host}" + (f" port {port}" if port else ""))
        out.append("")
        return out

    def generate_syslog_profiles(self) -> list[str]:
        if not self.config.syslog_profiles:
            return []
        out = ["# --- Syslog Server Profiles & Log Forwarding ---"]
        for p in self.config.syslog_profiles:
            name = _quote_if_needed(p.name)
            out.append(f"set shared server-profile syslog {name} server {_quote_if_needed(p.name)} server {p.server}")
            out.append(f"set shared server-profile syslog {name} server {_quote_if_needed(p.name)} port {p.port}")
            out.append(f"set shared server-profile syslog {name} server {_quote_if_needed(p.name)} "
                        f"transport {p.transport}")
            out.append(f"set shared server-profile syslog {name} server {_quote_if_needed(p.name)} "
                        f"facility {p.facility}")
            out.append(f"set shared server-profile syslog {name} server {_quote_if_needed(p.name)} "
                        f"format {p.log_format}")
            if p.source_interface:
                out.append(f"# NOTE: source interface/IP '{p.source_interface}' from the original "
                            f"config has no direct PAN-OS server-profile equivalent - PAN-OS always "
                            f"sources logs from the management or a configured service route")

            # A matching Log Forwarding Profile lets Security Policies send
            # their logs to this syslog destination - added to
            # log_forwarding_profiles so it shows up as a selectable option
            # on the Security Policies grid (same mechanism used for
            # manually-declared profiles), rather than force-assigning it to
            # every existing rule.
            lf_name = f"{p.name}-forwarding"
            out.append(f'set shared log-settings profiles {_quote_if_needed(lf_name)} match-list '
                        f'"all-logs" log-type traffic send-syslog {name}')
            out.append(f'set shared log-settings profiles {_quote_if_needed(lf_name)} match-list '
                        f'"all-logs" filter "All Logs"')
            if lf_name not in self.config.log_forwarding_profiles:
                self.config.log_forwarding_profiles.append(lf_name)
        out.append("")
        return out

    def generate_ntp(self) -> list[str]:
        if not self.config.ntp_profiles:
            return []
        out = ["# --- NTP Configuration ---"]
        for p in self.config.ntp_profiles:
            if p.primary_server:
                out.append(f"set deviceconfig system ntp-servers primary-ntp-server ntp-server-address {p.primary_server}")
            if p.secondary_server:
                out.append(f"set deviceconfig system ntp-servers secondary-ntp-server ntp-server-address {p.secondary_server}")
            if p.authentication:
                out.append("# TODO: NTP authentication was enabled on the source device - configure "
                            "the authentication key/type manually, it is never carried over")
                out.append("set deviceconfig system ntp-servers primary-ntp-server authentication-type "
                            "symmetric-key")
            if p.timezone:
                out.append(f"set deviceconfig system timezone {p.timezone}")
        out.append("")
        return out

    def generate_dns(self) -> list[str]:
        if not self.config.dns_profiles:
            return []
        out = ["# --- DNS Configuration ---"]
        for p in self.config.dns_profiles:
            if p.primary_dns:
                out.append(f"set deviceconfig system dns-setting servers primary {p.primary_dns}")
            if p.secondary_dns:
                out.append(f"set deviceconfig system dns-setting servers secondary {p.secondary_dns}")
            if p.domain_name:
                out.append(f"set deviceconfig system domain {p.domain_name}")
            if p.dns_proxy_enabled:
                out.append(f"# NOTE: '{p.name}' used a DNS proxy on the source device - PAN-OS DNS "
                            f"proxy objects are configured separately under Network > DNS Proxy, "
                            f"review and recreate manually if still needed")
        out.append("")
        return out

    def _unsupported_summary(self) -> None:
        unsupported = [i for i in self.config.issues if i.severity == "unsupported"]
        if not unsupported:
            return
        self.lines.append("# --- Unsupported / Manual Review Items ---")
        for issue in unsupported:
            self.lines.append(f"# TODO (UNSUPPORTED): [{issue.object_type}:{issue.object_name}] {issue.message}")
        self.lines.append("")


def _netmask_to_cidr(netmask: str) -> str:
    """Convert dotted netmask to CIDR prefix length; passes through if already CIDR."""
    if netmask.isdigit():
        return netmask
    try:
        octets = [int(o) for o in netmask.split(".")]
        bits = sum(bin(o).count("1") for o in octets)
        return str(bits)
    except (ValueError, AttributeError):
        return netmask
