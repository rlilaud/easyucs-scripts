from __future__ import annotations

import json
import re
import socket
from pathlib import Path
from typing import Any

from conftest import RunEucs, RunExtract
from fake_easyucs import FakeEasyUCS


def only_child(folder: Path) -> Path:
    children = list(folder.iterdir())
    assert len(children) == 1, children
    return children[0]


def only_instance_folder(output: Path) -> Path:
    (folder,) = [p for p in only_child(output).iterdir() if p.is_dir()]
    return folder


def closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def read_summary(output: Path) -> Any:
    return json.loads((only_child(output) / "summary.json").read_text(encoding="utf-8"))


def test_extracts_a_fresh_config_and_inventory_for_every_real_device(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fi_a = fake_easyucs.add_device("fi-a", "ucsm")
    cimc = fake_easyucs.add_device("rack-01", "cimc")
    central = fake_easyucs.add_device("central", "ucsc")
    fake_easyucs.add_device("ucsm_catalog.easyucs", "ucsm", is_system=True)
    fake_easyucs.add_device("cimc_catalog.easyucs", "cimc", is_system=True)

    result = run_extract(fake_easyucs.url, tmp_path)

    assert result.exit_code == 0, result.output
    instance_folder = only_instance_folder(tmp_path)
    assert sorted(p.name for p in instance_folder.iterdir()) == ["central", "fi-a", "rack-01"]
    for device in (fi_a, cimc, central):
        assert (device.configs_fetched, device.inventories_fetched) == (1, 1)
        device_folder = instance_folder / device.name
        assert (device_folder / "config.json").read_bytes() == device.latest_config
        assert (device_folder / "inventory.json").read_bytes() == device.latest_inventory


def test_output_is_laid_out_as_run_timestamp_then_instance_then_device(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")

    result = run_extract(fake_easyucs.url, tmp_path)

    assert result.exit_code == 0, result.output
    run_folder = only_child(tmp_path)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", run_folder.name)
    instance_name = f"127.0.0.1_{fake_easyucs.port}"
    assert sorted(p.name for p in run_folder.iterdir()) == sorted([instance_name, "summary.json"])
    instance_folder = run_folder / instance_name
    device_folder = only_child(instance_folder)
    assert device_folder.name == "fi-a"
    assert sorted(p.name for p in device_folder.iterdir()) == ["config.json", "inventory.json"]


def test_instance_root_url_may_end_with_a_slash(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")

    result = run_extract(fake_easyucs.url + "/", tmp_path)

    assert result.exit_code == 0, result.output
    assert (only_instance_folder(tmp_path) / "fi-a" / "config.json").is_file()


def test_device_names_are_made_safe_for_windows_file_names(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("UCS:A/B*?", "ucsm")
    fake_easyucs.add_device("CON", "cimc")
    fake_easyucs.add_device("lab central.", "ucsc")

    result = run_extract(fake_easyucs.url, tmp_path)

    assert result.exit_code == 0, result.output
    instance_folder = only_instance_folder(tmp_path)
    assert sorted(p.name for p in instance_folder.iterdir()) == ["UCS_A_B__", "_CON", "lab central"]
    for device_folder in instance_folder.iterdir():
        assert (device_folder / "config.json").is_file()
        assert (device_folder / "inventory.json").is_file()


def test_devices_whose_safe_names_clash_get_distinct_folders(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    colon = fake_easyucs.add_device("fi:a", "ucsm")
    slash = fake_easyucs.add_device("fi/a", "ucsm")

    result = run_extract(fake_easyucs.url, tmp_path)

    assert result.exit_code == 0, result.output
    instance_folder = only_instance_folder(tmp_path)
    saved = sorted((instance_folder / name / "config.json").read_bytes() for name in ("fi_a", "fi_a_2"))
    assert saved == sorted([colon.latest_config, slash.latest_config])


def test_two_consecutive_runs_create_two_run_folders_without_overwriting(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    device = fake_easyucs.add_device("fi-a", "ucsm")

    first = run_extract(fake_easyucs.url, tmp_path)
    first_config = device.latest_config
    second = run_extract(fake_easyucs.url, tmp_path)

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    first_run, second_run = sorted(tmp_path.iterdir())
    instance = f"127.0.0.1_{fake_easyucs.port}"
    assert (first_run / instance / "fi-a" / "config.json").read_bytes() == first_config
    assert (second_run / instance / "fi-a" / "config.json").read_bytes() == device.latest_config
    assert first_config != device.latest_config


def test_a_failed_fetch_task_fails_its_device_with_easyucs_message_and_other_devices_are_still_extracted(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm", task_outcome="failed", task_message="Unable to connect to fi-a")
    rack = fake_easyucs.add_device("rack-01", "cimc")

    result = run_extract(fake_easyucs.url, tmp_path)

    assert result.exit_code == 1
    assert "Unable to connect to fi-a" in result.output
    instance_folder = only_instance_folder(tmp_path)
    assert (instance_folder / "rack-01" / "config.json").read_bytes() == rack.latest_config
    assert not (instance_folder / "fi-a").exists()


def test_a_skipped_fetch_task_fails_its_device_with_easyucs_message(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm", task_outcome="skipped", task_message="Device is not reachable")

    result = run_extract(fake_easyucs.url, tmp_path)

    assert result.exit_code == 1
    assert "Device is not reachable" in result.output


def test_a_fetch_task_still_running_after_the_timeout_fails_its_device_and_other_devices_are_still_extracted(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm", task_outcome="in_progress")
    rack = fake_easyucs.add_device("rack-01", "cimc")

    result = run_extract(fake_easyucs.url, tmp_path, "--timeout", "0.2s")

    assert result.exit_code == 1
    assert "did not finish within 0.2s" in result.output
    instance_folder = only_instance_folder(tmp_path)
    assert (instance_folder / "rack-01" / "config.json").read_bytes() == rack.latest_config


def test_no_fetch_saves_the_most_recent_stored_config_and_inventory_without_fetching(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    device = fake_easyucs.add_device("fi-a", "ucsm")
    run_extract(fake_easyucs.url, tmp_path / "earlier")
    latest_config, latest_inventory = device.latest_config, device.latest_inventory

    result = run_extract(fake_easyucs.url, tmp_path / "now", "--no-fetch")

    assert result.exit_code == 0, result.output
    assert (device.configs_fetched, device.inventories_fetched) == (1, 1)
    device_folder = only_instance_folder(tmp_path / "now") / "fi-a"
    assert (device_folder / "config.json").read_bytes() == latest_config
    assert (device_folder / "inventory.json").read_bytes() == latest_inventory


def test_no_fetch_fails_a_device_with_nothing_stored_and_hints_to_fetch(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm", stored_config=False)
    fake_easyucs.add_device("rack-01", "cimc", stored_inventory=False)
    central = fake_easyucs.add_device("central", "ucsc")

    result = run_extract(fake_easyucs.url, tmp_path, "--no-fetch")

    assert result.exit_code == 1
    fi_a, rack, central_summary = read_summary(tmp_path)["devices"]
    assert (fi_a["outcome"], rack["outcome"], central_summary["outcome"]) == ("failed", "failed", "succeeded")
    assert "no stored Config" in fi_a["reason"]
    assert "no stored Inventory" in rack["reason"]
    for reason in (fi_a["reason"], rack["reason"]):
        assert "without --no-fetch" in reason
    instance_folder = only_instance_folder(tmp_path)
    assert sorted(p.name for p in instance_folder.iterdir()) == ["central"]
    assert (instance_folder / "central" / "config.json").read_bytes() == central.latest_config


def test_fetches_are_not_forced_by_default(run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path) -> None:
    device = fake_easyucs.add_device("fi-a", "ucsm")

    result = run_extract(fake_easyucs.url, tmp_path)

    assert result.exit_code == 0, result.output
    assert device.fetch_forces == [False, False]


def test_force_is_forwarded_to_every_fetch(run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path) -> None:
    device = fake_easyucs.add_device("fi-a", "ucsm")

    result = run_extract(fake_easyucs.url, tmp_path, "--force")

    assert result.exit_code == 0, result.output
    assert device.fetch_forces == [True, True]


def test_help_warns_that_force_may_produce_an_incomplete_config(run_eucs: RunEucs) -> None:
    result = run_eucs("extract", "--help")

    assert result.exit_code == 0, result.output
    assert "--force" in result.output
    assert "incomplete" in result.output


def test_help_documents_the_timeout_but_not_the_polling_interval(run_eucs: RunEucs) -> None:
    result = run_eucs("extract", "--help")

    assert result.exit_code == 0, result.output
    assert "--timeout" in result.output
    assert "poll" not in result.output.lower()


def test_an_invalid_timeout_is_rejected(run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path) -> None:
    result = run_extract(fake_easyucs.url, tmp_path, "--timeout", "soon")

    assert result.exit_code == 2
    assert "--timeout" in result.output


def test_a_fetch_refused_by_easyucs_fails_with_easyucs_message(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("LabDC-Paris", "intersight", fetch_error="Unsupported device type")

    result = run_extract(fake_easyucs.url, tmp_path)

    assert result.exit_code == 1
    assert "Unsupported device type" in result.output


def test_summary_records_run_parameters_and_the_outcome_and_files_of_every_device(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")
    fake_easyucs.add_device("rack-01", "cimc", task_outcome="failed", task_message="Unable to connect")
    fake_easyucs.add_device("ucsm_catalog.easyucs", "ucsm", is_system=True)
    instance = f"127.0.0.1_{fake_easyucs.port}"

    result = run_extract(fake_easyucs.url, tmp_path, "--timeout", "5m", "--force")

    assert result.exit_code == 1
    summary = read_summary(tmp_path)
    assert summary["parameters"] == {
        "urls": [fake_easyucs.url],
        "output": str(tmp_path),
        "no_fetch": False,
        "force": True,
        "timeout_seconds": 300,
    }
    assert summary["succeeded"] is False
    assert summary["instances"] == [{"name": instance, "url": fake_easyucs.url, "outcome": "succeeded", "reason": None}]
    fi_a, rack = summary["devices"]
    assert fi_a == {
        "instance": instance,
        "name": "fi-a",
        "type": "ucsm",
        "outcome": "succeeded",
        "reason": None,
        "files": {"config": f"{instance}/fi-a/config.json", "inventory": f"{instance}/fi-a/inventory.json"},
    }
    assert rack["instance"] == instance
    assert (rack["name"], rack["type"], rack["outcome"], rack["files"]) == ("rack-01", "cimc", "failed", {})
    assert "Unable to connect" in rack["reason"]


def test_a_run_where_every_device_succeeds_exits_zero_with_a_successful_summary(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")
    fake_easyucs.add_device("rack-01", "cimc")

    result = run_extract(fake_easyucs.url, tmp_path)

    assert result.exit_code == 0, result.output
    summary = read_summary(tmp_path)
    assert summary["succeeded"] is True
    assert [d["outcome"] for d in summary["devices"]] == ["succeeded", "succeeded"]
    table = result.output[result.output.index("Instance") :]
    assert re.search(r"rack-01.*cimc.*succeeded", table)


def test_a_summary_table_lists_every_device_at_the_end_of_the_run(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")
    fake_easyucs.add_device("rack-01", "cimc", task_outcome="skipped", task_message="Not reachable")

    result = run_extract(fake_easyucs.url, tmp_path)

    assert result.exit_code == 1
    table = result.output[result.output.index("Instance") :]
    assert re.search(r"Instance.*Device.*Type.*Outcome.*Reason", table)
    assert re.search(r"fi-a.*ucsm.*succeeded", table)
    assert re.search(r"rack-01.*cimc.*failed.*Not reachable", table)


def test_the_summary_table_shows_a_failed_instance(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.error = (503, "Down")

    result = run_extract(fake_easyucs.url, tmp_path)

    table = result.output[result.output.index("Instance") :]
    assert re.search(rf"127\.0\.0\.1_{fake_easyucs.port}.*failed.*HTTP 503: Down", table)


def test_an_instance_returning_http_errors_is_recorded_as_a_failed_instance(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")
    fake_easyucs.error = (503, "EasyUCS is starting")

    result = run_extract(fake_easyucs.url, tmp_path)

    assert result.exit_code == 1
    summary = read_summary(tmp_path)
    (instance,) = summary["instances"]
    assert instance["name"] == f"127.0.0.1_{fake_easyucs.port}"
    assert instance["outcome"] == "failed"
    assert "HTTP 503: EasyUCS is starting" in instance["reason"]
    assert summary["devices"] == []


def test_an_instance_answering_with_unexpected_json_is_recorded_as_a_failed_instance(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.devices_response = {"items": []}

    result = run_extract(fake_easyucs.url, tmp_path)

    assert result.exit_code == 1
    (instance,) = read_summary(tmp_path)["instances"]
    assert instance["outcome"] == "failed"
    assert "unexpected response" in instance["reason"]


def test_a_url_with_embedded_credentials_is_rejected(run_extract: RunExtract, tmp_path: Path) -> None:
    result = run_extract(f"http://admin:hunter2@127.0.0.1:{closed_port()}", tmp_path)

    assert result.exit_code == 2
    assert "hunter2" not in result.output
    assert not tmp_path.exists() or not any(tmp_path.iterdir())


def test_an_unreachable_instance_is_recorded_as_a_failed_instance(run_extract: RunExtract, tmp_path: Path) -> None:
    url = f"http://127.0.0.1:{closed_port()}"

    result = run_extract(url, tmp_path)

    assert result.exit_code == 1
    (instance,) = read_summary(tmp_path)["instances"]
    assert instance["outcome"] == "failed"
    assert f"GET {url}/api/v1/devices failed" in instance["reason"]
