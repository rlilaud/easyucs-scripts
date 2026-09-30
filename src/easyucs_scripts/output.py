"""Output writer: the timestamped run folder, the Instance / Device tree inside it, and the run summary."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from easyucs_scripts.extraction import DeviceResult, InstanceFailed, Result, all_succeeded
from easyucs_scripts.instances import Instance

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
    """One run's output folder. Each run gets a new folder; nothing is ever overwritten.

    Devices may be saved from several threads at once.
    """

    def __init__(self, path: Path, instance_names: Sequence[str]) -> None:
        self.path = path
        self._instance_folders = _distinct_folders(path, instance_names)

    @classmethod
    def create(cls, output_dir: Path, instance_names: Sequence[str]) -> RunFolder:
        """Create a new run folder for the Instances named `instance_names`, which are unique.

        Instances whose safe names clash get distinct folders, suffixed in the order given.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        return cls(_new_folder(output_dir, datetime.now().strftime(RUN_TIMESTAMP_FORMAT)), instance_names)

    def save_device(self, instance_name: str, device_name: str, config: bytes, inventory: bytes) -> Path:
        instance_folder = self._instance_folders[instance_name]
        instance_folder.mkdir(exist_ok=True)
        device_folder = _new_folder(instance_folder, safe_filename(device_name))
        (device_folder / CONFIG_FILENAME).write_bytes(config)
        (device_folder / INVENTORY_FILENAME).write_bytes(inventory)
        return device_folder

    def write_summary(
        self, parameters: Mapping[str, Any], instances: Sequence[Instance], results: Sequence[Result]
    ) -> Path:
        """Write the machine-readable `summary.json` of the run. `parameters` must not contain secrets."""
        instance_failures = {r.instance.name: r.reason for r in results if isinstance(r, InstanceFailed)}
        summary = {
            "parameters": dict(parameters),
            "succeeded": all_succeeded(results),
            "instances": [
                {
                    "name": instance.name,
                    "url": instance.url,
                    "outcome": "failed" if instance.name in instance_failures else "succeeded",
                    "reason": instance_failures.get(instance.name),
                }
                for instance in instances
            ],
            "devices": [self._device_summary(r) for r in results if isinstance(r, DeviceResult)],
        }
        path = self.path / SUMMARY_FILENAME
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def _device_summary(self, result: DeviceResult) -> dict[str, Any]:
        files = {}
        if result.folder is not None:
            files = {
                "config": self._relative_path(result.folder / CONFIG_FILENAME),
                "inventory": self._relative_path(result.folder / INVENTORY_FILENAME),
            }
        return {
            "instance": result.instance.name,
            "name": result.device.name,
            "type": result.device.type,
            "outcome": "succeeded" if result.succeeded else "failed",
            "reason": result.failure,
            "files": files,
        }

    def _relative_path(self, path: Path) -> str:
        """`path` relative to the run folder, with `/` separators on every OS."""
        return path.relative_to(self.path).as_posix()


def _distinct_folders(parent: Path, names: Sequence[str]) -> dict[str, Path]:
    """Map each of `names` to a folder of `parent` named after it, suffixed `_2`, `_3`... when
    its safe name is taken (case-insensitively, as on Windows)."""
    taken: set[str] = set()
    folders = {}
    for name in names:
        base = candidate = safe_filename(name)
        attempt = 1
        while candidate.casefold() in taken:
            attempt += 1
            candidate = f"{base}_{attempt}"
        taken.add(candidate.casefold())
        folders[name] = parent / candidate
    return folders


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
