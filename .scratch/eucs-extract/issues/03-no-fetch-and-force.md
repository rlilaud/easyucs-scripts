# 03: `--no-fetch` and `--force`

**What to build:** An operator can skip the live Fetch and just download the most recent stored Config and Inventory of each Device (`--no-fetch`), and can ask EasyUCS to force a Fetch past failed SDK objects or Intersight license validation (`--force`).

See the parent spec: `.scratch/eucs-extract/spec.md`.

**Blocked by:** 02 — Partial failures, summary and exit code

**Status:** ready-for-agent

- [x] With `--no-fetch`, no Fetch is started; the most recent stored Config and Inventory are downloaded and saved in the usual layout.
- [x] With `--no-fetch`, a Device with no stored Config or no stored Inventory is reported as failed with a reason hinting to run without `--no-fetch`.
- [x] `--force` is off by default; when set, the Fetch request carries `force: true`, otherwise `force: false`.
- [x] Help text documents `--force` as possibly producing an incomplete Config.
- [x] Tests (CLI against the fake EasyUCS) cover: `--no-fetch` with stored artifacts, `--no-fetch` without stored artifacts, and the `force` value received by the fake server with and without `--force`.

## Comments

Implemented on branch `03-no-fetch-and-force`. Notes for the next tickets:

- `summary.json` `parameters` now also holds `no_fetch` and `force` (booleans).
- `extract_instance` takes `fetch` (the inverse of `--no-fetch`) and `force`. The client raises `NothingStoredError`, a subclass of `EasyUCSError`, when a Device has no stored Config or Inventory; the orchestrator adds the `--no-fetch` hint only in skip-Fetch mode.
- `--force` combined with `--no-fetch` is accepted; `force` then has no effect since no Fetch is started.
- The fake EasyUCS records the `force` value of every Fetch request in `FakeDevice.fetch_forces`, and `add_device(..., stored_config=False, stored_inventory=False)` creates a Device with nothing stored.
