# 04: Device filters `--type` and `--device`

**What to build:** By default every real Device is extracted; an operator can narrow the run by device type and/or by Device name, repeating each filter to select several values.

See the parent spec: `.scratch/eucs-extract/spec.md`.

**Blocked by:** 01 — Walking skeleton

**Status:** ready-for-agent

- [ ] `--type` accepts `ucsm`, `cimc`, `imm_domain`, `ucsc`, `intersight`, is repeatable, and rejects other values with a clear error.
- [ ] `--device` matches Device names, is repeatable.
- [ ] When both are given, a Device must match both filters.
- [ ] Catalog Devices stay excluded whatever the filters.
- [ ] When filters match no Device in an Instance, a clear message says so for that Instance.
- [ ] Tests (CLI against the fake EasyUCS) cover: type filter, name filter, combined filters, repeated values, a filter matching nothing, an invalid type.
