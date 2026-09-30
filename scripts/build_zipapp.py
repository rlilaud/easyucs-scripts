"""Build `dist/eucs.pyz`, a zipapp bundling `eucs` and its dependencies that runs with any Python 3.9+ on any OS.

    python scripts/build_zipapp.py

Dependencies are resolved for the oldest supported Python, whatever Python runs the build. The
zipapp must hold only pure-Python code: a dependency installed as a compiled build is replaced
by its pure-Python wheel, PyYAML's optional `_yaml` extension is removed (PyYAML then uses its
pure-Python implementation), and the build fails if any compiled code is left.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
import sys
import tempfile
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGING = ROOT / "build" / "zipapp"
TARGET = ROOT / "dist" / "eucs.pyz"
OLDEST_PYTHON = "3.9"
# Click uses colorama on Windows only, so a build on another OS would not install it.
EXTRA_REQUIREMENTS = ["colorama"]
COMPILED_SUFFIXES = {".so", ".pyd", ".dll", ".dylib", ".exe"}
MAIN = 'import runpy\n\nrunpy.run_module("easyucs_scripts", run_name="__main__", alter_sys=True)\n'


def main() -> None:
    shutil.rmtree(STAGING, ignore_errors=True)
    install_dependencies()
    for dist_info in compiled_distributions():
        if dist_info.name.lower().startswith("pyyaml-"):
            remove_compiled_files(dist_info)
        else:
            replace_with_pure_wheel(dist_info)
    shutil.rmtree(STAGING / "bin", ignore_errors=True)
    compiled = compiled_files()
    if compiled:
        listing = "\n".join(f"  {path.relative_to(STAGING)}" for path in compiled)
        raise SystemExit(f"The zipapp must hold only pure-Python code, but these files are compiled:\n{listing}")
    (STAGING / "__main__.py").write_text(MAIN, encoding="utf-8")
    TARGET.parent.mkdir(exist_ok=True)
    zipapp.create_archive(STAGING, TARGET, interpreter="/usr/bin/env python3", compressed=True)
    print(f"Built {TARGET}")


def install_dependencies() -> None:
    with tempfile.TemporaryDirectory() as wheels:
        pip("wheel", "--no-deps", "--wheel-dir", wheels, str(ROOT))
        (wheel,) = Path(wheels).glob("*.whl")
        pip_install(str(wheel), *EXTRA_REQUIREMENTS)


def compiled_distributions() -> list[Path]:
    """The `.dist-info` folders of the installed distributions that contain compiled files."""
    return [
        dist_info
        for dist_info in sorted(STAGING.glob("*.dist-info"))
        if any(Path(path).suffix in COMPILED_SUFFIXES for path in recorded_files(dist_info))
    ]


def replace_with_pure_wheel(dist_info: Path) -> None:
    name, version = dist_info.name[: -len(".dist-info")].rsplit("-", 1)
    print(f"Replacing the compiled build of {name} {version} with its pure-Python wheel")
    remove_distribution(dist_info)
    pip_install(f"{name}=={version}", "--no-deps", "--platform", "any", "--implementation", "py", "--abi", "none")


def remove_distribution(dist_info: Path) -> None:
    for path in recorded_files(dist_info):
        (STAGING / path).unlink(missing_ok=True)
    shutil.rmtree(dist_info)
    for folder in sorted((p for p in STAGING.rglob("*") if p.is_dir()), reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir()


def remove_compiled_files(dist_info: Path) -> None:
    for path in recorded_files(dist_info):
        if Path(path).suffix in COMPILED_SUFFIXES:
            print(f"Removing the optional compiled extension {path}")
            (STAGING / path).unlink(missing_ok=True)


def recorded_files(dist_info: Path) -> list[str]:
    """The files a distribution installed in the staging folder, relative to it, from its `RECORD`.

    Console scripts are recorded outside it, as `../../bin/...`, and are left out.
    """
    with (dist_info / "RECORD").open(encoding="utf-8", newline="") as record:
        return [row[0] for row in csv.reader(record) if row and not row[0].startswith("..")]


def compiled_files() -> list[Path]:
    return sorted(path for path in STAGING.rglob("*") if path.suffix in COMPILED_SUFFIXES)


def pip_install(*args: str) -> None:
    pip(
        "install",
        "--target",
        str(STAGING),
        "--upgrade",
        "--no-compile",
        "--only-binary",
        ":all:",
        "--python-version",
        OLDEST_PYTHON,
        *args,
    )


def pip(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "pip", "--disable-pip-version-check", *args], check=True)


if __name__ == "__main__":
    main()
