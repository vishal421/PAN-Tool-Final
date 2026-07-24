"""User-agent parsing: browser, browser version, OS, and device type."""

from __future__ import annotations

from dataclasses import dataclass

from user_agents import parse as _parse_ua


@dataclass(frozen=True)
class DeviceInfo:
    browser: str | None = None
    browser_version: str | None = None
    os: str | None = None
    device_type: str = "desktop"  # desktop | mobile | tablet | bot


def parse_user_agent(ua_string: str | None) -> DeviceInfo:
    if not ua_string:
        return DeviceInfo(device_type="unknown")

    ua = _parse_ua(ua_string)

    if ua.is_bot:
        device_type = "bot"
    elif ua.is_tablet:
        device_type = "tablet"
    elif ua.is_mobile:
        device_type = "mobile"
    else:
        device_type = "desktop"

    version = ".".join(str(v) for v in ua.browser.version) if ua.browser.version else None

    return DeviceInfo(
        browser=ua.browser.family or None,
        browser_version=version,
        os=(ua.os.family or None),
        device_type=device_type,
    )
