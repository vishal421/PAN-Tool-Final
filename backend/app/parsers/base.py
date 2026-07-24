"""
BaseParser
==========
Every vendor parser inherits this. A new vendor should only need to:

  1. Create app/parsers/<vendor>/parser.py subclassing BaseParser
  2. Implement the five parse_* methods (return normalized objects)
  3. Register the class in app/parsers/registry.py

No other code should need to change. The API layer, generator, and
frontend all work off the vendor registry + NormalizedConfig, never
off a hardcoded vendor list.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

from app.normalizer.models import (
    AddressObject,
    AddressGroup,
    ServiceObject,
    ServiceGroup,
    Interface,
    Zone,
    Route,
    NATRule,
    Policy,
    ConversionIssue,
    NormalizedConfig,
)


class BaseParser(ABC):
    """
    Contract for a vendor configuration parser.

    Implementations must be resilient to: comments, blank lines,
    duplicate object names, forward references (object used before
    defined), nested groups, quoted names with spaces/special
    characters, and multi-line blocks. Prefer a real tokenizer/state
    machine over ad-hoc regex for anything block-structured.
    """

    vendor_key: str = "base"       # short machine key, e.g. "fortigate"
    vendor_label: str = "Base"     # display name, e.g. "FortiGate"

    def __init__(self, raw_text: str, filename: str = ""):
        self.raw_text = raw_text
        self.filename = filename
        self.logger = logging.getLogger(f"parser.{self.vendor_key}")
        self.issues: list[ConversionIssue] = []

    # ---- required per-vendor implementations -----------------------
    @abstractmethod
    def parse_addresses(self) -> tuple[list[AddressObject], list[AddressGroup]]:
        """Return (address objects, address groups) including FQDN objects."""
        raise NotImplementedError

    @abstractmethod
    def parse_services(self) -> tuple[list[ServiceObject], list[ServiceGroup]]:
        """Return (service objects, service groups)."""
        raise NotImplementedError

    @abstractmethod
    def parse_interfaces(self) -> tuple[list[Interface], list[Zone]]:
        """Return (interfaces, zones)."""
        raise NotImplementedError

    @abstractmethod
    def parse_routes(self) -> list[Route]:
        raise NotImplementedError

    @abstractmethod
    def parse_policies(self) -> tuple[list[Policy], list[NATRule]]:
        """Return (security policies, NAT rules)."""
        raise NotImplementedError

    # ---- optional per-vendor implementation --------------------------
    def parse_system_profiles(self) -> dict:
        """
        Optional. Vendors that support it should return a dict with any of
        the keys: 'ldap_profiles', 'radius_profiles', 'tacacs_profiles',
        'snmp_profiles', 'syslog_profiles', 'ntp_profiles', 'dns_profiles'
        (each a list of the matching app.normalizer.models dataclass).
        Default (no override) means this vendor doesn't parse these yet -
        returning {} is always safe and changes nothing downstream.
        """
        return {}

    # ---- shared orchestration (do not override) ---------------------
    def parse(self) -> NormalizedConfig:
        """
        Runs the full parse pipeline and returns a NormalizedConfig.
        Catches per-stage exceptions so one broken section (e.g. a
        malformed policy block) doesn't take down the whole conversion -
        it's recorded as an error issue instead.
        """
        config = NormalizedConfig()
        stages = [
            ("addresses", self._stage_addresses, config),
            ("services", self._stage_services, config),
            ("interfaces", self._stage_interfaces, config),
            ("routes", self._stage_routes, config),
            ("policies", self._stage_policies, config),
            ("system_profiles", self._stage_system_profiles, config),
        ]
        for stage_name, stage_fn, cfg in stages:
            try:
                self.logger.info("Starting stage: %s", stage_name)
                stage_fn(cfg)
                self.logger.info("Completed stage: %s", stage_name)
            except Exception as exc:  # noqa: BLE001 - deliberately broad, isolate stage failures
                self.logger.exception("Stage %s failed", stage_name)
                config.issues.append(
                    ConversionIssue(
                        severity="error",
                        object_type=stage_name,
                        object_name="<stage>",
                        message=f"Parser stage '{stage_name}' raised an exception: {exc}",
                    )
                )

        config.issues.extend(self.issues)
        return config

    def _stage_addresses(self, config: NormalizedConfig) -> None:
        addrs, groups = self.parse_addresses()
        config.addresses.extend(addrs)
        config.address_groups.extend(groups)

    def _stage_services(self, config: NormalizedConfig) -> None:
        svcs, groups = self.parse_services()
        config.services.extend(svcs)
        config.service_groups.extend(groups)

    def _stage_interfaces(self, config: NormalizedConfig) -> None:
        ifaces, zones = self.parse_interfaces()
        config.interfaces.extend(ifaces)
        config.zones.extend(zones)

    def _stage_routes(self, config: NormalizedConfig) -> None:
        config.routes.extend(self.parse_routes())

    def _stage_policies(self, config: NormalizedConfig) -> None:
        policies, nat_rules = self.parse_policies()
        config.policies.extend(policies)
        config.nat_rules.extend(nat_rules)

    def _stage_system_profiles(self, config: NormalizedConfig) -> None:
        data = self.parse_system_profiles()
        if not data:
            return
        config.ldap_profiles.extend(data.get("ldap_profiles", []))
        config.radius_profiles.extend(data.get("radius_profiles", []))
        config.tacacs_profiles.extend(data.get("tacacs_profiles", []))
        config.snmp_profiles.extend(data.get("snmp_profiles", []))
        config.syslog_profiles.extend(data.get("syslog_profiles", []))
        config.ntp_profiles.extend(data.get("ntp_profiles", []))
        config.dns_profiles.extend(data.get("dns_profiles", []))

    # ---- helpers available to subclasses -----------------------------
    @staticmethod
    def derive_zones_from_interfaces(interfaces: list[Interface]) -> list[Zone]:
        """
        For vendors whose config format doesn't define a first-class zone
        object (Check Point, Sophos XG, Cisco ASA) but does carry a
        per-interface zone/nameif hint, build real Zone objects by
        grouping interfaces on that hint. This is what lets the Zones tab
        show "zones from the backup" for every vendor, not just FortiGate
        (which has a native `config system zone` block already handled
        separately in its own parser).
        """
        grouped: dict[str, list[str]] = {}
        for iface in interfaces:
            if not iface.zone:
                continue
            grouped.setdefault(iface.zone, []).append(iface.name)
        origin = interfaces[0].origin if interfaces else None
        return [Zone(name=zname, interfaces=members, origin=origin) for zname, members in grouped.items()]

    def warn(self, object_type: str, object_name: str, message: str, source_line: Optional[str] = None) -> None:
        self.issues.append(ConversionIssue("warning", object_type, object_name, message, source_line))

    def error(self, object_type: str, object_name: str, message: str, source_line: Optional[str] = None) -> None:
        self.issues.append(ConversionIssue("error", object_type, object_name, message, source_line))

    def unsupported(self, object_type: str, object_name: str, message: str, source_line: Optional[str] = None) -> None:
        self.issues.append(ConversionIssue("unsupported", object_type, object_name, message, source_line))
