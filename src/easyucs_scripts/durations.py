"""Durations as operators type them: `90s`, `30m`, `1h`, or a bare number of seconds."""

from __future__ import annotations

import re

_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600}
_DURATION = re.compile(r"(\d+(?:\.\d+)?)([smh]?)")


def parse_duration(text: str) -> float:
    """Return the number of seconds in `text`, or raise ValueError."""
    match = _DURATION.fullmatch(text.strip().lower())
    if not match or float(match.group(1)) <= 0:
        raise ValueError(f"{text!r} is not a valid duration; expected e.g. 90s, 30m, 1h")
    return float(match.group(1)) * _UNIT_SECONDS[match.group(2) or "s"]


def format_duration(seconds: float) -> str:
    for unit in ("h", "m"):
        if seconds >= _UNIT_SECONDS[unit] and seconds % _UNIT_SECONDS[unit] == 0:
            return f"{seconds / _UNIT_SECONDS[unit]:g}{unit}"
    return f"{seconds:g}s"
