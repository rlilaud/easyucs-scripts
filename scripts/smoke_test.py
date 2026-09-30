"""Smoke-test a built `eucs` artifact: `--version`, then a short `extract` against the fake EasyUCS.

The command running the artifact is given as arguments:

    python scripts/smoke_test.py dist/eucs
    python3.9 scripts/smoke_test.py python3.9 dist/eucs.pyz

Only the standard library is used, so the smoke test can run with a bare Python in which the
artifact cannot borrow an installed package it failed to bundle.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from fake_easyucs import FakeEasyUCS  # noqa: E402


def main(command: Sequence[str]) -> None:
    check_version(command)
    check_extract(command)
    print("Smoke test passed")


def check_version(command: Sequence[str]) -> None:
    init = (ROOT / "src" / "easyucs_scripts" / "__init__.py").read_text(encoding="utf-8")
    expected = re.search(r'^__version__ = "([^"]+)"', init, re.MULTILINE)
    assert expected is not None
    printed = run(command, "--version").stdout.strip()
    if printed != expected.group(1):
        raise SystemExit(f"--version printed {printed!r}, expected {expected.group(1)!r}")


def check_extract(command: Sequence[str]) -> None:
    with FakeEasyUCS() as fake, tempfile.TemporaryDirectory() as tmp:
        device = fake.add_device("FI-A", "ucsm")
        fake.add_device("ucsm_catalog.easyucs", "ucsm", is_system=True)
        instances_file = Path(tmp, "instances.yaml")
        instances_file.write_text(f"instances:\n  - url: {fake.url}\n    name: lab\n")
        output = Path(tmp, "extractions")

        run(command, "extract", "--instances", str(instances_file), "--output", str(output), "--poll-interval", "0")

        run_folders = list(output.iterdir()) if output.is_dir() else []
        if len(run_folders) != 1:
            raise SystemExit(f"expected one run folder in {output}, found {len(run_folders)}")
        (run_folder,) = run_folders
        device_folders = [p.name for p in (run_folder / "lab").iterdir()]
        if device_folders != ["FI-A"]:
            raise SystemExit(f"expected only the FI-A Device folder, found {device_folders}")
        if (run_folder / "lab" / "FI-A" / "config.json").read_bytes() != device.latest_config:
            raise SystemExit("config.json is not the Config just Fetched")
        if (run_folder / "lab" / "FI-A" / "inventory.json").read_bytes() != device.latest_inventory:
            raise SystemExit("inventory.json is not the Inventory just Fetched")
        summary = json.loads((run_folder / "summary.json").read_text(encoding="utf-8"))
        if summary.get("succeeded") is not True:
            raise SystemExit(f"summary.json does not record a successful run: {summary}")
        if not (run_folder / "run.log").read_text(encoding="utf-8"):
            raise SystemExit("run.log is empty")


def run(command: Sequence[str], *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [*command, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300
    )
    print(f"$ {' '.join([*command, *args])}\n{result.stdout}{result.stderr}")
    if result.returncode != 0:
        raise SystemExit(f"exited with code {result.returncode}")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1:])
