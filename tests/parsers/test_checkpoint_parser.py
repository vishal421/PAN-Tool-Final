import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.parsers.checkpoint.parser import CheckPointParser
from app.normalizer.models import AddressType, ServiceProtocol, PolicyAction

SAMPLE_PATH = Path(__file__).resolve().parents[2] / "samples" / "checkpoint_sample.txt"


def _parse():
    text = SAMPLE_PATH.read_text()
    return CheckPointParser(raw_text=text, filename="checkpoint_sample.txt").parse()


def test_addresses_parsed():
    cfg = _parse()
    names = {a.name: a for a in cfg.addresses}
    assert names["Server01"].type == AddressType.IP_NETMASK
    assert names["Server01"].value == "10.10.10.10/32"

    assert names["InternalNet"].value == "192.168.1.0/24"

    assert names["DHCPRange1"].type == AddressType.IP_RANGE
    assert names["DHCPRange1"].value == "10.20.0.10-10.20.0.50"

    assert names["PublicDNS"].type == AddressType.FQDN
    assert names["PublicDNS"].value == "dns.example.com"


def test_address_group_parsed():
    cfg = _parse()
    groups = {g.name: g for g in cfg.address_groups}
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


def test_interfaces_parsed_with_security_zone_hint():
    cfg = _parse()
    ifaces = {i.name: i for i in cfg.interfaces}
    assert ifaces["eth0"].ip_address == "192.168.1.1"
    assert ifaces["eth0"].netmask == "24"
    assert ifaces["eth0"].zone == "Internal"
    assert ifaces["eth0"].mtu == 1500
    assert ifaces["eth1"].zone == "External"


def test_routes_parsed():
    cfg = _parse()
    assert len(cfg.routes) == 1
    r = cfg.routes[0]
    assert r.destination == "0.0.0.0/0"
    assert r.next_hop == "203.0.113.254"
    assert r.metric == 1


def test_policies_parsed_without_zone_assumption():
    cfg = _parse()
    assert len(cfg.policies) == 2
    allow_rule = next(p for p in cfg.policies if p.name == "Allow_LAN_to_WebServers")
    assert allow_rule.action == PolicyAction.ALLOW
    assert allow_rule.source_address == ["InternalNet"]
    assert allow_rule.dest_address == ["WebServers"]
    assert allow_rule.service == ["WebServices"]
    # Check Point Standard-layer rules aren't interface/zone-bound - should
    # stay "any", not get a fabricated zone the way FortiGate/Cisco would
    # need mapping for.
    assert allow_rule.source_zone == ["any"]
    assert allow_rule.dest_zone == ["any"]

    deny_rule = next(p for p in cfg.policies if p.name == "Deny_All_Else")
    assert deny_rule.action == PolicyAction.DROP


def test_nat_rules_parsed():
    cfg = _parse()
    assert len(cfg.nat_rules) == 2
    hide_nat = next(n for n in cfg.nat_rules if n.nat_type == "dynamic-ip-and-port")
    assert hide_nat.translated_source == "interface"
    assert hide_nat.source_address == ["InternalNet"]

    static_nat = next(n for n in cfg.nat_rules if n.nat_type == "static")
    # Check Point static NAT is automatically bidirectional - modeled
    # primarily as the destination-NAT half (so inbound traffic to the
    # translated address is actually translated back to the real host),
    # with bidirectional/nat_method flags set so the generator also notes
    # the reverse (outbound) leg.
    assert static_nat.dest_address == ["203.0.113.10"]
    assert static_nat.translated_dest == "Server01"
    assert static_nat.nat_method == "bidirectional"
    assert static_nat.bidirectional is True


def test_no_errors_for_well_formed_sample():
    cfg = _parse()
    errors = [i for i in cfg.issues if i.severity == "error"]
    assert errors == [], f"Unexpected parser errors: {errors}"
