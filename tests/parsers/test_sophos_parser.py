import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.parsers.sophos.parser import SophosXGParser
from app.normalizer.models import AddressType, ServiceProtocol, PolicyAction

SAMPLE_PATH = Path(__file__).resolve().parents[2] / "samples" / "sophos_xg_sample.export"


def _parse():
    text = SAMPLE_PATH.read_text()
    return SophosXGParser(raw_text=text, filename="sophos_xg_sample.export").parse()


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
    assert svcs["PING"].protocol == ServiceProtocol.ICMP
    assert svcs["PING"].icmp_type == 8


def test_service_group_parsed():
    cfg = _parse()
    groups = {g.name: g for g in cfg.service_groups}
    assert set(groups["WebServices"].members) == {"HTTPS_8443", "DNS_UDP"}


def test_interfaces_parsed_with_native_zone():
    cfg = _parse()
    ifaces = {i.name: i for i in cfg.interfaces}
    assert ifaces["Port1"].ip_address == "192.168.1.1"
    assert ifaces["Port1"].netmask == "255.255.255.0"
    assert ifaces["Port1"].zone == "LAN"
    assert ifaces["Port2"].zone == "WAN"
    assert ifaces["Port1"].mtu == 1500


def test_routes_parsed():
    cfg = _parse()
    assert len(cfg.routes) == 1
    r = cfg.routes[0]
    assert r.destination == "0.0.0.0/0"
    assert r.next_hop == "203.0.113.254"
    assert r.interface == "Port2"


def test_policies_parsed():
    cfg = _parse()
    assert len(cfg.policies) == 2
    allow_rule = next(p for p in cfg.policies if p.name == "Allow_LAN_to_WebServers")
    assert allow_rule.action == PolicyAction.ALLOW
    assert allow_rule.source_zone == ["LAN"]
    assert allow_rule.dest_zone == ["WAN"]
    assert allow_rule.source_address == ["InternalNet"]
    assert allow_rule.dest_address == ["WebServers"]
    assert allow_rule.service == ["WebServices"]

    deny_rule = next(p for p in cfg.policies if p.name == "Deny_All_Else")
    assert deny_rule.action == PolicyAction.DENY
    # Sophos XML spells its wildcard 'Any' (capitalized) - should be
    # normalized to the tool-wide lowercase 'any' convention so the
    # interface mapping step's "any" special-case actually matches.
    assert deny_rule.source_zone == ["any"]
    assert deny_rule.dest_zone == ["any"]
    assert deny_rule.source_address == ["any"]


def test_nat_rules_parsed():
    cfg = _parse()
    assert len(cfg.nat_rules) == 2
    snat = next(n for n in cfg.nat_rules if n.name == "SNAT_Internal_Out")
    assert snat.translated_source == "interface"
    assert snat.dest_zone == "Port2"  # named outbound interface, unlike Check Point's hide-behind-gateway

    dnat = next(n for n in cfg.nat_rules if n.name == "DNAT_WebServer")
    assert dnat.translated_dest == "Server01"
    assert dnat.nat_type == "static"


def test_no_errors_for_well_formed_sample():
    cfg = _parse()
    errors = [i for i in cfg.issues if i.severity == "error"]
    assert errors == [], f"Unexpected parser errors: {errors}"


def test_malformed_xml_reported_as_error_not_crash():
    parser = SophosXGParser(raw_text="<Configuration><IPHost><Name>Broken</Configuration>", filename="bad.xml")
    cfg = parser.parse()
    assert any(i.severity == "error" for i in cfg.issues)
