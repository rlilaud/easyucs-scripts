from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterator, Optional

import pytest
from fake_easyucs import FakeEasyUCS
from typer.testing import CliRunner, Result

from easyucs_scripts.cli import app

RunEucs = Callable[..., Result]


@pytest.fixture
def fake_easyucs() -> Iterator[FakeEasyUCS]:
    with FakeEasyUCS() as fake:
        yield fake


@pytest.fixture
def run_eucs() -> RunEucs:
    """Invoke the real `eucs` command in-process with the given arguments, as plain text wide
    enough that Rich tables don't wrap."""

    def run(*args: str) -> Result:
        # Any FORCE_COLOR value, even "0", makes Rich style its output as for a terminal.
        env: dict[str, Optional[str]] = {"COLUMNS": "250", "FORCE_COLOR": None, "TTY_COMPATIBLE": None}
        return CliRunner(env=env).invoke(app, list(args))

    return run


RunExtract = Callable[..., Result]


@pytest.fixture
def run_extract(run_eucs: RunEucs) -> RunExtract:
    """Run `eucs extract --url <url> --output <output>` without waiting between task polls."""

    def run(url: str, output: Path, *extra: str) -> Result:
        return run_eucs("extract", "--url", url, "--output", str(output), "--poll-interval", "0", *extra)

    return run
