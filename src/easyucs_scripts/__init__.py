"""Command-line tools for EasyUCS Instances."""

import logging

__version__ = "0.1.0"

# Outside a run log, what the package logs goes nowhere rather than to stderr.
logging.getLogger(__name__).addHandler(logging.NullHandler())
