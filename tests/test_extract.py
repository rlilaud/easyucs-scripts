from __future__ import annotations

import re
import socket
from pathlib import Path

from conftest import RunEucs
from fake_easyucs import FakeEasyUCS


def only_child(folder: Path) -> Path:
    children = list(folder.iterdir())
    assert len(children) == 1, children
    return children[0]


def test_extracts_a_fresh_config_and_inventory_for_every_real_device(
    run_eucs: RunEucs, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fi_a = fake_easyucs.add_device("fi-a", "ucsm")
    cimc = fake_easyucs.add_device("rack-01", "cimc")
    central = fake_easyucs.add_device("central", "ucsc")
    fake_easyucs.add_device("ucsm_catalog.easyucs", "ucsm", is_system=True)
    fake_easyucs.add_device("cimc_catalog.easyucs", "cimc", is_system=True)

    result = run_eucs("extract", "--url", fake_easyucs.url, "--output", str(tmp_path))

    assert result.exit_code == 0, result.output
    instance_folder = only_child(only_child(tmp_path))
    assert sorted(p.name for p in instance_folder.iterdir()) == ["central", "fi-a", "rack-01"]
    for device in (fi_a, cimc, central):
        assert device.fetch_count == 1
        device_folder = instance_folder / device.name
        assert (device_folder / "config.json").read_bytes() == device.latest_config
        assert (device_folder / "inventory.json").read_bytes() == device.latest_inventory


def test_output_is_laid_out_as_run_timestamp_then_instance_then_device(
    run_eucs: RunEucs, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")

    result = run_eucs("extract", "--url", fake_easyucs.url, "--output", str(tmp_path))

    assert result.exit_code == 0, result.output
    run_folder = only_child(tmp_path)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", run_folder.name)
    instance_folder = only_child(run_folder)
    assert instance_folder.name == f"127.0.0.1_{fake_easyucs.port}"
    device_folder = only_child(instance_folder)
    assert device_folder.name == "fi-a"
    assert sorted(p.name for p in device_folder.iterdir()) == ["config.json", "inventory.json"]


def test_instance_root_url_may_end_with_a_slash(
    run_eucs: RunEucs, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")

    result = run_eucs("extract", "--url", fake_easyucs.url + "/", "--output", str(tmp_path))

    assert result.exit_code == 0, result.output
    assert (only_child(only_child(tmp_path)) / "fi-a" / "config.json").is_file()


def test_device_names_are_made_safe_for_windows_file_names(
    run_eucs: RunEucs, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("UCS:A/B*?", "ucsm")
    fake_easyucs.add_device("CON", "cimc")
    fake_easyucs.add_device("lab central.", "ucsc")

    result = run_eucs("extract", "--url", fake_easyucs.url, "--output", str(tmp_path))

    assert result.exit_code == 0, result.output
    instance_folder = only_child(only_child(tmp_path))
    assert sorted(p.name for p in instance_folder.iterdir()) == ["UCS_A_B__", "_CON", "lab central"]
    for device_folder in instance_folder.iterdir():
        assert (device_folder / "config.json").is_file()
        assert (device_folder / "inventory.json").is_file()


def test_two_consecutive_runs_create_two_run_folders_without_overwriting(
    run_eucs: RunEucs, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    device = fake_easyucs.add_device("fi-a", "ucsm")

    first = run_eucs("extract", "--url", fake_easyucs.url, "--output", str(tmp_path))
    first_config = device.latest_config
    second = run_eucs("extract", "--url", fake_easyucs.url, "--output", str(tmp_path))

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    first_run, second_run = sorted(tmp_path.iterdir())
    instance = f"127.0.0.1_{fake_easyucs.port}"
    assert (first_run / instance / "fi-a" / "config.json").read_bytes() == first_config
    assert (second_run / instance / "fi-a" / "config.json").read_bytes() == device.latest_config
    assert first_config != device.latest_config


def test_an_unreachable_instance_fails_cleanly_with_a_non_zero_exit_code(run_eucs: RunEucs, tmp_path: Path) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]

    result = run_eucs("extract", "--url", f"http://127.0.0.1:{closed_port}", "--output", str(tmp_path))

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit), "expected an error message, not a traceback"
