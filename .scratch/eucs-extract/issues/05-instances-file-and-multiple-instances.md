# 05: Instances file and multiple Instances

**What to build:** An operator can list Instances in a YAML (or JSON) Instances file passed with `--instances`, repeat `--url`, or combine both; all listed Instances are extracted in one run (sequentially for now). The file format already reserves an authentication block so it won't break when EasyUCS adds authentication, while refusing plain-text passwords.

See the parent spec: `.scratch/eucs-extract/spec.md` (Instances file schema).

**Blocked by:** 01 — Walking skeleton

**Status:** ready-for-agent

- [ ] An Instances file loader (no network) returns validated Instance definitions or raises one validation error type whose message names the offending entry and field. It also builds definitions from bare `--url` values so both sources share one shape.
- [ ] File schema: top-level `instances:` list; per entry `url` (required), `name` (optional, derived from host and port when absent), `verify_tls` (optional, default true), `ca_bundle` (optional path), `auth` (optional). Unknown fields are rejected.
- [ ] Parsed with PyYAML's safe loader; JSON files are accepted.
- [ ] `auth` requires `type`; only `none` is accepted today, other types get a clear "not supported yet" error. `username` and `password_env` are reserved names; a literal `password` field is always rejected with an explanation pointing to `password_env`.
- [ ] Duplicate Instance names (explicit or derived, across file and `--url`) are rejected before any network call.
- [ ] `--url` is repeatable; `--instances` and `--url` combine; providing neither is a clear error.
- [ ] Unit tests on the loader (seam 2) cover: valid YAML, valid JSON, name derivation, duplicates, missing `url`, unknown field, `auth` absent, `type: none`, unsupported type, literal `password`, `verify_tls`/`ca_bundle` parsing, YAML syntax error, error messages pinpointing the entry.
- [ ] CLI tests against two fake EasyUCS Instances cover: file only, repeated `--url`, file plus `--url`, no source.
