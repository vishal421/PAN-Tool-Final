"""
Junos "set"-style configuration tokenizer.

Unlike FortiGate/Cisco's block-oriented CLI (config/edit/next/end), a Junos
`set`-format export (what you get from `show configuration | display set`,
or the "set" export from J-Web) is already flat: every line fully spells
out its own path from the root, e.g.:

    set security zones security-zone trust interfaces ge-0/0/0.0
    set security policies from-zone trust to-zone untrust policy allow-web then permit

This means there's no nesting/indentation to track (unlike FortiGate) -
each line simply needs to be split into tokens (respecting quoted strings
for values with spaces) so parser.py can pattern-match against the token
list directly.
"""

from __future__ import annotations

import shlex


def strip_noise(raw_text: str) -> list[str]:
    """
    Split into non-empty, non-comment lines, keeping only actual `set`
    configuration statements. Junos "set" exports sometimes carry a
    leading '## Last changed:' banner or '#' comment lines, and can mix in
    'deactivate'/'annotate' lines (config we intentionally don't act on -
    those are surfaced as informational issues by the caller, not parsed).
    """
    lines: list[str] = []
    for raw in raw_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def tokenize(line: str) -> list[str]:
    """
    Split one `set ...` line into tokens, honoring double-quoted values
    (e.g. `set snmp location "Data Center 1"` -> [..., 'Data Center 1']).
    Returns tokens WITHOUT the leading 'set' keyword.
    """
    try:
        toks = shlex.split(line, posix=True)
    except ValueError:
        # Unbalanced quotes etc - fall back to a naive split rather than
        # dropping the line entirely.
        toks = line.split()
    if toks and toks[0] == "set":
        toks = toks[1:]
    return toks


def set_lines(lines: list[str]) -> list[list[str]]:
    """Return tokenized `set ...` lines only (skips delete/deactivate/annotate/etc)."""
    out = []
    for line in lines:
        if not line.startswith("set "):
            continue
        out.append(tokenize(line))
    return out


def match_prefix(tokens: list[str], prefix: list[str]) -> list[str] | None:
    """
    If `tokens` starts with the given literal prefix, return the
    remaining tokens after it; otherwise None.
    """
    if len(tokens) < len(prefix):
        return None
    if tokens[:len(prefix)] != prefix:
        return None
    return tokens[len(prefix):]
