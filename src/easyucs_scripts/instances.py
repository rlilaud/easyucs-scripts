"""Instance definitions, built from bare `--url` values."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Instance:
    url: str
    name: str


def instance_from_url(url: str) -> Instance:
    """Build an Instance named after the URL's host and port (e.g. `10.0.0.5_5010`)."""
    invalid_url_error = ValueError(f"{url!r} is not a valid Instance URL; expected http(s)://<host>[:<port>]")
    parts = urlsplit(url)
    try:
        port = parts.port
    except ValueError:
        raise invalid_url_error from None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise invalid_url_error
    name = parts.hostname if port is None else f"{parts.hostname}_{port}"
    return Instance(url=url, name=name)
