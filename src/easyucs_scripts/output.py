"""Output writer: the timestamped run folder and the Instance / Device tree inside it."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

RUN_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"

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
        stamp = datetime.now().strftime(RUN_TIMESTAMP_FORMAT)
        output_dir.mkdir(parents=True, exist_ok=True)
        candidate = output_dir / stamp
        attempt = 1
        while True:
            try:
                candidate.mkdir()
            except FileExistsError:
                attempt += 1
                candidate = output_dir / f"{stamp}_{attempt}"
            else:
                return cls(candidate)

    def save_device(self, instance_name: str, device_name: str, config: bytes, inventory: bytes) -> Path:
        device_folder = self.path / safe_filename(instance_name) / safe_filename(device_name)
        device_folder.mkdir(parents=True, exist_ok=True)
        (device_folder / "config.json").write_bytes(config)
        (device_folder / "inventory.json").write_bytes(inventory)
        return device_folder
