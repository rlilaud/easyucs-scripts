# 05: Instances file and multiple Instances

**What to build:** An operator can list Instances in a YAML (or JSON) Instances file passed with `--instances`, repeat `--url`, or combine both; all listed Instances are extracted in one run (sequentially for now). The file format already reserves an authentication block so it won't break when EasyUCS adds authentication, while refusing plain-text passwords.

See the parent spec: `.scratch/eucs-extract/spec.md` (Instances file schema).

**Blocked by:** 01 — Walking skeleton

**Status:** ready-for-agent

- [x] An Instances file loader (no network) returns validated Instance definitions or raises one validation error type whose message names the offending entry and field. It also builds definitions from bare `--url` values so both sources share one shape.
- [x] File schema: top-level `instances:` list; per entry `url` (required), `name` (optional, derived from host and port when absent), `verify_tls` (optional, default true), `ca_bundle` (optional path), `auth` (optional). Unknown fields are rejected.
- [x] Parsed with PyYAML's safe loader; JSON files are accepted.
- [x] `auth` requires `type`; only `none` is accepted today, other types get a clear "not supported yet" error. `username` and `password_env` are reserved names; a literal `password` field is always rejected with an explanation pointing to `password_env`.
- [x] Duplicate Instance names (explicit or derived, across file and `--url`) are rejected before any network call.
- [x] `--url` is repeatable; `--instances` and `--url` combine; providing neither is a clear error.
- [x] Unit tests on the loader (seam 2) cover: valid YAML, valid JSON, name derivation, duplicates, missing `url`, unknown field, `auth` absent, `type: none`, unsupported type, literal `password`, `verify_tls`/`ca_bundle` parsing, YAML syntax error, error messages pinpointing the entry.
- [x] CLI tests against two fake EasyUCS Instances cover: file only, repeated `--url`, file plus `--url`, no source.

## Comments

Implemented on branch `05-instances-file-and-multiple-instances`. Notes for the next tickets:

- The loader's single entry point is `resolve_instances(instances_file, urls)` in `instances.py`: file entries first, then one Instance per `--url`, then a name-uniqueness check. Every problem raises `InstanceDefinitionError` (a `ValueError`), whose message names the file, the entry (`entry 2`, plus `('name')` when it has one) and the field (`'auth.type'`). URLs holding credentials are never echoed back. The CLI turns it into a usage error (exit code 2) before creating the run folder.
- Files ending in `.json` are parsed with the `json` module, because PyYAML rejects some valid JSON (tab indentation). Every other file goes through `yaml.safe_load`.
- `Instance` now carries `verify_tls` (default `True`) and `ca_bundle` (`Optional[Path]`), parsed and validated but **not used yet**: the client ignores them until 07. A relative `ca_bundle` is resolved against the Instances file's folder, so a file and its bundle can be moved together. `ca_bundle` together with `verify_tls: false` is rejected as contradictory. The loader does not check that the bundle file exists; 07 owns that.
- `auth` is validated and then dropped: `Instance` has no auth field while `none` is the only accepted type.
- Instances are extracted one after another in the order given (06 parallelises this loop in `commands/extract.py`).
- Two Instance names that only differ once sanitised for file names (`lab:a`, `lab/a`) get distinct folders (`lab_a`, `lab_a_2`), as Devices already did. `RunFolder` remembers each Instance's folder.
- `summary.json` `parameters` now has `instances_file` (path as given, or `null`) and `urls` (only the `--url` values). Each Instance's URL is in `instances`.
- PyYAML is a new runtime dependency (`types-PyYAML` for mypy). The zipapp build (09) must strip its compiled `_yaml` extension.
- Tests: `other_easyucs` is a second fake EasyUCS fixture; `run_extract_from(sources, output, *extra)` runs `extract` with any mix of `--instances` / `--url`.
