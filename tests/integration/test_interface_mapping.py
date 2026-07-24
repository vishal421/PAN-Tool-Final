import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.mapping.apply import InterfaceMappingEntry, validate_mapping, apply_mapping
from app.mapping.defaults import build_default_mapping
from app.normalizer.models import (
    NormalizedConfig, Interface, Policy, PolicyAction, NATRule, Route,
)


def _sample_config():
    cfg = NormalizedConfig()
    cfg.interfaces = [
        Interface(name="port1", ip_address="192.168.1.1", netmask="255.255.255.0"),
        Interface(name="port2", ip_address="203.0.113.1", netmask="255.255.255.0"),
    ]
    cfg.policies = [
        Policy(name="rule1", source_zone=["port1"], dest_zone=["port2"],
               source_address=["any"], dest_address=["any"], service=["any"],
               action=PolicyAction.ALLOW),
    ]
    cfg.nat_rules = [
        NATRule(name="nat1", source_zone=["port1"], dest_zone="port2",
                translated_source="interface", nat_type="dynamic-ip-and-port"),
    ]
    cfg.routes = [
        Route(name="default", destination="0.0.0.0/0", next_hop="203.0.113.254", interface="port2"),
    ]
    return cfg


def _full_mapping():
    return [
        InterfaceMappingEntry(source_interface="port1", pan_interface="ethernet1/1",
                               zone="LAN", virtual_router="default", ip_address="192.168.1.1",
                               netmask="255.255.255.0"),
        InterfaceMappingEntry(source_interface="port2", pan_interface="ethernet1/2",
                               zone="WAN", virtual_router="default", ip_address="203.0.113.1",
                               netmask="255.255.255.0"),
    ]


def test_validate_flags_unmapped_interface():
    cfg = _sample_config()
    result = validate_mapping(cfg, [_full_mapping()[0]])  # only port1 mapped
    assert result.blocking
    assert any(i.object_name == "port2" for i in result.errors)


def test_validate_flags_duplicate_pan_interface():
    cfg = _sample_config()
    mappings = _full_mapping()
    mappings[1].pan_interface = "ethernet1/1"  # collide with port1's assignment
    result = validate_mapping(cfg, mappings)
    assert result.blocking
    assert any("already assigned" in i.message for i in result.errors)


def test_validate_flags_invalid_ip():
    cfg = _sample_config()
    mappings = _full_mapping()
    mappings[0].ip_address = "not-an-ip"
    result = validate_mapping(cfg, mappings)
    assert result.blocking
    assert any("Invalid IP" in i.message for i in result.errors)


def test_validate_passes_on_complete_mapping():
    cfg = _sample_config()
    result = validate_mapping(cfg, _full_mapping())
    assert not result.blocking
    assert result.errors == []


def test_apply_mapping_rewrites_everything():
    cfg = _sample_config()
    apply_mapping(cfg, _full_mapping())

    ifaces = {i.name: i for i in cfg.interfaces}
    assert ifaces["port1"].pan_name == "ethernet1/1"
    assert ifaces["port1"].zone == "LAN"
    assert ifaces["port2"].pan_name == "ethernet1/2"
    assert ifaces["port2"].zone == "WAN"

    # Zones rebuilt from the mapping
    zone_names = {z.name for z in cfg.zones}
    assert zone_names == {"LAN", "WAN"}

    # Policy zones rewritten from raw interface names to mapped zone names
    rule = cfg.policies[0]
    assert rule.source_zone == ["LAN"]
    assert rule.dest_zone == ["WAN"]

    # NAT rewritten: zones translated, and the 'interface' SNAT marker
    # resolved to the mapped egress interface's PAN name
    nat = cfg.nat_rules[0]
    assert nat.source_zone == ["LAN"]
    assert nat.dest_zone == "WAN"
    assert nat.translated_source == "interface:ethernet1/2"

    # Route interface/VR rewritten
    route = cfg.routes[0]
    assert route.interface == "ethernet1/2"
    assert route.virtual_router == "default"


def test_default_mapping_covers_every_interface():
    cfg = _sample_config()
    mapping = build_default_mapping(cfg)
    assert {m.source_interface for m in mapping} == {"port1", "port2"}
    result = validate_mapping(cfg, mapping)
    assert not result.blocking
