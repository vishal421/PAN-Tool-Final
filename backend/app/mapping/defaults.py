"""
Default (legacy) mapping - a convenience auto-mapping used only by the
one-shot /api/convert endpoint for people who skip the interface mapping
wizard entirely. It assigns PAN interfaces sequentially and uses the
parser's suggested zone (Interface.zone) as-is.

This intentionally still "assumes" a zone, which is exactly what the
wizard exists to avoid - so results from this path are lower-fidelity by
design. It exists for quick/throwaway testing, not production migrations.
"""

from __future__ import annotations

from app.normalizer.models import NormalizedConfig
from app.mapping.apply import InterfaceMappingEntry


def build_default_mapping(config: NormalizedConfig) -> list[InterfaceMappingEntry]:
    entries = []
    for idx, iface in enumerate(config.interfaces, start=1):
        entries.append(InterfaceMappingEntry(
            source_interface=iface.name,
            pan_interface=f"ethernet1/{idx}",
            zone=iface.zone or iface.name,
            virtual_router=iface.virtual_router or "default",
            interface_type="layer3",
            ip_address=iface.ip_address,
            netmask=iface.netmask,
            description=iface.description,
            enabled=iface.enabled,
        ))
    return entries
