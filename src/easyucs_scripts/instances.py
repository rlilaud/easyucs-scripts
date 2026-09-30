"""Instances file loader: validated Instance definitions, from an Instances file and bare `--url` values.

Pure: it reads the Instances file but never touches the network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence
from urllib.parse import urlsplit

import yaml

_ENTRY_FIELDS = ("url", "name", "verify_tls", "ca_bundle", "auth")
_AUTH_FIELDS = ("type", "username", "password_env")
_SUPPORTED_AUTH_TYPES = ("none",)


class InstanceDefinitionError(ValueError):
    """An Instance definition is invalid. The message pinpoints the source, entry and field."""


@dataclass(frozen=True)
class Instance:
    url: str
    name: str
    verify_tls: bool = True
    ca_bundle: Optional[Path] = None


def resolve_instances(instances_file: Optional[Path], urls: Sequence[str]) -> list[Instance]:
    """The Instances listed in `instances_file`, then one per URL in `urls`, with distinct names."""
    instances = [] if instances_file is None else _load_file(instances_file)
    for url in urls:
        try:
            instances.append(Instance(url=url, name=_name_from_url(url)))
        except InstanceDefinitionError as exc:
            raise InstanceDefinitionError(f"--url: {exc}") from None
    _check_distinct_names(instances)
    return instances


def _load_file(path: Path) -> list[Instance]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InstanceDefinitionError(f"Cannot read Instances file {path}: {exc}") from None
    document = _parse(path, text)
    if not isinstance(document, dict):
        raise InstanceDefinitionError(f"{path}: expected a top-level 'instances' list")
    unknown = [key for key in document if key != "instances"]
    if unknown:
        raise InstanceDefinitionError(f"{path}: unknown top-level field {unknown[0]!r}; only 'instances' is accepted")
    if "instances" not in document:
        raise InstanceDefinitionError(f"{path}: expected a top-level 'instances' list")
    entries = document["instances"]
    if not isinstance(entries, list):
        raise InstanceDefinitionError(f"{path}: 'instances' must be a list of Instance entries")
    if not entries:
        raise InstanceDefinitionError(f"{path}: 'instances' must list at least one Instance")
    return [_parse_entry(entry, _EntryContext(path, position, entry)) for position, entry in enumerate(entries, 1)]


def _parse(path: Path, text: str) -> Any:
    # PyYAML does not accept every JSON document (tab indentation, for one), hence the JSON parser.
    if path.suffix.lower() == ".json":
        try:
            return json.loads(text)
        except ValueError as exc:
            raise InstanceDefinitionError(f"{path} is not valid JSON: {exc}") from None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise InstanceDefinitionError(f"{path} is not valid YAML or JSON: {exc}") from None


class _EntryContext:
    """Where an entry sits in the Instances file, to build error messages that pinpoint it."""

    def __init__(self, path: Path, position: int, entry: Any) -> None:
        self.path = path
        name = entry.get("name") if isinstance(entry, dict) else None
        self.label = f"entry {position}" + (f" ({name!r})" if isinstance(name, str) and name else "")

    def error(self, problem: str, field: Optional[str] = None) -> InstanceDefinitionError:
        where = self.label if field is None else f"{self.label}, field {field!r}"
        return InstanceDefinitionError(f"{self.path}, {where}: {problem}")


def _parse_entry(entry: Any, context: _EntryContext) -> Instance:
    if not isinstance(entry, dict):
        raise context.error("expected a mapping with at least a 'url' field")
    _reject_unknown_fields(entry, _ENTRY_FIELDS, context, None)

    url = entry.get("url")
    if url is None:
        raise context.error("is required", "url")
    if not isinstance(url, str):
        raise context.error("must be a URL such as http://10.0.0.5:5010", "url")
    try:
        derived_name = _name_from_url(url)
    except InstanceDefinitionError as exc:
        raise context.error(str(exc), "url") from None

    name = entry.get("name", derived_name)
    if not isinstance(name, str) or not name:
        raise context.error("must be a non-empty text", "name")

    verify_tls = entry.get("verify_tls", True)
    if not isinstance(verify_tls, bool):
        raise context.error("must be true or false", "verify_tls")

    ca_bundle = entry.get("ca_bundle")
    if ca_bundle is not None:
        if not isinstance(ca_bundle, str) or not ca_bundle:
            raise context.error("must be the path of a CA bundle file", "ca_bundle")
        if not verify_tls:
            raise context.error("'ca_bundle' is only used to verify TLS; remove it or set 'verify_tls: true'")

    if "auth" in entry:
        _check_auth(entry["auth"], context)

    return Instance(
        url=url,
        name=name,
        verify_tls=verify_tls,
        ca_bundle=None if ca_bundle is None else context.path.parent / ca_bundle,
    )


def _check_auth(auth: Any, context: _EntryContext) -> None:
    if not isinstance(auth, dict):
        raise context.error("must be a mapping with at least a 'type' field, e.g. 'type: none'", "auth")
    if "password" in auth:
        raise context.error(
            "plain-text passwords are not allowed in the Instances file; set 'password_env' to the name"
            " of an environment variable holding the password instead",
            "auth.password",
        )
    _reject_unknown_fields(auth, _AUTH_FIELDS, context, "auth")
    auth_type = auth.get("type")
    if auth_type is None:
        raise context.error("is required", "auth.type")
    if auth_type not in _SUPPORTED_AUTH_TYPES:
        raise context.error(
            f"authentication type {auth_type!r} is not supported yet; only 'none' is accepted", "auth.type"
        )
    for field in ("username", "password_env"):
        if field in auth and not isinstance(auth[field], str):
            raise context.error("must be a text", f"auth.{field}")


def _reject_unknown_fields(
    mapping: dict[Any, Any], accepted: Sequence[str], context: _EntryContext, parent: Optional[str]
) -> None:
    for key in mapping:
        if key not in accepted:
            field = str(key) if parent is None else f"{parent}.{key}"
            raise context.error(f"unknown field; accepted fields are {', '.join(accepted)}", field)


def _name_from_url(url: str) -> str:
    """The Instance name derived from the URL's host and port (e.g. `10.0.0.5_5010`)."""
    parts = urlsplit(url)
    if parts.username is not None or parts.password is not None:
        # The URL is not echoed back: it holds a secret.
        raise InstanceDefinitionError("Instance URLs must not contain credentials (user:password@host)")
    invalid_url_error = InstanceDefinitionError(
        f"{url!r} is not a valid Instance URL; expected http(s)://<host>[:<port>]"
    )
    try:
        port = parts.port
    except ValueError:
        raise invalid_url_error from None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise invalid_url_error
    return parts.hostname if port is None else f"{parts.hostname}_{port}"


def _check_distinct_names(instances: Sequence[Instance]) -> None:
    seen: dict[str, Instance] = {}
    for instance in instances:
        other = seen.setdefault(instance.name, instance)
        if other is not instance:
            raise InstanceDefinitionError(
                f"Two Instances are named {instance.name!r} ({other.url} and {instance.url});"
                " give them distinct names with 'name' in the Instances file"
            )
