from __future__ import annotations

import ssl
from pathlib import Path
from typing import Callable, Iterator, Optional, Sequence

import pytest
import trustme
from fake_easyucs import FakeEasyUCS
from typer.testing import CliRunner, Result

from easyucs_scripts.cli import app

RunEucs = Callable[..., Result]


@pytest.fixture
def fake_easyucs() -> Iterator[FakeEasyUCS]:
    with FakeEasyUCS() as fake:
        yield fake


@pytest.fixture
def other_easyucs() -> Iterator[FakeEasyUCS]:
    """A second fake EasyUCS Instance, for runs over several Instances."""
    with FakeEasyUCS() as fake:
        yield fake


@pytest.fixture(scope="session")
def test_ca() -> trustme.CA:
    """A certificate authority that no system trusts, generated for this test session only."""
    return trustme.CA()


@pytest.fixture
def https_easyucs(test_ca: trustme.CA) -> Iterator[FakeEasyUCS]:
    """A fake EasyUCS Instance serving HTTPS with a certificate issued by `test_ca`."""
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    test_ca.issue_cert("127.0.0.1").configure_cert(context)
    with FakeEasyUCS(tls=context) as fake:
        yield fake


@pytest.fixture
def run_eucs() -> RunEucs:
    """Invoke the real `eucs` command in-process with the given arguments, as plain text wide
    enough that Rich tables don't wrap."""

    def run(*args: str) -> Result:
        # Any FORCE_COLOR value, even "0", makes Rich style its output as for a terminal, and
        # Typer's help does the same under GITHUB_ACTIONS unless _TYPER_FORCE_DISABLE_TERMINAL is set.
        env: dict[str, Optional[str]] = {
            "COLUMNS": "250",
            "FORCE_COLOR": None,
            "TTY_COMPATIBLE": None,
            "_TYPER_FORCE_DISABLE_TERMINAL": "1",
        }
        return CliRunner(env=env).invoke(app, list(args))

    return run


RunExtractFrom = Callable[..., Result]


@pytest.fixture
def run_extract_from(run_eucs: RunEucs) -> RunExtractFrom:
    """Run `eucs extract <sources> --output <output>` without waiting between task polls, where
    `sources` are the `--instances` and `--url` options."""

    def run(sources: Sequence[str], output: Path, *extra: str) -> Result:
        return run_eucs("extract", *sources, "--output", str(output), "--poll-interval", "0", *extra)

    return run


RunExtract = Callable[..., Result]


@pytest.fixture
def run_extract(run_extract_from: RunExtractFrom) -> RunExtract:
    """Run `eucs extract --url <url> --output <output>` without waiting between task polls."""

    def run(url: str, output: Path, *extra: str) -> Result:
        return run_extract_from(["--url", url], output, *extra)

    return run
