# 09: Standalone artifacts built and smoke-tested in CI

**What to build:** CI produces the two distribution families on every push, so an operator can grab a self-contained artifact: a one-file executable for Windows, Linux and macOS that needs nothing installed, and a single universal zipapp that runs with any Python ≥ 3.9. Each artifact is proven to work before it's kept.

See the parent spec: `.scratch/eucs-extract/spec.md` (Distribution).

**Blocked by:** 01 — Walking skeleton; 05 — Instances file and multiple Instances

**Status:** ready-for-agent

- [ ] PyInstaller one-file executables are built for Windows, macOS and Linux; the Linux build runs on a glibc 2.28 baseline (RHEL 8 era) so it works on RHEL 8+, its rebuilds, Ubuntu 22.04+ and SLES 15 SP4+.
- [ ] A universal zipapp (`.pyz`) is built bundling all dependencies; PyYAML's compiled `_yaml` extension is stripped so the pure-Python implementation is used on every platform.
- [ ] CI fails if any bundled dependency of the zipapp contains compiled code.
- [ ] Each executable is smoke-tested on its OS runner: `--version`, then a short `extract` against the fake EasyUCS producing the expected files.
- [ ] The zipapp is smoke-tested the same way with the oldest supported Python (3.9) and a recent one.
- [ ] Artifacts are uploaded as CI build artifacts.
