# 01: Walking skeleton — `eucs extract --url` on one Instance, happy path

**What to build:** An operator can run `eucs extract --url <instance-root-url>` and get, for every real Device of that Instance, a freshly Fetched Config and Inventory saved under a timestamped run folder. This ticket lays down the project itself (package `easyucs_scripts`, console command `eucs`, Typer + Rich), the CI test pipeline, and the fake EasyUCS used by all later tests. Devices are processed one after another with plain console output; no progress bars, no failure handling beyond crashing cleanly.

See the parent spec: `.scratch/eucs-extract/spec.md` (API contract, output layout, testing seams).

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [x] Python ≥ 3.9 project with a single console command `eucs`; `eucs --version` prints the package version.
- [x] `eucs extract` exposes `--url` (single value for now) and `--output` (default `./extractions`), with English help text.
- [x] The tool appends `/api/v1` to the given root URL and never reads the `servers` URL of EasyUCS's published spec.
- [x] All HTTP to EasyUCS goes through one EasyUCS client per Instance, which lists Devices, starts a Fetch, polls the task until `successful`, locates the most recent Config and Inventory (listing ordered by timestamp descending), and downloads them.
- [x] Catalog Devices (`is_system == true`) are never extracted.
- [x] Output is written to `<output>/<run timestamp>/<instance name>/<device name>/config.json` and `inventory.json`; run timestamps contain no characters invalid on Windows; Instance name is derived from the URL host and port (e.g. `10.0.0.5_5010`); Device and Instance names are sanitised for Windows file names.
- [x] Two consecutive runs create two distinct run folders; nothing is overwritten.
- [x] Exit code is 0 when every Device succeeded.
- [x] A reusable fake EasyUCS (standard-library HTTP server in a background thread, scenario-configurable) implements the endpoints used so far; tests drive the real CLI in-process against it and assert only on exit code and files on disk.
- [x] Tests cover: happy path with several Devices including Catalog Devices, output layout, name sanitisation, two runs not colliding.
- [x] An optional integration test runs the CLI against a real Instance when `EUCS_TEST_URL` is set, and is skipped otherwise.
- [x] CI runs the test suite on every push on Windows, Linux and macOS.

## Comments

Implemented on branch `01-walking-skeleton`. Notes for the next tickets:

- The CI workflow (`.github/workflows/tests.yml`, Python 3.9 and 3.13) has not run on GitHub yet; Python 3.9 was not available locally.
- The fake EasyUCS completes every Fetch task immediately, so the `in_progress` polling loop is not exercised yet. Ticket 02 (hidden polling interval, `failed`/`skipped`/timeout scenarios) should make task status scenario-configurable.
- The Config/Inventory listing shape (`{"configs": [{"config_uuid", "timestamp"}]}`, `{"inventories": [{"inventory_uuid", ...}]}`) and query parameters are assumed; confirm with `EUCS_TEST_URL` against a real Instance.
- Unexpected response shapes (`KeyError`) and disk errors still end in a traceback; ticket 02 owns failure handling.
- Device names that sanitise to the same folder name get `_2`, `_3`... suffixes.
