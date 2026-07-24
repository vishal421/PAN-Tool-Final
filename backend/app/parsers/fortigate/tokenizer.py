"""
FortiGate Block Tokenizer
==========================
FortiGate config exports use a nested block grammar:

    config <section>
        edit "<name>"
            set <key> <value...>
            config <nested-section>
                ...
            end
        next
    end

This module walks that grammar with explicit depth tracking (not
regex-only), so it's resilient to comments, blank lines, nested
sub-blocks inside an edit entry (e.g. `config ipv6` under an interface),
quoted names containing spaces, and duplicate edit names (both are
returned; the caller decides how to handle the duplicate).
"""

from __future__ import annotations

import shlex


def strip_noise(text: str) -> list[str]:
    """Remove comments and blank lines, return stripped non-empty lines."""
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def unquote(token: str) -> str:
    token = token.strip()
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        return token[1:-1]
    return token


def parse_set_line(line: str) -> tuple[str, list[str]]:
    """`set subnet 10.0.0.1 255.255.255.0` -> ('subnet', ['10.0.0.1', '255.255.255.0'])"""
    try:
        tokens = shlex.split(line)
    except ValueError:
        # Unbalanced quotes etc - fall back to naive split rather than crashing the stage
        tokens = line.split()
    # tokens[0] == 'set'
    key = tokens[1] if len(tokens) > 1 else ""
    values = tokens[2:]
    return key, values


def extract_top_config_block(lines: list[str], section_path: str) -> list[str]:
    """
    Find the first top-level `config <section_path>` ... `end` block
    (depth-balanced against nested config/end pairs) and return its
    inner lines, markers excluded.
    """
    target = f"config {section_path}"
    n = len(lines)
    i = 0
    while i < n:
        if lines[i] == target:
            depth = 1
            j = i + 1
            block: list[str] = []
            while j < n and depth > 0:
                if lines[j].startswith("config "):
                    depth += 1
                    block.append(lines[j])
                elif lines[j] == "end":
                    depth -= 1
                    if depth == 0:
                        break
                    block.append(lines[j])
                else:
                    block.append(lines[j])
                j += 1
            return block
        i += 1
    return []


def extract_flat_fields(block_lines: list[str]) -> dict[str, list[str]]:
    """
    Parse `set <key> <value...>` lines directly inside a flat (non-edit)
    config block, skipping over any nested `config ... end` sub-blocks.
    Used for singleton settings blocks that don't use `edit`/`next`
    entries, e.g. `config system dns`, `config system ntp`,
    `config system snmp sysinfo`, `config log syslogd setting`.
    """
    fields: dict[str, list[str]] = {}
    depth = 0
    for line in block_lines:
        if line.startswith("config "):
            depth += 1
            continue
        if line == "end":
            if depth > 0:
                depth -= 1
            continue
        if depth == 0 and line.startswith("set "):
            key, values = parse_set_line(line)
            fields[key] = values
    return fields


def extract_edit_entries(block_lines: list[str]) -> list[tuple[str, dict[str, list[str]], list[str]]]:
    """
    Within a config block's inner lines, extract top-level `edit "name"`
    ... `next` entries. Returns a list of (name, fields, nested_raw_lines).

    `fields` maps set-key -> value tokens for `set` lines directly inside
    the entry (not inside a nested config sub-block).
    `nested_raw_lines` preserves anything inside a nested config/end
    sub-block verbatim, for future use / unsupported-flagging - Version 1
    scope doesn't parse nested sub-blocks (e.g. per-interface IPv6 config).
    """
    entries: list[tuple[str, dict[str, list[str]], list[str]]] = []
    i, n = 0, len(block_lines)
    while i < n:
        line = block_lines[i]
        if line.startswith("edit "):
            name = unquote(line[len("edit "):].strip())
            fields: dict[str, list[str]] = {}
            nested_raw: list[str] = []
            depth_edit = 1
            depth_config = 0
            j = i + 1
            while j < n and depth_edit > 0:
                l = block_lines[j]
                if l.startswith("config "):
                    depth_config += 1
                    nested_raw.append(l)
                elif l == "end" and depth_config > 0:
                    depth_config -= 1
                    nested_raw.append(l)
                elif l == "next" and depth_config == 0:
                    depth_edit -= 1
                    if depth_edit == 0:
                        break
                elif l.startswith("set ") and depth_config == 0:
                    key, values = parse_set_line(l)
                    fields[key] = values
                else:
                    nested_raw.append(l)
                j += 1
            entries.append((name, fields, nested_raw))
            i = j + 1
        else:
            i += 1
    return entries
