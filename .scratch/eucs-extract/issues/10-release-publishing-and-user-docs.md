# 10: Release publishing and user documentation

**What to build:** Pushing a `vX.Y.Z` tag publishes a GitHub Release carrying all artifacts and a SHA-256 checksums file, and the README tells an operator, in English, everything needed to install and use the tool in an air-gapped environment.

See the parent spec: `.scratch/eucs-extract/spec.md`.

**Blocked by:** 02, 03, 04, 05, 06, 07, 08, 09

**Status:** ready-for-agent

- [x] Pushing a `vX.Y.Z` tag builds all artifacts (reusing 09) and publishes them to a GitHub Release with a SHA-256 checksums file.
- [x] The released version matches the tag and is what `eucs --version` prints.
- [x] README (English) covers: what the tool does (using the `GLOSSARY.md` vocabulary), air-gap installation for each artifact including checksum verification, supported OS and minimum Python, `eucs extract` usage and every option, Instances file format with examples (including the reserved `auth` block and `password_env`, and why plain passwords are refused), output layout, exit codes, TLS options and how to check a `ca_bundle` with `openssl x509 -text -noout -in <file>` (not expired, RSA ≥ 2048 or P-256+, SHA-2 signature), and how to run the unsigned macOS executable past Gatekeeper.
- [x] README ends with a section explaining why only pure-Python dependencies are allowed (standalone executables and universal zipapp) and that PyYAML is used without its compiled extension.

## Comments

- 2026-09-30: the tag is checked against `__version__` in a first `release-tag` job that every build job waits for, so a forgotten version bump fails before any macOS minutes are spent. Release assets are `eucs-windows-x86_64.exe`, `eucs-linux-x86_64`, `eucs-macos-arm64`, `eucs.pyz` and `SHA256SUMS` (`sha256sum` format). A failing macOS build or smoke test blocks the whole release, since the issue asks for all artifacts.
