"""Runs `eucs extract` against a real EasyUCS Instance when `EUCS_TEST_URL` is set."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import RunEucs

EUCS_TEST_URL = os.environ.get("EUCS_TEST_URL")

pytestmark = pytest.mark.skipif(
    not EUCS_TEST_URL, reason="set EUCS_TEST_URL to the root URL of a real EasyUCS Instance"
)


def test_extracts_every_real_device_of_a_real_instance(run_eucs: RunEucs, tmp_path: Path) -> None:
    assert EUCS_TEST_URL is not None

    result = run_eucs("extract", "--url", EUCS_TEST_URL, "--output", str(tmp_path))

    assert result.exit_code == 0, result.output
    (run_folder,) = tmp_path.iterdir()
    (instance_folder,) = [p for p in run_folder.iterdir() if p.is_dir()]
    device_folders = list(instance_folder.iterdir())
    assert device_folders, "the Instance has no real Device to extract"
    for device_folder in device_folders:
        assert not device_folder.name.endswith("_catalog.easyucs")
        assert (device_folder / "config.json").stat().st_size > 0
        assert (device_folder / "inventory.json").stat().st_size > 0
