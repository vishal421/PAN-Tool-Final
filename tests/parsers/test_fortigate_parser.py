import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.parsers.fortigate.parser import FortiGateParser
from app.normalizer.models import AddressType, ServiceProtocol, PolicyAction

SAMPLE_PATH = Path(__file__).resolve().parents[2] / "samples" / "fortigate_sample.conf"


def _parse():
    text = SAMPLE_PATH.read_text()
    return FortiGateParser(raw_text=text, filename="fortigate_sample.conf").parse()


def test_addresses_parsed():
    cfg = _parse()
    names = {a.name: a for a in cfg.addresses}
    assert "Server01" in names
    assert names["Server01"].type == AddressType.IP_NETMASK
    assert names["Server01"].value == "10.10.10.10/32"

    assert names["InternalNet"].value == "192.168.1.0/24"

    assert names["PublicDNS"].type == AddressType.FQDN
    assert names["PublicDNS"].value == "dns.example.com"

    assert names["DHCPRange1"].type == AddressType.IP_RANGE
    assert names["DHCPRange1"].value == "10.20.0.10-10.20.0.50"


def test_address_group_parsed():
    cfg = _parse()
    groups = {g.name: g for g in cfg.address_groups}
    assert "WebServers" in groups
    assert set(groups["WebServers"].members) == {"Server01", "Server02"}


def test_services_parsed():
    cfg = _parse()
    svcs = {s.name: s for s in cfg.services}
    assert svcs["HTTPS_8443"].protocol == ServiceProtocol.TCP
    assert svcs["HTTPS_8443"].dest_port == "8443"
    assert svcs["DNS_UDP"].protocol == ServiceProtocol.UDP
    assert svcs["DNS_UDP"].dest_port == "53"
    assert svcs["PING"].protocol == ServiceProtocol.ICMP
    assert svcs["PING"].icmp_type == 8


def test_service_group_parsed():
    cfg = _parse()
    groups = {g.name: g for g in cfg.service_groups}
    assert set(groups["WebServices"].members) == {"HTTPS_8443", "DNS_UDP"}


def test_interfaces_and_zones_parsed():
    cfg = _parse()
    ifaces = {i.name: i for i in cfg.interfaces}
    assert ifaces["port1"].ip_address == "192.168.1.1"
    assert ifaces["port1"].netmask == "255.255.255.0"
    assert ifaces["port1"].zone == "LAN"
    assert ifaces["port2"].zone == "WAN"
    assert ifaces["port1"].mtu == 1500


def test_routes_parsed():
    cfg = _parse()
    assert len(cfg.routes) == 1
    r = cfg.routes[0]
    assert r.destination == "0.0.0.0/0"
    assert r.next_hop == "203.0.113.254"
    assert r.interface == "port2"


def test_policies_parsed():
    cfg = _parse()
    assert len(cfg.policies) == 2
    allow_rule = next(p for p in cfg.policies if p.name == "Allow_LAN_to_WebServers")
    assert allow_rule.action == PolicyAction.ALLOW
    assert allow_rule.source_address == ["InternalNet"]
    assert allow_rule.dest_address == ["WebServers"]
    assert allow_rule.service == ["WebServices"]
    # The parser intentionally does NOT auto-resolve srcintf/dstintf to a
    # zone - PAN-OS is zone-based while FortiGate policies are interface-
    # based, and the tool defers that translation to the user-confirmed
    # interface mapping step rather than guessing.
    assert allow_rule.source_zone == ["port1"]
    assert allow_rule.dest_zone == ["port2"]

    deny_rule = next(p for p in cfg.policies if p.name == "Deny_All_Else")
    assert deny_rule.action == PolicyAction.DENY
    assert deny_rule.source_zone == ["any"]
    assert deny_rule.dest_zone == ["any"]


def test_policy_nat_parsed():
    cfg = _parse()
    snat_rules = [n for n in cfg.nat_rules if n.nat_type == "dynamic-ip-and-port"]
    assert len(snat_rules) == 1
    nat = snat_rules[0]
    assert nat.translated_source == "interface"
    assert nat.source_zone == ["port1"]
    assert nat.dest_zone == "port2"


def test_vip_dnat_parsed():
    cfg = _parse()
    dnat_rules = [n for n in cfg.nat_rules if n.nat_type == "static"]
    assert len(dnat_rules) == 1
    vip = dnat_rules[0]
    assert vip.name == "DMZ_WebServer_VIP"
    assert vip.dest_address == ["203.0.113.50"]
    assert vip.translated_dest == "10.10.10.10"
    assert vip.dest_zone == "port2"


def test_no_errors_for_well_formed_sample():
    cfg = _parse()
    errors = [i for i in cfg.issues if i.severity == "error"]
    assert errors == [], f"Unexpected parser errors: {errors}"
