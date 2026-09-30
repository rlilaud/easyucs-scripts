# 04: Device filters `--type` and `--device`

**What to build:** By default every real Device is extracted; an operator can narrow the run by device type and/or by Device name, repeating each filter to select several values.

See the parent spec: `.scratch/eucs-extract/spec.md`.

**Blocked by:** 01 — Walking skeleton

**Status:** ready-for-agent

- [x] `--type` accepts `ucsm`, `cimc`, `imm_domain`, `ucsc`, `intersight`, is repeatable, and rejects other values with a clear error.
- [x] `--device` matches Device names, is repeatable.
- [x] When both are given, a Device must match both filters.
- [x] Catalog Devices stay excluded whatever the filters.
- [x] When filters match no Device in an Instance, a clear message says so for that Instance.
- [x] Tests (CLI against the fake EasyUCS) cover: type filter, name filter, combined filters, repeated values, a filter matching nothing, an invalid type.

## Comments

Implemented on branch `04-device-filters`. Notes for the next tickets:

- `extract_instance` takes a `DeviceFilter` (`types`, `names`; empty means no narrowing). `DeviceFilter.selects` also drops Catalog Devices, so the orchestrator no longer checks `is_catalog` itself.
- `--device` is an exact, case-sensitive match on the name EasyUCS reports (not the sanitised folder name). `--type` is validated by Typer from the `DeviceType` enum, so invalid values exit with code 2 and list the accepted types.
- When an Instance has no selected Device, the orchestrator yields `NoDeviceSelected`. It is not a failure (exit code stays 0): with several Instances (05), a `--device` name will usually match in only one of them. The CLI prints "No Device of Instance X matches --type / --device", or "Instance X has no Device to extract" when no filter is given, and the summary table shows a "no Device" row. `summary.json` does not record it; the Instance appears as `succeeded` with no Devices.
- Every result type now has a `succeeded` property, and `all_succeeded` relies on it.
- `summary.json` `parameters` now also holds `device_types` and `device_names` (sorted, deduplicated lists).
