# 02: Partial failures, summary and exit code

**What to build:** When a Device's Fetch fails, is skipped, times out, or the Instance itself is unreachable, the run keeps going with everything else. At the end the operator sees a Rich summary table (Instance, Device, type, outcome, reason), finds a machine-readable `summary.json` in the run folder, and gets a non-zero exit code if anything failed.

See the parent spec: `.scratch/eucs-extract/spec.md`.

**Blocked by:** 01 — Walking skeleton

**Status:** ready-for-agent

- [ ] A task ending `failed` or `skipped` marks the Device as failed with EasyUCS's `status_message` as the reason; other Devices still get extracted.
- [ ] `--timeout` sets the per-Device Fetch timeout (default 30 minutes) and accepts short values; a task still `in_progress` past the timeout marks the Device as failed with a timeout reason.
- [ ] A hidden option (absent from help) sets the task polling interval, so tests run fast.
- [ ] An unreachable Instance, or one returning HTTP errors, is recorded as a failed Instance with a reason; the run does not crash.
- [ ] A Rich summary table is printed at the end of every run.
- [ ] `summary.json` in the run folder records the run parameters (no secrets) and, per Device: Instance, name, type, outcome, reason, and paths of saved files; failed Instances appear with their reason.
- [ ] Exit code is 0 only if every selected Device succeeded; non-zero otherwise.
- [ ] Tests (CLI against the fake EasyUCS) cover: failed task, skipped task, timeout, unreachable Instance, `summary.json` content, and both exit codes.
