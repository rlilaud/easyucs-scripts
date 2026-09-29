"""Output writer: the timestamped run folder and the Instance / Device tree inside it."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

RUN_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
CONFIG_FILENAME = "config.json"
INVENTORY_FILENAME = "inventory.json"
SUMMARY_FILENAME = "summary.json"

_WINDOWS_INVALID_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_filename(name: str) -> str:
    """Turn `name` into a file name that is valid on Windows, and therefore everywhere."""
    cleaned = _WINDOWS_INVALID_CHARACTERS.sub("_", name).rstrip(" .")
    if not cleaned:
        return "_"
    if cleaned.split(".")[0].upper() in _WINDOWS_RESERVED_NAMES:
        return "_" + cleaned
    return cleaned


class RunFolder:
    """One run's output folder. Each run gets a new folder; nothing is ever overwritten."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def create(cls, output_dir: Path) -> RunFolder:
        output_dir.mkdir(parents=True, exist_ok=True)
        return cls(_new_folder(output_dir, datetime.now().strftime(RUN_TIMESTAMP_FORMAT)))

    def save_device(self, instance_name: str, device_name: str, config: bytes, inventory: bytes) -> Path:
        instance_folder = self.path / safe_filename(instance_name)
        instance_folder.mkdir(exist_ok=True)
        device_folder = _new_folder(instance_folder, safe_filename(device_name))
        (device_folder / CONFIG_FILENAME).write_bytes(config)
        (device_folder / INVENTORY_FILENAME).write_bytes(inventory)
        return device_folder

    def write_summary(self, summary: Mapping[str, Any]) -> Path:
        path = self.path / SUMMARY_FILENAME
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def relative_path(self, path: Path) -> str:
        """`path` relative to the run folder, with `/` separators on every OS."""
        return path.relative_to(self.path).as_posix()


def _new_folder(parent: Path, name: str) -> Path:
    """Create `parent/name`, or `parent/name_2`, `name_3`... if taken (case-insensitively on Windows)."""
    candidate = parent / name
    attempt = 1
    while True:
        try:
            candidate.mkdir()
        except FileExistsError:
            attempt += 1
            candidate = parent / f"{name}_{attempt}"
        else:
            return candidate
