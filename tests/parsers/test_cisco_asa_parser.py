import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.parsers.cisco.parser import CiscoASAParser
from app.normalizer.models import AddressType, ServiceProtocol, PolicyAction

SAMPLE_PATH = Path(__file__).resolve().parents[2] / "samples" / "cisco_asa_sample.cfg"


def _parse():
    text = SAMPLE_PATH.read_text()
    return CiscoASAParser(raw_text=text, filename="cisco_asa_sample.cfg").parse()


def test_addresses_parsed():
    cfg = _parse()
    names = {a.name: a for a in cfg.addresses}
    assert names["SERVER01"].type == AddressType.IP_NETMASK
    assert names["SERVER01"].value == "10.10.10.10/32"

    assert names["INTERNAL_NET"].value == "192.168.1.0/24"

    assert names["DHCP_RANGE"].type == AddressType.IP_RANGE
    assert names["DHCP_RANGE"].value == "10.20.0.10-10.20.0.50"

    assert names["PUBLIC_DNS"].type == AddressType.FQDN
    assert names["PUBLIC_DNS"].value == "dns.example.com"


def test_address_group_parsed():
    cfg = _parse()
    groups = {g.name: g for g in cfg.address_groups}
    assert set(groups["WEB_SERVERS"].members) == {"SERVER01", "SERVER02"}


def test_services_parsed():
    cfg = _parse()
    svcs = {s.name: s for s in cfg.services}
    assert svcs["HTTPS_8443"].protocol == ServiceProtocol.TCP
    assert svcs["HTTPS_8443"].dest_port == "8443"
    assert svcs["DNS_UDP"].protocol == ServiceProtocol.UDP
    assert svcs["DNS_UDP"].dest_port == "53"


def test_service_group_parsed_with_synthesized_members():
    cfg = _parse()
    groups = {g.name: g for g in cfg.service_groups}
    assert "WEB_SERVICES" in groups
    assert len(groups["WEB_SERVICES"].members) == 2
    # port-object entries get synthesized service objects since ASA allows
    # inline ports with no standalone `object service` definition
    svc_names = {s.name for s in cfg.services}
    assert set(groups["WEB_SERVICES"].members).issubset(svc_names)


def test_interfaces_parsed():
    cfg = _parse()
    ifaces = {i.name: i for i in cfg.interfaces}
    inside = ifaces["inside"]
    assert inside.hardware_name == "GigabitEthernet0/0"
    assert inside.ip_address == "192.168.1.1"
    assert inside.mtu == 1500

    outside = ifaces["outside"]
    assert outside.hardware_name == "GigabitEthernet0/1"


def test_routes_parsed():
    cfg = _parse()
    assert len(cfg.routes) == 1
    r = cfg.routes[0]
    assert r.destination == "0.0.0.0/0"
    assert r.next_hop == "203.0.113.254"
    assert r.interface == "outside"


def test_acl_policies_parsed_with_zone_from_access_group():
    cfg = _parse()
    assert len(cfg.policies) == 3

    https_rule = next(p for p in cfg.policies if "OUTSIDE_IN_1" == p.name)
    assert https_rule.action == PolicyAction.ALLOW
    # bound via `access-group OUTSIDE_IN in interface outside`
    assert https_rule.dest_zone == ["outside"]
    assert https_rule.source_zone == ["any"]
    assert https_rule.dest_address == ["SERVER01"]
    assert https_rule.service == ["tcp/8443"]

    deny_rule = next(p for p in cfg.policies if p.name == "OUTSIDE_IN_3")
    assert deny_rule.action == PolicyAction.DENY


def test_no_errors_for_well_formed_sample():
    cfg = _parse()
    errors = [i for i in cfg.issues if i.severity == "error"]
    assert errors == [], f"Unexpected parser errors: {errors}"


def test_object_nat_parsed():
    cfg = _parse()
    static_nats = [n for n in cfg.nat_rules if n.nat_type == "static"]
    assert len(static_nats) == 1
    nat = static_nats[0]
    # Object NAT `static` is a 1:1, bidirectional NAT - modeled primarily as
    # the destination-NAT half (so inbound traffic to the mapped address is
    # actually translated back to the real host) with bidirectional/
    # nat_method flags set so the generator also notes the reverse leg.
    assert nat.dest_address == ["203.0.113.10"]
    assert nat.translated_dest == "SERVER01"
    assert nat.nat_method == "bidirectional"
    assert nat.bidirectional is True
    assert nat.source_zone == ["any"]
    assert nat.dest_zone == "outside"


def test_manual_nat_parsed():
    cfg = _parse()
    dynamic_nats = [n for n in cfg.nat_rules if n.nat_type == "dynamic-ip-and-port"]
    assert len(dynamic_nats) == 1
    nat = dynamic_nats[0]
    assert nat.source_address == ["INTERNAL_NET"]
    assert nat.translated_source == "interface"
    assert nat.source_zone == ["inside"]
    assert nat.dest_zone == "outside"
