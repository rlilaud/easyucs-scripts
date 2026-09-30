import subprocess
import sys
from pathlib import Path

import pytest

import easyucs_scripts

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_release_tag.py"
EXPECTED_TAG = f"v{easyucs_scripts.__version__}"


def check_release_tag(tag: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), tag], capture_output=True, text=True)


def test_a_tag_naming_the_package_version_passes() -> None:
    result = check_release_tag(EXPECTED_TAG)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("tag", ["v99.0.0", easyucs_scripts.__version__, f"{EXPECTED_TAG}-rc1"])
def test_a_tag_not_naming_the_package_version_fails_and_says_why(tag: str) -> None:
    result = check_release_tag(tag)

    assert result.returncode != 0
    assert tag in result.stderr
    assert EXPECTED_TAG in result.stderr
