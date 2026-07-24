"""
Configuration Cleanup
======================
A second, distinct kind of check from app.validation.engine: that module
asks "is this reference/name STRUCTURALLY VALID". This module asks "is
this object actually USED, and are there objects we could merge or
delete before export". Modeled after firewall Best-Practice-Assessment
(BPA) style cleanup reports.

Findings are grouped by category, each with a name, a human message, and
enough info for the frontend to offer "delete this" directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.normalizer.models import NormalizedConfig

_IGNORED_REFS = {"any", "all", "none"}


def _is_real_ref(name: str | None) -> bool:
    return bool(name) and name not in _IGNORED_REFS and not name.startswith("interface:")


@dataclass
class CleanupFinding:
    category: str        # unused_address | unused_address_group | unused_service |
                          # unused_service_group | empty_address_group | empty_service_group |
                          # duplicate_address | duplicate_service
    object_type: str      # addresses | address_groups | services | service_groups (matches EDITABLE_CATEGORIES)
    name: str
    message: str
    related: list[str] = field(default_factory=list)  # e.g. the other object names in a duplicate cluster


def _collect_address_refs(config: NormalizedConfig) -> set[str]:
    refs: set[str] = set()
    for g in config.address_groups:
        refs.update(m for m in g.members if _is_real_ref(m))
    for p in config.policies:
        refs.update(a for a in (p.source_address or []) if _is_real_ref(a))
        refs.update(a for a in (p.dest_address or []) if _is_real_ref(a))
    for n in config.nat_rules:
        refs.update(a for a in (n.source_address or []) if _is_real_ref(a))
        refs.update(a for a in (n.dest_address or []) if _is_real_ref(a))
        if _is_real_ref(n.translated_source):
            refs.add(n.translated_source)
        if _is_real_ref(n.translated_dest):
            refs.add(n.translated_dest)
    return refs


def _collect_service_refs(config: NormalizedConfig) -> set[str]:
    refs: set[str] = set()
    for g in config.service_groups:
        refs.update(m for m in g.members if _is_real_ref(m))
    for p in config.policies:
        refs.update(s for s in (p.service or []) if _is_real_ref(s))
    for n in config.nat_rules:
        if _is_real_ref(n.service):
            refs.add(n.service)
    return refs


def find_cleanup_issues(config: NormalizedConfig) -> list[CleanupFinding]:
    findings: list[CleanupFinding] = []

    address_refs = _collect_address_refs(config)
    # An address group counts as "used" both if directly referenced AND if
    # it's referenced only because it nests inside another group that's
    # itself used - but the simplest, still-correct rule here is: any name
    # appearing in _collect_address_refs (which already includes group
    # members of other groups) counts as used, regardless of whether that
    # referencing group is itself used. This intentionally slightly
    # under-reports "unused" (a chain of groups nested only inside each
    # other, referenced by nothing, would show as 'used' by each other) -
    # a safe bias for a delete-suggesting tool: never suggest deleting
    # something that's still referenced by ANYTHING else in the config.
    for a in config.addresses:
        if a.name not in address_refs:
            findings.append(CleanupFinding(
                "unused_address", "addresses", a.name,
                "Not referenced by any address group, security policy, or NAT rule.",
            ))
    for g in config.address_groups:
        if not g.members:
            findings.append(CleanupFinding(
                "empty_address_group", "address_groups", g.name, "This group has no members.",
            ))
        elif g.name not in address_refs:
            findings.append(CleanupFinding(
                "unused_address_group", "address_groups", g.name,
                "Not referenced by any security policy or NAT rule.",
            ))

    service_refs = _collect_service_refs(config)
    for s in config.services:
        if s.name not in service_refs:
            findings.append(CleanupFinding(
                "unused_service", "services", s.name,
                "Not referenced by any service group, security policy, or NAT rule.",
            ))
    for sg in config.service_groups:
        if not sg.members:
            findings.append(CleanupFinding(
                "empty_service_group", "service_groups", sg.name, "This group has no members.",
            ))
        elif sg.name not in service_refs:
            findings.append(CleanupFinding(
                "unused_service_group", "service_groups", sg.name,
                "Not referenced by any security policy or NAT rule.",
            ))

    # --- Duplicate-value clusters (candidates to merge, not delete outright) ---
    by_value: dict[tuple, list[str]] = {}
    for a in config.addresses:
        by_value.setdefault((a.type.value, a.value), []).append(a.name)
    for (_, _), names in by_value.items():
        if len(names) > 1:
            for n in names:
                others = [x for x in names if x != n]
                findings.append(CleanupFinding(
                    "duplicate_address", "addresses", n,
                    f"Same value as: {', '.join(others)} - consider merging into one object.",
                    related=others,
                ))

    by_svc_value: dict[tuple, list[str]] = {}
    for s in config.services:
        by_svc_value.setdefault((s.protocol.value, s.dest_port or "", s.source_port or ""), []).append(s.name)
    for _, names in by_svc_value.items():
        if len(names) > 1:
            for n in names:
                others = [x for x in names if x != n]
                findings.append(CleanupFinding(
                    "duplicate_service", "services", n,
                    f"Same protocol/port as: {', '.join(others)} - consider merging into one object.",
                    related=others,
                ))

    return findings
