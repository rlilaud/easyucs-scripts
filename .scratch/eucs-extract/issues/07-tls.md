# 07: TLS verification, CA bundle and opt-out

**What to build:** HTTPS Instances are verified against trusted CAs by default; an operator can point an Instance at an internal CA bundle, or, as a last resort, disable verification for one Instance and be warned about it on every run.

See the parent spec: `.scratch/eucs-extract/spec.md` (Security).

**Blocked by:** 02 — Partial failures, summary and exit code; 05 — Instances file and multiple Instances

**Status:** ready-for-agent

- [ ] TLS certificates are verified by default.
- [ ] `ca_bundle` in an Instances file entry makes the client verify against that bundle; a missing or unreadable bundle file is a clear error before any extraction.
- [ ] `verify_tls: false` disables verification for that Instance only, and a prominent warning naming the Instance is printed on every run.
- [ ] A certificate verification failure is reported as a failed Instance with an explanatory reason (suggesting `ca_bundle`).
- [ ] The fake EasyUCS can serve HTTPS with a test certificate generated at test time; no certificate or private key is committed to the repository.
- [ ] Tests cover: untrusted certificate fails by default, succeeds with `ca_bundle`, succeeds with `verify_tls: false` and shows the warning, missing bundle file error.
