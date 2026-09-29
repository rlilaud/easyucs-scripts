# 06: Parallelism and live progress

**What to build:** All Instances are processed at the same time, each with a bounded number of Devices in flight, and the operator watches one live Rich progress bar per Device driven by the progress EasyUCS reports. A failure stays confined to its Device or Instance.

See the parent spec: `.scratch/eucs-extract/spec.md`.

**Blocked by:** 02 — Partial failures, summary and exit code; 05 — Instances file and multiple Instances

**Status:** ready-for-agent

- [ ] Instances are processed in parallel.
- [ ] `--workers` (default 4) bounds concurrent Devices per Instance.
- [ ] One Rich progress bar per Device, updated from the task's `progress` field, ending in a visible success or failure state.
- [ ] The orchestration reports progress events and outcomes without rendering; rendering lives in the `extract` subcommand.
- [ ] Summary, `summary.json` and exit code behave exactly as in 02 under parallel execution.
- [ ] Tests (CLI against the fake EasyUCS) cover: the fake server records peak concurrent Fetches per Instance and it never exceeds `--workers`; two Instances progress simultaneously; one failing Device or Instance doesn't affect the others' outputs.
