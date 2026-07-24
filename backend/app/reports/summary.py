"""
Configuration Summary
=======================
Turns a parsed NormalizedConfig into flat, table-ready rows per object
type - addresses, address groups, services, service groups, policies,
NAT rules. Used both by GET /api/jobs/{id}/summary (JSON, for the UI
table) and the Excel export, so the two never drift out of sync.
"""

from __future__ import annotations

from app.normalizer.models import NormalizedConfig


def address_rows(config: NormalizedConfig) -> list[dict]:
    return [
        {
            "Name": a.name,
            "Type": a.type.value,
            "Value": a.value,
            "Description": a.description,
        }
        for a in config.addresses
    ]


def address_group_rows(config: NormalizedConfig) -> list[dict]:
    return [
        {
            "Name": g.name,
            "Members": ", ".join(g.members),
            "Member Count": len(g.members),
            "Description": g.description,
        }
        for g in config.address_groups
    ]


def service_rows(config: NormalizedConfig) -> list[dict]:
    rows = []
    for s in config.services:
        if s.protocol.value in ("icmp", "icmp6"):
            detail = f"type={s.icmp_type if s.icmp_type is not None else 'any'}"
        else:
            detail = s.dest_port or "any"
        rows.append({
            "Name": s.name,
            "Protocol": s.protocol.value,
            "Port / Detail": detail,
            "Description": s.description,
        })
    return rows


def service_group_rows(config: NormalizedConfig) -> list[dict]:
    return [
        {
            "Name": g.name,
            "Members": ", ".join(g.members),
            "Member Count": len(g.members),
            "Description": g.description,
        }
        for g in config.service_groups
    ]


def policy_rows(config: NormalizedConfig) -> list[dict]:
    return [
        {
            "Name": p.name,
            "Source Zone": ", ".join(p.source_zone),
            "Dest Zone": ", ".join(p.dest_zone),
            "Source Address": ", ".join(p.source_address),
            "Dest Address": ", ".join(p.dest_address),
            "Service": ", ".join(p.service),
            "Action": p.action.value,
            "Disabled": p.disabled,
            "Description": p.description,
        }
        for p in config.policies
    ]


def nat_rule_rows(config: NormalizedConfig) -> list[dict]:
    return [
        {
            "Name": n.name,
            "Source Address": ", ".join(n.source_address),
            "Dest Address": ", ".join(n.dest_address),
            "Translated Source": n.translated_source or "",
            "Translated Dest": n.translated_dest or "",
            "NAT Type": n.nat_type,
            "Disabled": n.disabled,
        }
        for n in config.nat_rules
    ]


def interface_rows(config: NormalizedConfig) -> list[dict]:
    return [
        {
            "Name": i.name,
            "Hardware Name": i.hardware_name or "",
            "IP Address": i.ip_address or "",
            "Netmask": i.netmask or "",
            "Suggested Zone": i.zone or "",
            "Description": i.description,
        }
        for i in config.interfaces
    ]


def route_rows(config: NormalizedConfig) -> list[dict]:
    return [
        {
            "Name": r.name or "",
            "Destination": r.destination,
            "Next Hop": r.next_hop or "",
            "Interface": r.interface or "",
            "Metric": r.metric if r.metric is not None else "",
        }
        for r in config.routes
    ]


def build_summary(config: NormalizedConfig) -> dict:
    """Returns {counts: {...}, tables: {category: [row, ...]}}."""
    return {
        "counts": config.stats(),
        "tables": {
            "addresses": address_rows(config),
            "address_groups": address_group_rows(config),
            "services": service_rows(config),
            "service_groups": service_group_rows(config),
            "interfaces": interface_rows(config),
            "routes": route_rows(config),
            "policies": policy_rows(config),
            "nat_rules": nat_rule_rows(config),
        },
    }
