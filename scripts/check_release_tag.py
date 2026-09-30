"""Check that a release tag names the package version, so that a release prints its tag's version.

    python scripts/check_release_tag.py v1.2.3

The tag must be `v` followed by `__version__` from `src/easyucs_scripts/__init__.py`. Only the
standard library is used, and the package is read as text rather than imported.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def package_version() -> str:
    init = (ROOT / "src" / "easyucs_scripts" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "([^"]+)"', init, re.MULTILINE)
    if match is None:
        raise SystemExit("__version__ not found in src/easyucs_scripts/__init__.py")
    return match.group(1)


def main(tag: str) -> None:
    expected = f"v{package_version()}"
    if tag != expected:
        raise SystemExit(
            f"Tag {tag!r} does not name the package version: expected {expected!r}."
            " Set __version__ in src/easyucs_scripts/__init__.py, then tag that commit."
        )
    print(f"Tag {tag} names the package version")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
