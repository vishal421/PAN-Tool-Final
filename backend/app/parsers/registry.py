"""
Vendor Registry
===============
Single source of truth mapping a vendor key (as sent by the frontend)
to its parser class. Adding a new vendor in a later phase means:

  1. Implement app/parsers/<vendor>/parser.py
  2. Import + register it here

Nothing else in the API layer needs to change.
"""

from __future__ import annotations

from app.parsers.base import BaseParser

# Populated incrementally as each vendor parser is built (Phases 2-5).
# Kept as a plain dict (not a decorator-based registry) intentionally -
# explicit > implicit for a security-relevant conversion tool where you
# want to grep and see exactly what's registered.
_REGISTRY: dict[str, type[BaseParser]] = {}


def register(key: str, parser_cls: type[BaseParser]) -> None:
    _REGISTRY[key] = parser_cls


def get_parser_class(key: str) -> type[BaseParser] | None:
    return _REGISTRY.get(key)


def list_vendors() -> list[dict]:
    return [
        {"key": key, "label": cls.vendor_label}
        for key, cls in sorted(_REGISTRY.items())
    ]


# --- Vendor registrations ---------------------------------------------
from app.parsers.fortigate.parser import FortiGateParser
register("fortigate", FortiGateParser)

from app.parsers.cisco.parser import CiscoASAParser
register("cisco", CiscoASAParser)

from app.parsers.checkpoint.parser import CheckPointParser
register("checkpoint", CheckPointParser)

from app.parsers.sophos.parser import SophosXGParser
register("sophos", SophosXGParser)

from app.parsers.juniper.parser import JuniperSRXParser
register("juniper_srx", JuniperSRXParser)
