"""
Check Point Tokenizer
======================
Real-world Check Point migrations typically combine two different export
sources into one bundle:

  1. Management API (`mgmt_cli`) commands for the security policy database -
     objects, services, groups, access rules, NAT rules:
         add host name "Server01" ip-address "10.10.10.10"
         add access-rule layer "Network" name "Rule1" source "Internal" ...

  2. Gaia OS `clish` commands (from `show configuration`) for the gateway's
     own interfaces and routing:
         set interface eth0 ipv4-address 192.168.1.1 mask-length 24
         set static-route 0.0.0.0/0 nexthop gateway address 203.0.113.254 priority 1

This module tokenizes both styles. Neither is block-structured (unlike
FortiGate) - every command is a single line - so this is a straight
shlex-based tokenizer rather than a nested-block parser, but it's still a
real tokenizer (not string-splitting on assumed positions), so it copes
with quoted values containing spaces and comma-separated member lists.
"""

from __future__ import annotations

import shlex


def strip_noise(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        lines.append(line)
    return lines


def tokenize_line(line: str) -> list[str]:
    try:
        return shlex.split(line)
    except ValueError:
        return line.split()


def parse_mgmt_cli_fields(tokens: list[str]) -> dict[str, list[str]]:
    """
    `add host name "Server01" ip-address "10.10.10.10"` -> tokens[0]='add',
    tokens[1]='host', then alternating key/value pairs. Repeated keys (e.g.
    multiple `members "X"` entries) accumulate into a list, which also
    naturally handles the comma-separated shorthand some exports use
    (`members "A,B"`) once split by the caller.

    Returns {key: [value1, value2, ...]}.
    """
    fields: dict[str, list[str]] = {}
    i = 2  # skip 'add' and the object-type token
    n = len(tokens)
    while i < n - 1:
        key, value = tokens[i], tokens[i + 1]
        fields.setdefault(key, []).append(value)
        i += 2
    return fields


def split_member_list(values: list[str]) -> list[str]:
    """Flattens repeated-key values and comma-separated shorthand into one list."""
    out: list[str] = []
    for v in values:
        out.extend([m.strip() for m in v.split(",") if m.strip()])
    return out
