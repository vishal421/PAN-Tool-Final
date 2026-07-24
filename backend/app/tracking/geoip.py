"""
GeoIP lookup, abstracted behind a single `lookup(ip)` function so the
provider can be swapped (e.g. for a local MaxMind GeoLite2 database, per
the "Future-Ready Design" requirement) without touching any calling code.

Deliberately fails soft: any network error, timeout, private/loopback IP,
or disabled provider just returns an all-None result rather than raising -
a broken GeoIP lookup should never take down pageview tracking.
"""

from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass
from functools import lru_cache

import httpx

from app.core.config import settings

logger = logging.getLogger("app.tracking.geoip")


@dataclass(frozen=True)
class GeoLocation:
    country: str | None = None   # ISO2
    region: str | None = None
    city: str | None = None
    timezone: str | None = None


_EMPTY = GeoLocation()


def _is_public(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved)


@lru_cache(maxsize=4096)
def _lookup_ip_api(ip: str) -> GeoLocation:
    try:
        resp = httpx.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,countryCode,regionName,city,timezone"},
            timeout=settings.geoip_timeout_seconds,
        )
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.debug("GeoIP lookup failed for %s: %s", ip, exc)
        return _EMPTY

    if data.get("status") != "success":
        return _EMPTY
    return GeoLocation(
        country=data.get("countryCode"),
        region=data.get("regionName"),
        city=data.get("city"),
        timezone=data.get("timezone"),
    )


def lookup(ip: str | None) -> GeoLocation:
    """Best-effort GeoIP lookup. Returns an all-None GeoLocation on any failure."""
    if not ip or settings.geoip_provider == "none" or not _is_public(ip):
        return _EMPTY
    if settings.geoip_provider == "ip-api":
        return _lookup_ip_api(ip)
    logger.warning("Unknown GEOIP_PROVIDER=%s - location lookups disabled.", settings.geoip_provider)
    return _EMPTY
