"""
Normalized Object Model
========================
Every vendor parser (FortiGate, Check Point, Cisco ASA, Sophos XG, ...)
populates ONLY these classes. No vendor-specific logic exists past this
boundary. The Palo Alto generator consumes ONLY these classes.

This is the seam that makes the "add a vendor = add a parser module"
promise true. If you ever find yourself writing vendor-specific
branching in the generator, something has leaked and needs fixing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ObjectOrigin(str, Enum):
    """Where a normalized object came from, for traceability in reports."""
    FORTIGATE = "fortigate"
    CHECKPOINT = "checkpoint"
    CISCO_ASA = "cisco_asa"
    SOPHOS_XG = "sophos_xg"
    JUNIPER_SRX = "juniper_srx"
    MANUAL = "manual"


class AddressType(str, Enum):
    IP_NETMASK = "ip-netmask"
    IP_RANGE = "ip-range"
    FQDN = "fqdn"
    IP_WILDCARD = "ip-wildcard"  # PAN-OS has no native equivalent -> flagged unsupported downstream


class ServiceProtocol(str, Enum):
    TCP = "tcp"
    UDP = "udp"
    SCTP = "sctp"
    ICMP = "icmp"
    ICMP6 = "icmp6"


class PolicyAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    DROP = "drop"
    RESET = "reset-client"


@dataclass
class ConversionIssue:
    """
    A single thing that could not be cleanly converted. Never silently
    dropped - every unsupported / ambiguous field produces one of these,
    which downstream becomes a TODO comment in the CLI output and a row
    in the coverage report.
    """
    severity: str  # "warning" | "error" | "unsupported"
    object_type: str  # e.g. "policy", "address", "interface"
    object_name: str
    message: str
    source_line: Optional[str] = None


@dataclass
class AddressObject:
    name: str
    type: AddressType
    value: str  # ip/mask, range "a-b", or fqdn string
    description: str = ""
    tags: list[str] = field(default_factory=list)
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class AddressGroup:
    name: str
    members: list[str] = field(default_factory=list)  # names of AddressObject or nested AddressGroup
    description: str = ""
    dynamic_filter: Optional[str] = None  # tag-based dynamic groups; None = static
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class ServiceObject:
    name: str
    protocol: ServiceProtocol
    dest_port: Optional[str] = None   # "443" or "8000-8010"
    source_port: Optional[str] = None
    icmp_type: Optional[int] = None
    icmp_code: Optional[int] = None
    description: str = ""
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class ServiceGroup:
    name: str
    members: list[str] = field(default_factory=list)
    description: str = ""
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class Interface:
    name: str  # the identifier referenced elsewhere in the config (FortiGate:
               # raw interface name e.g. "port1"; Cisco: nameif e.g. "outside" -
               # this is deliberately the SAME namespace used by Policy
               # source_zone/dest_zone and Route.interface, so the interface
               # mapping step can rewrite all three consistently)
    hardware_name: Optional[str] = None  # Cisco only: the physical name (e.g. "GigabitEthernet0/0"),
                                          # shown to the user for context since `name` is the nameif
    pan_name: Optional[str] = None  # mapped PAN-OS interface name (e.g. "ethernet1/1") - set by the
                                     # interface mapping step, not the parser
    interface_type: str = "layer3"  # layer3 | layer2 | vwire - set by the mapping step
    enabled: bool = True
    description: str = ""
    ip_address: Optional[str] = None
    netmask: Optional[str] = None
    zone: Optional[str] = None  # parser's SUGGESTED zone (e.g. FortiGate system-zone name, or Cisco
                                 # nameif) - a prefill hint for the mapping UI, never used directly for
                                 # generation. The mapping step's user-confirmed zone is authoritative.
    vlan: Optional[int] = None
    virtual_router: Optional[str] = None
    mtu: Optional[int] = None
    management_profile: Optional[str] = None
    dhcp_enabled: bool = False
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class Zone:
    name: str
    interfaces: list[str] = field(default_factory=list)
    description: str = ""
    origin: Optional[ObjectOrigin] = None


@dataclass
class Route:
    name: Optional[str]
    destination: str
    next_hop: Optional[str] = None
    interface: Optional[str] = None
    metric: Optional[int] = None
    virtual_router: str = "default"
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class NATRule:
    """
    Covers every NAT variant called for by the migration scope: static,
    dynamic (dynamic-ip / dynamic-ip-and-port aka PAT), source, destination,
    bidirectional, VIP/virtual-IP (destination NAT, optionally with port
    forwarding), one-to-one (single source -> single translated_source,
    nat_type='static'), many-to-one (a subnet/range dynamically translated
    to one IP, nat_type='dynamic-ip-and-port'), and interface-based PAT
    (interface_based=True, translated_source='interface[:<pan_iface>]').
    """
    name: str
    source_zone: list[str] = field(default_factory=list)
    dest_zone: Optional[str] = None
    source_address: list[str] = field(default_factory=list)
    dest_address: list[str] = field(default_factory=list)
    translated_source: Optional[str] = None
    translated_dest: Optional[str] = None
    service: Optional[str] = None
    nat_type: str = "static"  # static | dynamic-ip | dynamic-ip-and-port
    # Which side(s) this rule translates - PAN-OS models source and
    # destination translation as independent settings on the same rule, so
    # "bidirectional" really means both are populated on one NATRule.
    nat_method: str = "source"  # source | destination | bidirectional
    bidirectional: bool = False
    interface_based: bool = False  # translate to the egress interface's own IP (a form of PAT)
    egress_interface: Optional[str] = None     # explicit ethernet1/1-24 pick for interface-address PAT
    egress_interface_ip: Optional[str] = None  # user-editable reference IP shown next to egress_interface
    original_port: Optional[str] = None    # original dest port for VIP/DNAT port-forwarding
    translated_port: Optional[str] = None  # translated dest port for VIP/DNAT port-forwarding
    disabled: bool = False
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class Policy:
    name: str
    source_zone: list[str] = field(default_factory=lambda: ["any"])
    dest_zone: list[str] = field(default_factory=lambda: ["any"])
    source_address: list[str] = field(default_factory=lambda: ["any"])
    dest_address: list[str] = field(default_factory=lambda: ["any"])
    service: list[str] = field(default_factory=lambda: ["any"])
    application: list[str] = field(default_factory=lambda: ["any"])
    action: PolicyAction = PolicyAction.DENY
    log_start: bool = False
    log_end: bool = True
    description: str = ""
    disabled: bool = False
    schedule: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    log_forwarding_profile: Optional[str] = None
    security_profile_group: Optional[str] = None
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class LdapServerProfile:
    """Palo Alto 'LDAP Server Profile' equivalent."""
    name: str
    servers: list[str] = field(default_factory=list)  # "host" or "host:port", primary first
    base_dn: str = ""
    bind_dn: str = ""
    bind_password: Optional[str] = None
    ssl_mode: str = "none"  # none | ldaps | starttls
    timeout: Optional[int] = None
    description: str = ""
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class RadiusServerProfile:
    """Palo Alto 'RADIUS Server Profile' equivalent."""
    name: str
    servers: list[str] = field(default_factory=list)  # "host" or "host:auth_port"
    shared_secret: Optional[str] = None
    timeout: Optional[int] = None
    retries: Optional[int] = None
    auth_port: Optional[int] = None
    acct_port: Optional[int] = None
    description: str = ""
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class TacacsServerProfile:
    """Palo Alto 'TACACS+ Server Profile' equivalent."""
    name: str
    servers: list[str] = field(default_factory=list)  # "host" or "host:port"
    shared_secret: Optional[str] = None
    timeout: Optional[int] = None
    use_for_authentication: bool = True
    use_for_authorization: bool = False
    use_for_accounting: bool = False
    description: str = ""
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class SnmpUser:
    """A single SNMPv3 user entry within a SnmpProfile."""
    name: str
    auth_protocol: Optional[str] = None  # md5 | sha
    auth_password: Optional[str] = None
    priv_protocol: Optional[str] = None  # des | aes
    priv_password: Optional[str] = None


@dataclass
class SnmpProfile:
    """Palo Alto SNMP monitoring configuration (device SNMP + SNMP trap server profile)."""
    name: str = "default"
    version: str = "v2c"  # v2c | v3
    community: Optional[str] = None  # v2c community string
    users: list[SnmpUser] = field(default_factory=list)  # v3 users
    trap_destinations: list[str] = field(default_factory=list)  # "host" or "host:port"
    contact: str = ""
    location: str = ""
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class SyslogServerProfile:
    """Palo Alto 'Syslog Server Profile' equivalent, feeding a generated Log Forwarding Profile."""
    name: str
    server: str = ""
    port: int = 514
    transport: str = "UDP"  # UDP | TCP
    facility: str = "LOG_USER"
    log_format: str = "BSD"  # BSD | IETF
    source_interface: Optional[str] = None
    description: str = ""
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class NtpProfile:
    """Palo Alto NTP configuration (device-wide, so at most one row is generally expected)."""
    name: str = "ntp"
    primary_server: Optional[str] = None
    secondary_server: Optional[str] = None
    authentication: bool = False
    authentication_key: Optional[str] = None
    timezone: Optional[str] = None
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class DnsProfile:
    """Palo Alto DNS configuration (device-wide, so at most one row is generally expected)."""
    name: str = "dns"
    primary_dns: Optional[str] = None
    secondary_dns: Optional[str] = None
    domain_name: Optional[str] = None
    search_domain: Optional[str] = None
    dns_proxy_enabled: bool = False
    origin: Optional[ObjectOrigin] = None
    source_line: Optional[str] = None


@dataclass
class NormalizedConfig:
    """Container returned by every parser's .parse() call."""
    addresses: list[AddressObject] = field(default_factory=list)
    address_groups: list[AddressGroup] = field(default_factory=list)
    services: list[ServiceObject] = field(default_factory=list)
    service_groups: list[ServiceGroup] = field(default_factory=list)
    interfaces: list[Interface] = field(default_factory=list)
    zones: list[Zone] = field(default_factory=list)
    routes: list[Route] = field(default_factory=list)
    nat_rules: list[NATRule] = field(default_factory=list)
    policies: list[Policy] = field(default_factory=list)
    issues: list[ConversionIssue] = field(default_factory=list)

    # --- Policy Profiles -------------------------------------------------
    # These reference profiles that already exist on the destination
    # firewall - we only need their NAMES here (not contents), so Policy
    # rows can point at one via a dropdown instead of free-typing it.
    log_forwarding_profiles: list[str] = field(default_factory=list)
    security_profile_groups: list[str] = field(default_factory=list)

    # --- System / auth / logging profiles ---------------------------------
    ldap_profiles: list[LdapServerProfile] = field(default_factory=list)
    radius_profiles: list[RadiusServerProfile] = field(default_factory=list)
    tacacs_profiles: list[TacacsServerProfile] = field(default_factory=list)
    snmp_profiles: list[SnmpProfile] = field(default_factory=list)
    syslog_profiles: list[SyslogServerProfile] = field(default_factory=list)
    ntp_profiles: list[NtpProfile] = field(default_factory=list)  # 0 or 1 entries in practice
    dns_profiles: list[DnsProfile] = field(default_factory=list)  # 0 or 1 entries in practice

    def stats(self) -> dict:
        return {
            "addresses": len(self.addresses),
            "address_groups": len(self.address_groups),
            "services": len(self.services),
            "service_groups": len(self.service_groups),
            "interfaces": len(self.interfaces),
            "zones": len(self.zones),
            "routes": len(self.routes),
            "nat_rules": len(self.nat_rules),
            "policies": len(self.policies),
            "ldap_profiles": len(self.ldap_profiles),
            "radius_profiles": len(self.radius_profiles),
            "tacacs_profiles": len(self.tacacs_profiles),
            "snmp_profiles": len(self.snmp_profiles),
            "syslog_profiles": len(self.syslog_profiles),
            "ntp_profiles": len(self.ntp_profiles),
            "dns_profiles": len(self.dns_profiles),
            "warnings": len([i for i in self.issues if i.severity == "warning"]),
            "errors": len([i for i in self.issues if i.severity == "error"]),
            "unsupported": len([i for i in self.issues if i.severity == "unsupported"]),
            "information": len([i for i in self.issues if i.severity == "information"]),
        }
