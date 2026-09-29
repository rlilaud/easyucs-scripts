# 03: `--no-fetch` and `--force`

**What to build:** An operator can skip the live Fetch and just download the most recent stored Config and Inventory of each Device (`--no-fetch`), and can ask EasyUCS to force a Fetch past failed SDK objects or Intersight license validation (`--force`).

See the parent spec: `.scratch/eucs-extract/spec.md`.

**Blocked by:** 02 — Partial failures, summary and exit code

**Status:** ready-for-agent

- [ ] With `--no-fetch`, no Fetch is started; the most recent stored Config and Inventory are downloaded and saved in the usual layout.
- [ ] With `--no-fetch`, a Device with no stored Config or no stored Inventory is reported as failed with a reason hinting to run without `--no-fetch`.
- [ ] `--force` is off by default; when set, the Fetch request carries `force: true`, otherwise `force: false`.
- [ ] Help text documents `--force` as possibly producing an incomplete Config.
- [ ] Tests (CLI against the fake EasyUCS) cover: `--no-fetch` with stored artifacts, `--no-fetch` without stored artifacts, and the `force` value received by the fake server with and without `--force`.
