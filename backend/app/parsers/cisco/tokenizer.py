"""
Cisco ASA Tokenizer
====================
ASA config syntax is indentation-based rather than block-delimited:

    object network SERVER01
     host 10.10.10.10
    object-group network DMZ_HOSTS
     network-object object SERVER01
     network-object host 10.10.10.20
    interface GigabitEthernet0/1
     nameif outside
     security-level 0
     ip address 203.0.113.1 255.255.255.0

Any line beginning with whitespace is a child of the nearest preceding
non-indented "parent" line. This module walks that structure explicitly
(not regex-only) and is resilient to comments (`!`), blank lines, and
extra/irregular indentation depth (ASA exports aren't always consistent
about one-space vs multi-space indents, so we don't rely on exact depth -
just "indented or not").
"""

from __future__ import annotations

import shlex


def group_lines(text: str) -> list[tuple[str, list[str]]]:
    """
    Returns a list of (parent_line, [child_lines]) tuples in document order.
    Comments (`!`) and blank lines are dropped. Parent lines are top-level
    (no leading whitespace); child lines are anything indented, attached to
    the most recent parent.
    """
    groups: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None

    for raw in text.splitlines():
        if not raw.strip():
            continue
        if raw.strip().startswith("!"):
            continue
        if raw[0] not in (" ", "\t"):
            current = (raw.strip(), [])
            groups.append(current)
        else:
            if current is not None:
                current[1].append(raw.strip())
            # else: an indented line before any parent - malformed/truncated
            # export; silently skip rather than crash the whole parse.
    return groups


def tokens(line: str) -> list[str]:
    """Shlex-split a single ASA command line, tolerating unbalanced quotes."""
    try:
        return shlex.split(line)
    except ValueError:
        return line.split()
