# Spec: `eucs extract` — bulk Extraction of Configs and Inventories from EasyUCS Instances

Status: ready-for-agent

## Problem Statement

I operate several EasyUCS Instances, and each Instance manages several Devices (UCS Manager, CIMC, IMM domains, UCS Central, Intersight). Whenever I need the current Config and Inventory of every Device, I have to open each Instance's UI, trigger a Fetch on each Device one by one, wait for it, and download the resulting files by hand. This is slow, error-prone, and does not scale with the number of Instances and Devices.

On top of that, many of the customer environments I work in are air-gapped or restrict downloading dependencies, so any tool I bring must run without internet access and without installing packages, on Windows and Linux (and ideally macOS).

## Solution

A command-line tool, `eucs`, whose first feature is `eucs extract`. Given one or more Instances (on the command line and/or in an Instances file), it discovers every real Device in each Instance, asks the Instance to Fetch a fresh Config and Inventory for each one (or skips the Fetch on request), waits for completion while showing live progress, downloads both artifacts, and saves them in a timestamped, never-overwritten output folder. At the end it prints a summary table, writes a machine-readable summary and a detailed log, and exits non-zero if anything failed.

The tool is shipped as self-contained artifacts: a standalone executable per OS that needs nothing installed, and a single universal zipapp file that runs with any Python 3.9+. It is designed so new features can be added as new subcommands reusing a shared EasyUCS client, and so authentication can be plugged in later without breaking the Instances file format.

All user-facing text (help, errors, documentation) is in English.

## User Stories

### Pointing the tool at Instances

1. As an operator, I want to pass one Instance URL on the command line, so that I can extract from a single Instance without writing any file.
2. As an operator, I want to repeat the URL option to pass several Instances, so that I can extract from a few Instances ad hoc.
3. As an operator, I want to pass an Instances file, so that I can keep a reusable list of all my Instances.
4. As an operator, I want to combine an Instances file and extra URLs in the same run, so that I can add a one-off Instance to my usual list.
5. As an operator, I want a clear error when I provide no Instance at all, so that the tool never silently targets something I didn't choose.
6. As an operator, I want to give the Instance root URL (as I type it in my browser), so that I don't need to know the API path.
7. As an operator, I want the Instances file to accept YAML, so that it is easy to read and edit by hand.
8. As an operator, I want the Instances file to also accept JSON, so that I can generate it from other tools.
9. As an operator, I want to give each Instance an optional short name, so that output folders and the summary are readable.
10. As an operator, I want a sensible name derived from the URL host and port when I don't give one, so that naming is optional.
11. As an operator, I want an error when two Instances end up with the same name, so that their outputs never collide.
12. As an operator, I want precise error messages when the Instances file is malformed (bad syntax, missing URL, unknown field, invalid value), including which entry is wrong, so that I can fix it quickly.

### Choosing Devices

13. As an operator, I want every real Device of every Instance to be extracted by default, so that "run it" means "get everything".
14. As an operator, I want Catalog Devices to be always excluded, so that runs don't fail on pseudo-Devices with no equipment behind them.
15. As an operator, I want to filter by device type (ucsm, cimc, imm_domain, ucsc, intersight), so that I can extract only the kinds of Devices I care about.
16. As an operator, I want to filter by Device name, so that I can extract a single Device or a handful of them.
17. As an operator, I want to repeat the type and name filters, so that I can select several types or several Devices at once.
18. As an operator, I want a clear message when my filters match no Device in an Instance, so that I know the filter, not the tool, is the cause.

### Fetching and downloading

19. As an operator, I want each Device to be Fetched live by default, so that I get its current Config and Inventory.
20. As an operator, I want an option to skip the Fetch and download the most recent stored Config and Inventory, so that I can get results quickly when freshness doesn't matter or a Device is unreachable.
21. As an operator, I want a Device with no stored Config or Inventory to be reported as failed with a hint to run without the skip-Fetch option, so that I understand why nothing was saved.
22. As an operator, I want both the Config and the Inventory of each Device to be saved, so that I have the complete picture in one run.
23. As an operator, I want an option to force the Fetch past failed SDK objects or Intersight license validation, so that I can still get a (possibly incomplete) Config from a problematic Device.
24. As an operator, I want the force option to be off by default and documented as possibly producing an incomplete Config, so that I don't get partial results by accident.
25. As an operator, I want a per-Device timeout on the Fetch (30 minutes by default, configurable), so that a stuck Device doesn't block the run forever.
26. As an operator, I want a Fetch reported as failed by EasyUCS to be recorded with EasyUCS's status message, so that I can see the root cause without opening EasyUCS.

### Progress, concurrency, and results

27. As an operator, I want all Instances to be processed in parallel, so that total run time is bounded by the slowest Instance rather than the sum.
28. As an operator, I want a bounded number of Devices processed concurrently per Instance (4 by default, configurable), so that I don't overload an EasyUCS Instance.
29. As an operator, I want a live progress bar per Device, driven by the progress EasyUCS reports, so that I can see the run advancing.
30. As an operator, I want the run to continue when one Device or one whole Instance fails, so that one problem doesn't cost me every other result.
31. As an operator, I want an unreachable Instance to be reported as failed in the summary, so that I notice it.
32. As an operator, I want a summary table at the end (Instance, Device, type, outcome, reason), so that I see at a glance what succeeded and what didn't.
33. As an operator, I want a non-zero exit code when at least one Device or Instance failed, so that I can use the tool in scripts and schedulers.
34. As an operator, I want a zero exit code when everything succeeded, so that automation can rely on it.

### Output on disk

35. As an operator, I want to choose the output directory (default `./extractions`), so that I control where files land.
36. As an operator, I want each run to go into its own timestamped folder, so that previous extractions are never overwritten and I keep history.
37. As an operator, I want files organised as run folder, then Instance, then Device, with a Config file and an Inventory file per Device, so that results are easy to navigate.
38. As an operator on Windows, I want Device and Instance names made safe for file names, so that names with special characters don't break the run.
39. As an operator, I want a machine-readable run summary in the run folder, so that other tools can consume the results.
40. As an operator, I want a detailed log file in the run folder, so that I can diagnose failures after the fact or send it to someone.
41. As an operator, I want a verbose option that also shows detailed logs on the console, so that I can troubleshoot interactively.
42. As a security-conscious operator, I want the log file and the console to never contain secrets or authentication headers, so that logs are safe to share.

### TLS

43. As an operator, I want TLS certificates to be verified by default for HTTPS Instances, so that I'm protected against interception.
44. As an operator with an internal PKI, I want to point an Instance at a CA bundle file, so that I can verify certificates issued by my company CA.
45. As an operator in a lab, I want to disable TLS verification for a specific Instance, so that I can work with self-signed certificates.
46. As an operator, I want a prominent warning on every run when TLS verification is disabled, so that I don't forget it's off.

### Authentication readiness

47. As an operator, I want the Instances file to accept an optional authentication block per Instance, so that my files keep working when EasyUCS adds authentication.
48. As an operator, I want only the "none" authentication type to be accepted today, with a clear error for any other type, so that I'm never misled into thinking credentials are used.
49. As a security-conscious operator, I want the tool to refuse plain-text passwords in the Instances file and instead read secrets from an environment variable or a masked interactive prompt, so that credentials never end up in shared files or repositories.

### Distribution and installation

50. As an operator in an air-gapped environment, I want a single standalone executable for Windows, so that I can copy one file and run it without installing anything.
51. As an operator in an air-gapped environment, I want a single standalone executable for Linux that runs on RHEL 8+, its rebuilds, Ubuntu 22.04+ and SLES 15 SP4+, so that it works on common supported enterprise distributions.
52. As an operator on macOS, I want a standalone executable too, with instructions to get past Gatekeeper since it isn't signed, so that I can use it on my laptop.
53. As an operator who has Python 3.9+ but can't install packages, I want a single universal zipapp file, so that I can run the tool with the Python that's already there on any OS.
54. As an operator, I want SHA-256 checksums published with every release, so that I can verify the files after transferring them into an air-gapped network.
55. As an operator, I want to print the tool version, so that I can report exactly what I'm running.
56. As an operator, I want every command and option to have English help text, so that I can learn the tool without external documentation.

### Maintainer

57. As the maintainer, I want releases (all artifacts plus checksums) to be built and published automatically when I push a version tag, so that releasing is one step.
58. As the maintainer, I want new features to be added as new subcommands that reuse a shared EasyUCS client, so that adding a feature doesn't require touching existing ones.
59. As the maintainer, I want all HTTP interaction with an Instance to go through one client, so that adding authentication later happens in one place.
60. As the maintainer, I want automated tests that run in CI on every pull request without any real EasyUCS, so that regressions are caught early.
61. As the maintainer, I want an optional integration test that runs against a real Instance when I provide its URL, so that I can check the tool against the real API.
62. As a future contributor, I want the README to explain why only pure-Python dependencies are allowed, so that I don't break the standalone and zipapp distributions by adding a compiled dependency.

## Implementation Decisions

### Shape of the application

- A modular monolith: one Python package (`easyucs_scripts`), one console command (`eucs`). The CLI uses Typer; all terminal rendering (progress, tables, warnings, help) uses Rich.
- Each feature is a subcommand in its own module, registered explicitly with the root command. No plugin discovery or entry-point mechanism (it would add complexity for a single-author tool and fits poorly with frozen executables).
- `eucs --version` prints the package version.

### Modules

- **Instances file loader**: turns an Instances file path into a validated list of Instance definitions, or raises a single validation error type whose message pinpoints the offending entry and field. Also builds Instance definitions from bare `--url` values so both sources share one shape. Enforces name derivation and uniqueness, TLS options consistency, and the authentication rules below. This module is pure (no network) and is its own test seam.
- **EasyUCS client**: one client per Instance, the only component that speaks HTTP to EasyUCS. Owns the base URL (root URL plus `/api/v1`), TLS settings, the future authentication hook, JSON error handling, listing Devices, starting a Fetch, polling a task until it reaches a terminal status or times out, locating the most recent Config and Inventory of a Device, and downloading them. Hides the API's asynchronous task model behind a simple "fetch and wait" operation. Future subcommands reuse it.
- **Extraction orchestrator**: given Instance definitions, filters and options, runs the Extraction across Instances in parallel with a bounded worker pool per Instance, collects a per-Device outcome (success, failure with reason), and reports progress events. It does not render anything itself.
- **Output writer**: creates the timestamped run folder and the Instance/Device tree, sanitises names for file systems (Windows rules included), writes the Config and Inventory files, the run summary, and the run log.
- **`extract` subcommand**: parses options, wires the modules together, renders progress bars and the final summary table with Rich, prints the TLS-disabled warning, and sets the exit code.

### EasyUCS API contract (as observed on EasyUCS, OpenAPI 3 spec served at `/easyucs.json`)

- API root is `<instance root URL>/api/v1`. The `servers` URL in EasyUCS's published spec is wrong (hard-coded port), so the tool never reads it; the user provides the root URL.
- List Devices: `GET /devices` returns `devices[]` with `device_uuid`, `device_name`, `device_type` (`cimc`, `ucsm`, `ucsc`, `imm_domain`, `intersight`), `is_system`, `system_usage`, `is_hidden`, `is_reachable`.
- Catalog Devices are those with `is_system == true` (observed with `system_usage == "catalog"` and names like `ucsm_catalog.easyucs`); they are always excluded.
- Fetch: `POST /devices/{device_uuid}/configs/actions/fetch`, then `POST /devices/{device_uuid}/inventories/actions/fetch`, each with body `{"force": <bool>}` and returning `{"task": <task_uuid>}`. The combined `POST /devices/{device_uuid}/actions/fetch_config_and_inventory` is not used: EasyUCS 1.0.6 refuses it for Intersight with HTTP 500 `"Unsupported device type"`. EasyUCS runs one task per Device at a time; a second task waits as `pending`.
- Task: `GET /tasks/{task_uuid}` returns `{"task": {...}}` (the published spec omits this wrapper) with `status` (`pending`, `in_progress`, `successful`, `failed`, `skipped`), `progress`, `status_message`, timestamps. `pending` and `in_progress` are unfinished; `successful` is the only success; anything else is a failure carrying `status_message`.
- The task payload does not reference the created Config/Inventory. After a successful Fetch, the most recent Config and Inventory are located by listing `GET /devices/{uuid}/configs` and `GET /devices/{uuid}/inventories` ordered by timestamp descending (`order_by_attribute=timestamp`, `order_by_direction=desc`, `page_size=1`). Listed items are identified by `uuid`. The same lookup serves the skip-Fetch mode.
- Download: `GET /devices/{uuid}/configs/{uuid}/actions/download` and `GET /devices/{uuid}/inventories/{uuid}/actions/download` return the file content (JSON), saved as-is.
- Errors come back as JSON `{"message": "..."}`; that message is surfaced to the operator.
- On the maintainer's lab, one Intersight Device takes about 3 minutes per Fetch (Config, then Inventory).
- EasyUCS currently declares no security scheme.

### CLI contract of `eucs extract`

- Instance sources: `--instances <file>` and/or `--url <root-url>` (repeatable); at least one required.
- Filters: `--type <device_type>` (repeatable), `--device <name>` (repeatable). No filter means all real Devices.
- Behaviour: `--no-fetch`, `--force` (off by default), `--timeout` (per-Device Fetch timeout, default 30 minutes, accepts short values), `--workers` (per-Instance concurrency, default 4), `--output <dir>` (default `./extractions`), `-v/--verbose`.
- A hidden, undocumented option controls the task polling interval (needed so tests don't wait).
- Exit code 0 when every selected Device succeeded; non-zero if any Device or Instance failed, or on invalid input.

### Instances file schema

- Top-level `instances:` list. Each entry: `url` (required), `name` (optional, derived from host and port such as `10.0.0.5_5010` when absent; duplicates rejected), `verify_tls` (optional, default true), `ca_bundle` (optional path; a relative path is relative to the Instances file's folder), `auth` (optional).
- Parsed with PyYAML's safe loader, which also accepts most JSON. Files ending in `.json` are parsed as JSON instead, because PyYAML rejects some valid JSON (tab indentation).
- `auth`: `type` is required inside the block; only `none` is accepted today, any other value is a clear error. The schema reserves `username` and `password_env` (name of an environment variable holding the secret; masked prompt if unset) for future types. A literal `password` field is always rejected with an explanation.
- Unknown fields are rejected, so typos don't pass silently.

### Output layout

- `<output>/<run timestamp>/<instance name>/<device name>/config.json` and `inventory.json`, plus `<output>/<run timestamp>/summary.json` and `run.log`. Run timestamps are file-system safe (no colons). Names are sanitised for Windows.
- `summary.json` records the run parameters (no secrets) and, per Device, Instance, name, type, outcome, reason, and paths of saved files; failed Instances appear with their reason.

### Security

- No credentials in files, logs, or console output. Authentication headers are never logged.
- TLS verification is on by default. `ca_bundle` supports internal PKIs; documentation tells users to check the bundle (`openssl x509 -text -noout -in <file>`: not expired, RSA ≥ 2048 or P-256+, SHA-2 signature). `verify_tls: false` triggers a visible warning on every run.

### Distribution

- Two artifact families, both built by GitHub Actions on a `vX.Y.Z` tag and attached to a GitHub Release with a SHA-256 checksums file:
  - PyInstaller one-file executables for Windows, Linux (built on a glibc 2.28 baseline: RHEL 8+ and its rebuilds, Ubuntu 22.04+, SLES 15 SP4+) and macOS (built in CI, unsigned, not tested by the maintainer; README documents the Gatekeeper workaround).
  - One universal zipapp (`.pyz`) running on Python ≥ 3.9 on any OS.
- Dependencies must be pure Python so the zipapp stays universal: Typer (with Click), Rich, `requests` (and its pure-Python dependencies), PyYAML used without its compiled `_yaml` extension (PyYAML falls back to its pure-Python implementation when the extension is absent; the zipapp build strips it). The README ends with a section explaining this constraint.
- End-of-life operating systems are not supported.
- Minimum Python for development and the zipapp: 3.9. The executables embed a recent Python.

## Testing Decisions

- Good tests exercise external behaviour only: what a user sees (exit code, files on disk and their content, `summary.json`, key messages) or what a module's public interface returns. They never assert on internal calls, private helpers, or HTTP library details, so refactoring internals doesn't break them.
- **Seam 1: the `eucs` command against a fake EasyUCS.** Tests invoke the real CLI in-process (Typer's test runner) against a fake EasyUCS: a small HTTP server built on the standard library, started in a background thread, implementing the endpoints listed in the API contract. Each test configures a scenario. Scenarios to cover at least:
  - happy path with several Devices across two Instances, including Catalog Devices that must be skipped;
  - type and name filters, including a filter matching nothing;
  - Fetch task ending `failed` and `skipped` (reason surfaced), task never finishing (timeout with a short `--timeout`);
  - `--no-fetch` with and without stored Config/Inventory;
  - `--force` forwarded to the Fetch request;
  - an unreachable Instance alongside a healthy one (run continues, non-zero exit);
  - `--workers` bound respected per Instance (the fake server records peak concurrency);
  - output layout, timestamped run folders not overwriting each other, Windows-unsafe Device names sanitised;
  - `summary.json` content and exit codes;
  - no-source error; TLS-disabled warning.
- **Seam 2: the Instances file loader.** Unit tests call the loader directly with YAML and JSON inputs: valid files, name derivation from URL, duplicate names, missing `url`, unknown fields, `auth` absent or `type: none` accepted, other auth types rejected, literal `password` rejected, `verify_tls` / `ca_bundle` handling, syntax errors, and error messages that pinpoint the entry.
- **Optional integration test**: when `EUCS_TEST_URL` is set, run the CLI against that real Instance through Seam 1's code path; skipped otherwise. Not run in CI.
- **Artifact smoke tests in CI**: the built executables and the zipapp are run with `--version` and with a short `extract` against the fake EasyUCS on each OS runner.
- Prior art: none; the repository has no code or tests yet. These tests establish the conventions.

## Out of Scope

- Any EasyUCS feature other than Config and Inventory Extraction (backups, reports, config push, device actions). These are future subcommands.
- Implementing any real authentication type; only the file schema and the single client hook are prepared.
- Deduplicating equipment registered in several Instances.
- Filtering by Device tags; selecting only Config or only Inventory.
- Including Catalog Devices in any mode.
- A plugin system or third-party extensions.
- Signing or notarising the macOS executable; code-signing the Windows executable.
- Supporting end-of-life operating systems (RHEL/CentOS 7, Ubuntu 20.04, and older).
- Publishing to PyPI.
- A wheelhouse distribution (superseded by the zipapp).

## Further Notes

- Domain vocabulary (Instance, Device, Catalog Device, Config, Inventory, Fetch, Extraction) is defined in `GLOSSARY.md` and should be used consistently in code, help text and documentation.
- The API facts above were read from a live EasyUCS instance; the maintainer's lab currently contains only UCS Central and Intersight Devices, so UCSM, CIMC and IMM domain behaviour is only covered by the fake EasyUCS until tested on real equipment.
- Fetch duration on large UCS Manager domains can reach several minutes; the default timeout and worker count are starting points to revisit with field feedback.
