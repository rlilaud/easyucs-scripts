"""Build `dist/eucs` (`dist/eucs.exe` on Windows), a one-file executable of `eucs` for the current OS.

    python -m pip install . pyinstaller
    python scripts/build_executable.py

The executable embeds the Python running the build and the installed dependencies.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "pyinstaller"


def main() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",
            "--name",
            "eucs",
            "--clean",
            "--noconfirm",
            "--distpath",
            str(ROOT / "dist"),
            "--workpath",
            str(BUILD),
            "--specpath",
            str(BUILD),
            "--paths",
            str(ROOT / "src"),
            str(ROOT / "src" / "easyucs_scripts" / "__main__.py"),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
