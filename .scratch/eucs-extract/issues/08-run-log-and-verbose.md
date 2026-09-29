# 08: Run log and verbose mode

**What to build:** Every run leaves a detailed `run.log` in its run folder (requests, task statuses, full errors) that the operator can use or share to diagnose problems; `-v` also shows that detail on the console. Logs never contain secrets.

See the parent spec: `.scratch/eucs-extract/spec.md`.

**Blocked by:** 02 — Partial failures, summary and exit code

**Status:** ready-for-agent

- [ ] `run.log` is written in the run folder for every run, including failed ones.
- [ ] It records requested endpoints and HTTP statuses, task status transitions, and full error details for failed Devices and Instances.
- [ ] Without `-v` the console shows only progress, warnings and the summary; with `-v/--verbose` it also shows the detailed log.
- [ ] Authentication headers and any secret values are never written to the log or console.
- [ ] Tests (CLI against the fake EasyUCS) cover: `run.log` exists and mentions a failed Device's reason; verbose output contains detail absent from normal output; a request carrying an `Authorization` header (injected by the test through the client's auth hook) never shows the header value in `run.log` or console.
