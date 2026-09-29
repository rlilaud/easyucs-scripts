# 02: Partial failures, summary and exit code

**What to build:** When a Device's Fetch fails, is skipped, times out, or the Instance itself is unreachable, the run keeps going with everything else. At the end the operator sees a Rich summary table (Instance, Device, type, outcome, reason), finds a machine-readable `summary.json` in the run folder, and gets a non-zero exit code if anything failed.

See the parent spec: `.scratch/eucs-extract/spec.md`.

**Blocked by:** 01 — Walking skeleton

**Status:** ready-for-agent

- [x] A task ending `failed` or `skipped` marks the Device as failed with EasyUCS's `status_message` as the reason; other Devices still get extracted.
- [x] `--timeout` sets the per-Device Fetch timeout (default 30 minutes) and accepts short values; a task still `in_progress` past the timeout marks the Device as failed with a timeout reason.
- [x] A hidden option (absent from help) sets the task polling interval, so tests run fast.
- [x] An unreachable Instance, or one returning HTTP errors, is recorded as a failed Instance with a reason; the run does not crash.
- [x] A Rich summary table is printed at the end of every run.
- [x] `summary.json` in the run folder records the run parameters (no secrets) and, per Device: Instance, name, type, outcome, reason, and paths of saved files; failed Instances appear with their reason.
- [x] Exit code is 0 only if every selected Device succeeded; non-zero otherwise.
- [x] Tests (CLI against the fake EasyUCS) cover: failed task, skipped task, timeout, unreachable Instance, `summary.json` content, and both exit codes.

## Comments

Implemented on branch `02-partial-failures`. Notes for the next tickets:

- `--timeout` accepts `90s`, `30m`, `1h` or a bare number of seconds. It bounds the whole Fetch of a Device (Config then Inventory, `pending` time included), not each task.
- `summary.json` shape: `parameters` (`urls`, `output`, `timeout_seconds`), `succeeded`, `instances[]` (`name`, `url`, `outcome`, `reason`) and `devices[]` (`instance`, `name`, `type`, `outcome`, `reason`, `files`). Outcomes are `succeeded` / `failed`; `files` holds paths relative to the run folder with `/` separators, and is empty for a failed Device. Tickets 03 and 04 should add their options to `parameters`.
- Instance URLs embedding credentials (`user:password@host`) are rejected, so no secret can reach `summary.json`, the console or error messages.
- Responses missing expected fields now fail the Device or Instance with an "unexpected response" reason instead of a traceback. Disk errors while saving fail the Device.
- CLI tests run with `COLUMNS=250` and without `FORCE_COLOR`/`TTY_COMPATIBLE` so Rich output is plain and unwrapped regardless of the developer's shell.
