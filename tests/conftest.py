from __future__ import annotations

from typing import Callable, Iterator

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
    """Invoke the real `eucs` command in-process with the given arguments."""

    def run(*args: str) -> Result:
        return CliRunner().invoke(app, list(args))

    return run
