"""The run log: the detailed record of a run, written to a file and, in verbose mode, to the console.

Modules log through `logging.getLogger(__name__)`; everything under the `easyucs_scripts`
logger ends up in the run log. Nothing logged may contain a secret or an authentication header.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from rich.console import Console
from rich.logging import RichHandler

_PACKAGE_LOGGER = logging.getLogger("easyucs_scripts")
_FILE_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"


@contextmanager
def run_log(path: Path, console: Optional[Console]) -> Iterator[None]:
    """Record everything the package logs to `path`, and to `console` if given, until the block ends."""
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(_FILE_FORMAT))
    handlers: list[logging.Handler] = [file_handler]
    if console is not None:
        handlers.append(RichHandler(console=console, show_path=False, log_time_format="%H:%M:%S"))
    previous_level = _PACKAGE_LOGGER.level
    _PACKAGE_LOGGER.setLevel(logging.DEBUG)
    for handler in handlers:
        _PACKAGE_LOGGER.addHandler(handler)
    try:
        yield
    finally:
        for handler in handlers:
            _PACKAGE_LOGGER.removeHandler(handler)
            handler.close()
        _PACKAGE_LOGGER.setLevel(previous_level)
