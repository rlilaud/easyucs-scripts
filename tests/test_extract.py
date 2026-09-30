from __future__ import annotations

import json
import re
import socket
from pathlib import Path
from typing import Any

from conftest import RunEucs, RunExtract, RunExtractFrom
from fake_easyucs import FakeDevice, FakeEasyUCS


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
    assert len(device.fetch_forces) == 2
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


def test_type_filter_extracts_only_devices_of_that_type(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")
    fake_easyucs.add_device("fi-b", "ucsm")
    rack = fake_easyucs.add_device("rack-01", "cimc")
    fake_easyucs.add_device("ucsm_catalog.easyucs", "ucsm", is_system=True)

    result = run_extract(fake_easyucs.url, tmp_path, "--type", "ucsm")

    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in only_instance_folder(tmp_path).iterdir()) == ["fi-a", "fi-b"]
    assert rack.fetch_forces == []


def test_an_unknown_device_type_is_rejected_with_the_accepted_types(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    device = fake_easyucs.add_device("fi-a", "ucsm")

    result = run_extract(fake_easyucs.url, tmp_path, "--type", "nexus")

    assert result.exit_code == 2
    assert "--type" in result.output
    assert "nexus" in result.output
    for accepted in ("ucsm", "cimc", "imm_domain", "ucsc", "intersight"):
        assert accepted in result.output
    assert device.fetch_forces == []


def test_device_filter_extracts_only_the_device_with_that_name(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")
    fake_easyucs.add_device("fi-b", "ucsm")

    result = run_extract(fake_easyucs.url, tmp_path, "--device", "fi-b")

    assert result.exit_code == 0, result.output
    assert [p.name for p in only_instance_folder(tmp_path).iterdir()] == ["fi-b"]


def test_filters_can_be_repeated_to_select_several_values(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    for name, device_type in [("fi-a", "ucsm"), ("rack-01", "cimc"), ("central", "ucsc"), ("LabDC", "intersight")]:
        fake_easyucs.add_device(name, device_type)

    by_type = run_extract(fake_easyucs.url, tmp_path / "by-type", "--type", "cimc", "--type", "intersight")
    by_name = run_extract(fake_easyucs.url, tmp_path / "by-name", "--device", "fi-a", "--device", "central")

    assert by_type.exit_code == 0, by_type.output
    assert by_name.exit_code == 0, by_name.output
    assert sorted(p.name for p in only_instance_folder(tmp_path / "by-type").iterdir()) == ["LabDC", "rack-01"]
    assert sorted(p.name for p in only_instance_folder(tmp_path / "by-name").iterdir()) == ["central", "fi-a"]


def test_a_device_must_match_both_type_and_name_filters(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")
    fake_easyucs.add_device("fi-b", "ucsm")
    fake_easyucs.add_device("rack-01", "cimc")

    result = run_extract(
        fake_easyucs.url, tmp_path, "--type", "ucsm", "--device", "fi-a", "--device", "rack-01"
    )

    assert result.exit_code == 0, result.output
    assert [p.name for p in only_instance_folder(tmp_path).iterdir()] == ["fi-a"]


def test_catalog_devices_stay_excluded_even_when_filters_name_them(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")
    catalog = fake_easyucs.add_device("ucsm_catalog.easyucs", "ucsm", is_system=True)

    result = run_extract(
        fake_easyucs.url, tmp_path, "--type", "ucsm", "--device", "fi-a", "--device", "ucsm_catalog.easyucs"
    )

    assert result.exit_code == 0, result.output
    assert [p.name for p in only_instance_folder(tmp_path).iterdir()] == ["fi-a"]
    assert catalog.fetch_forces == []


def test_filters_matching_no_device_say_so_for_the_instance(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")
    fake_easyucs.add_device("ucsm_catalog.easyucs", "ucsm", is_system=True)

    result = run_extract(fake_easyucs.url, tmp_path, "--type", "cimc")

    assert result.exit_code == 0, result.output
    assert re.search(rf"No Device of Instance 127\.0\.0\.1_{fake_easyucs.port} matches", result.output)
    assert read_summary(tmp_path)["devices"] == []


def test_an_instance_with_only_catalog_devices_says_it_has_no_device_to_extract(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("ucsm_catalog.easyucs", "ucsm", is_system=True)

    result = run_extract(fake_easyucs.url, tmp_path)

    assert result.exit_code == 0, result.output
    assert f"Instance 127.0.0.1_{fake_easyucs.port} has no Device to extract" in result.output


def test_summary_records_run_parameters_and_the_outcome_and_files_of_every_device(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")
    fake_easyucs.add_device("rack-01", "cimc", task_outcome="failed", task_message="Unable to connect")
    fake_easyucs.add_device("ucsm_catalog.easyucs", "ucsm", is_system=True)
    instance = f"127.0.0.1_{fake_easyucs.port}"

    result = run_extract(fake_easyucs.url, tmp_path, "--timeout", "5m", "--force", "--type", "ucsm", "--type", "cimc")

    assert result.exit_code == 1
    summary = read_summary(tmp_path)
    assert summary["parameters"] == {
        "instances_file": None,
        "urls": [fake_easyucs.url],
        "device_types": ["cimc", "ucsm"],
        "device_names": [],
        "output": str(tmp_path),
        "no_fetch": False,
        "force": True,
        "timeout_seconds": 300,
        "workers": 4,
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


def write_instances_file(folder: Path, entries: list[tuple[str, str]]) -> Path:
    """Write an Instances file listing `(name, url)` entries."""
    path = folder / "instances.yaml"
    lines = ["instances:"] + [f"  - name: {name}\n    url: {url}" for name, url in entries]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def assert_saved(instance_folder: Path, device: FakeDevice) -> None:
    device_folder = instance_folder / device.name
    assert (device_folder / "config.json").read_bytes() == device.latest_config
    assert (device_folder / "inventory.json").read_bytes() == device.latest_inventory


def test_extracts_every_instance_listed_in_an_instances_file(
    run_extract_from: RunExtractFrom, fake_easyucs: FakeEasyUCS, other_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fi_a = fake_easyucs.add_device("fi-a", "ucsm")
    fake_easyucs.add_device("ucsm_catalog.easyucs", "ucsm", is_system=True)
    central = other_easyucs.add_device("central", "ucsc")
    instances_file = write_instances_file(tmp_path, [("paris", fake_easyucs.url), ("lyon", other_easyucs.url)])

    result = run_extract_from(["--instances", str(instances_file)], tmp_path / "out")

    assert result.exit_code == 0, result.output
    run_folder = only_child(tmp_path / "out")
    assert sorted(p.name for p in run_folder.iterdir()) == ["lyon", "paris", "summary.json"]
    assert_saved(run_folder / "paris", fi_a)
    assert_saved(run_folder / "lyon", central)
    summary = json.loads((run_folder / "summary.json").read_text(encoding="utf-8"))
    assert summary["parameters"]["instances_file"] == str(instances_file)
    assert summary["parameters"]["urls"] == []
    assert [(i["name"], i["url"], i["outcome"]) for i in summary["instances"]] == [
        ("paris", fake_easyucs.url, "succeeded"),
        ("lyon", other_easyucs.url, "succeeded"),
    ]
    assert [(d["instance"], d["name"]) for d in summary["devices"]] == [("paris", "fi-a"), ("lyon", "central")]


def test_url_can_be_repeated_to_extract_several_instances(
    run_extract_from: RunExtractFrom, fake_easyucs: FakeEasyUCS, other_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fi_a = fake_easyucs.add_device("fi-a", "ucsm")
    central = other_easyucs.add_device("central", "ucsc")

    result = run_extract_from(["--url", fake_easyucs.url, "--url", other_easyucs.url], tmp_path)

    assert result.exit_code == 0, result.output
    run_folder = only_child(tmp_path)
    assert_saved(run_folder / f"127.0.0.1_{fake_easyucs.port}", fi_a)
    assert_saved(run_folder / f"127.0.0.1_{other_easyucs.port}", central)
    assert read_summary(tmp_path)["parameters"]["urls"] == [fake_easyucs.url, other_easyucs.url]


def test_an_instances_file_and_urls_combine(
    run_extract_from: RunExtractFrom, fake_easyucs: FakeEasyUCS, other_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fi_a = fake_easyucs.add_device("fi-a", "ucsm")
    central = other_easyucs.add_device("central", "ucsc")
    instances_file = write_instances_file(tmp_path, [("paris", fake_easyucs.url)])

    result = run_extract_from(["--instances", str(instances_file), "--url", other_easyucs.url], tmp_path / "out")

    assert result.exit_code == 0, result.output
    run_folder = only_child(tmp_path / "out")
    assert_saved(run_folder / "paris", fi_a)
    assert_saved(run_folder / f"127.0.0.1_{other_easyucs.port}", central)


def test_no_instance_source_is_a_clear_error(run_extract_from: RunExtractFrom, tmp_path: Path) -> None:
    result = run_extract_from([], tmp_path)

    assert result.exit_code == 2
    assert "--instances" in result.output
    assert "--url" in result.output
    assert not tmp_path.exists() or not any(tmp_path.iterdir())


def test_an_invalid_instances_file_is_rejected_before_any_extraction(
    run_extract_from: RunExtractFrom, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    device = fake_easyucs.add_device("fi-a", "ucsm")
    instances_file = tmp_path / "instances.yaml"
    instances_file.write_text(f"instances:\n  - url: {fake_easyucs.url}\n  - nmae: lyon\n", encoding="utf-8")

    result = run_extract_from(["--instances", str(instances_file)], tmp_path / "out")

    assert result.exit_code == 2
    assert "entry 2" in result.output
    assert "nmae" in result.output
    assert device.fetch_forces == []
    assert not (tmp_path / "out").exists()


def test_duplicate_instance_names_across_file_and_url_are_rejected_before_any_extraction(
    run_extract_from: RunExtractFrom, fake_easyucs: FakeEasyUCS, other_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    device = fake_easyucs.add_device("fi-a", "ucsm")
    other_device = other_easyucs.add_device("central", "ucsc")
    clashing_name = f"127.0.0.1_{fake_easyucs.port}"
    instances_file = write_instances_file(tmp_path, [(clashing_name, other_easyucs.url)])

    result = run_extract_from(["--instances", str(instances_file), "--url", fake_easyucs.url], tmp_path / "out")

    assert result.exit_code == 2
    assert clashing_name in result.output
    assert (device.fetch_forces, other_device.fetch_forces) == ([], [])
    assert not (tmp_path / "out").exists()


def test_a_failed_instance_does_not_stop_the_others(
    run_extract_from: RunExtractFrom, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fi_a = fake_easyucs.add_device("fi-a", "ucsm")
    down_url = f"http://127.0.0.1:{closed_port()}"

    result = run_extract_from(["--url", down_url, "--url", fake_easyucs.url], tmp_path)

    assert result.exit_code == 1
    assert_saved(only_child(tmp_path) / f"127.0.0.1_{fake_easyucs.port}", fi_a)
    down, up = read_summary(tmp_path)["instances"]
    assert (down["url"], down["outcome"]) == (down_url, "failed")
    assert (up["url"], up["outcome"]) == (fake_easyucs.url, "succeeded")


def test_instances_whose_safe_names_clash_get_distinct_folders(
    run_extract_from: RunExtractFrom, fake_easyucs: FakeEasyUCS, other_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fi_a = fake_easyucs.add_device("fi-a", "ucsm")
    fi_b = other_easyucs.add_device("fi-b", "ucsm")
    instances_file = write_instances_file(tmp_path, [("'lab:a'", fake_easyucs.url), ("'lab/a'", other_easyucs.url)])

    result = run_extract_from(["--instances", str(instances_file)], tmp_path / "out")

    assert result.exit_code == 0, result.output
    run_folder = only_child(tmp_path / "out")
    assert_saved(run_folder / "lab_a", fi_a)
    assert_saved(run_folder / "lab_a_2", fi_b)
    files = [d["files"]["config"] for d in read_summary(tmp_path / "out")["devices"]]
    assert files == ["lab_a/fi-a/config.json", "lab_a_2/fi-b/config.json"]


SLOW_POLLING = ("--poll-interval", "0.01")


def test_workers_bounds_the_devices_fetched_at_once_in_an_instance(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.task_seconds = 0.1
    for index in range(5):
        fake_easyucs.add_device(f"fi-{index}", "ucsm")

    result = run_extract(fake_easyucs.url, tmp_path, "--workers", "2", *SLOW_POLLING)

    assert result.exit_code == 0, result.output
    assert fake_easyucs.peak_concurrent_fetches == 2
    assert len(list(only_instance_folder(tmp_path).iterdir())) == 5


def test_four_devices_of_an_instance_are_fetched_at_once_by_default(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.task_seconds = 0.1
    for index in range(6):
        fake_easyucs.add_device(f"fi-{index}", "ucsm")

    result = run_extract(fake_easyucs.url, tmp_path, *SLOW_POLLING)

    assert result.exit_code == 0, result.output
    assert fake_easyucs.peak_concurrent_fetches == 4


def test_workers_must_be_at_least_one(run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path) -> None:
    device = fake_easyucs.add_device("fi-a", "ucsm")

    result = run_extract(fake_easyucs.url, tmp_path, "--workers", "0")

    assert result.exit_code == 2
    assert "--workers" in result.output
    assert device.fetch_forces == []


def test_instances_are_extracted_at_the_same_time(
    run_extract_from: RunExtractFrom, fake_easyucs: FakeEasyUCS, other_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.task_seconds = other_easyucs.task_seconds = 0.2
    fi_a = fake_easyucs.add_device("fi-a", "ucsm")
    central = other_easyucs.add_device("central", "ucsc")

    result = run_extract_from(["--url", fake_easyucs.url, "--url", other_easyucs.url], tmp_path, *SLOW_POLLING)

    assert result.exit_code == 0, result.output
    assert fi_a.fetch_started_at is not None and central.fetch_started_at is not None
    assert fi_a.fetch_finished_at is not None and central.fetch_finished_at is not None
    assert max(fi_a.fetch_started_at, central.fetch_started_at) < min(fi_a.fetch_finished_at, central.fetch_finished_at)


def test_in_a_parallel_run_a_failing_device_or_instance_does_not_affect_the_others(
    run_extract_from: RunExtractFrom, fake_easyucs: FakeEasyUCS, other_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.task_seconds = other_easyucs.task_seconds = 0.1
    fake_easyucs.add_device("fi-a", "ucsm", task_outcome="failed", task_message="Unable to connect to fi-a")
    rack = fake_easyucs.add_device("rack-01", "cimc")
    fake_easyucs.add_device("fi-b", "ucsm", task_outcome="in_progress")
    central = fake_easyucs.add_device("central", "ucsc")
    lab_dc = other_easyucs.add_device("LabDC", "intersight")
    down_url = f"http://127.0.0.1:{closed_port()}"
    instances_file = write_instances_file(
        tmp_path, [("paris", fake_easyucs.url), ("down", down_url), ("lyon", other_easyucs.url)]
    )

    result = run_extract_from(
        ["--instances", str(instances_file)], tmp_path / "out", "--timeout", "0.5s", *SLOW_POLLING
    )

    assert result.exit_code == 1
    run_folder = only_child(tmp_path / "out")
    assert sorted(p.name for p in (run_folder / "paris").iterdir()) == ["central", "rack-01"]
    assert_saved(run_folder / "paris", rack)
    assert_saved(run_folder / "paris", central)
    assert_saved(run_folder / "lyon", lab_dc)
    summary = read_summary(tmp_path / "out")
    assert summary["succeeded"] is False
    assert [(i["name"], i["outcome"]) for i in summary["instances"]] == [
        ("paris", "succeeded"),
        ("down", "failed"),
        ("lyon", "succeeded"),
    ]
    assert [(d["instance"], d["name"], d["outcome"]) for d in summary["devices"]] == [
        ("paris", "fi-a", "failed"),
        ("paris", "rack-01", "succeeded"),
        ("paris", "fi-b", "failed"),
        ("paris", "central", "succeeded"),
        ("lyon", "LabDC", "succeeded"),
    ]


def test_each_device_has_a_progress_bar_that_ends_showing_its_outcome(
    run_extract: RunExtract, fake_easyucs: FakeEasyUCS, tmp_path: Path
) -> None:
    fake_easyucs.add_device("fi-a", "ucsm")
    fake_easyucs.add_device("rack-01", "cimc", task_outcome="failed", task_message="Unable to connect")
    instance = re.escape(f"127.0.0.1_{fake_easyucs.port}")

    result = run_extract(fake_easyucs.url, tmp_path)

    assert result.exit_code == 1
    progress = result.output[: result.output.index("Extraction summary")]
    assert re.search(rf"{instance} / fi-a \(ucsm\).*100%.*succeeded", progress)
    assert re.search(rf"{instance} / rack-01 \(cimc\).*failed", progress)
