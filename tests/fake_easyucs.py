"""A fake EasyUCS Instance: a standard-library HTTP server serving the API under `/api/v1`.

Tests build a scenario by adding Devices, point `eucs` at `FakeEasyUCS.url`, and inspect
the Devices afterwards. Every Device starts with one stored Config and Inventory; each
Fetch stores a new, distinguishable pair, so tests can tell fresh artifacts from stale ones.
"""

from __future__ import annotations

import itertools
import json
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, Optional
from urllib.parse import parse_qs, urlsplit

API_PREFIX = "/api/v1"
_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


@dataclass
class StoredArtifact:
    uuid: str
    timestamp: str
    content: bytes


@dataclass
class FakeDevice:
    name: str
    device_type: str
    is_system: bool
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    configs: list[StoredArtifact] = field(default_factory=list)
    inventories: list[StoredArtifact] = field(default_factory=list)
    fetch_count: int = 0

    @property
    def latest_config(self) -> bytes:
        return max(self.configs, key=lambda a: a.timestamp).content

    @property
    def latest_inventory(self) -> bytes:
        return max(self.inventories, key=lambda a: a.timestamp).content


class FakeEasyUCS:
    def __init__(self) -> None:
        self.devices: list[FakeDevice] = []
        self._tasks: dict[str, dict[str, Any]] = {}
        self._clock = itertools.count(1)
        self._lock = threading.Lock()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_for(self))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> FakeEasyUCS:
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()

    def add_device(self, name: str, device_type: str = "ucsm", *, is_system: bool = False) -> FakeDevice:
        device = FakeDevice(name=name, device_type=device_type, is_system=is_system)
        self._store_artifacts(device)
        self.devices.append(device)
        return device

    def _store_artifacts(self, device: FakeDevice) -> None:
        timestamp = (_EPOCH + timedelta(minutes=next(self._clock))).isoformat()
        for kind, store in (("config", device.configs), ("inventory", device.inventories)):
            content = json.dumps({"device": device.name, kind: f"fetch #{device.fetch_count}"}).encode()
            store.append(StoredArtifact(uuid=str(uuid.uuid4()), timestamp=timestamp, content=content))

    # Request handling, called from the server threads.

    def handle(self, method: str, path: str, query: dict[str, list[str]]) -> tuple[int, Any]:
        with self._lock:
            if not path.startswith(API_PREFIX + "/"):
                return 404, {"message": "Not found"}
            path = path[len(API_PREFIX) :]

            if method == "GET" and path == "/devices":
                return 200, {"devices": [_device_payload(d) for d in self.devices]}

            match = re.fullmatch(r"/devices/([^/]+)/actions/fetch_config_and_inventory", path)
            if method == "POST" and match:
                return self._start_fetch(match.group(1))

            match = re.fullmatch(r"/tasks/([^/]+)", path)
            if method == "GET" and match and match.group(1) in self._tasks:
                return 200, self._tasks[match.group(1)]

            match = re.fullmatch(r"/devices/([^/]+)/(configs|inventories)", path)
            if method == "GET" and match:
                device = self._device(match.group(1))
                if device is None:
                    return 404, {"message": "Device not found"}
                return 200, _listing(match.group(2), _artifacts(device, match.group(2)), query)

            match = re.fullmatch(r"/devices/([^/]+)/(configs|inventories)/([^/]+)/actions/download", path)
            if method == "GET" and match:
                device = self._device(match.group(1))
                if device is not None:
                    for artifact in _artifacts(device, match.group(2)):
                        if artifact.uuid == match.group(3):
                            return 200, artifact.content
                return 404, {"message": "Not found"}

            return 404, {"message": "Not found"}

    def _device(self, device_uuid: str) -> Optional[FakeDevice]:
        return next((d for d in self.devices if d.uuid == device_uuid), None)

    def _start_fetch(self, device_uuid: str) -> tuple[int, Any]:
        device = self._device(device_uuid)
        if device is None:
            return 404, {"message": "Device not found"}
        if device.is_system:
            return 500, {"message": "Catalog Devices cannot be fetched"}
        device.fetch_count += 1
        self._store_artifacts(device)
        task_uuid = str(uuid.uuid4())
        self._tasks[task_uuid] = {"status": "successful", "progress": 100, "status_message": "Fetch complete"}
        return 200, {"task": task_uuid}


def _device_payload(device: FakeDevice) -> dict[str, Any]:
    return {
        "device_uuid": device.uuid,
        "device_name": device.name,
        "device_type": device.device_type,
        "is_system": device.is_system,
        "system_usage": "catalog" if device.is_system else None,
        "is_hidden": device.is_system,
        "is_reachable": True,
    }


def _artifacts(device: FakeDevice, collection: str) -> list[StoredArtifact]:
    return device.configs if collection == "configs" else device.inventories


def _listing(collection: str, artifacts: list[StoredArtifact], query: dict[str, list[str]]) -> dict[str, Any]:
    """List artifacts oldest first unless the caller asks for another order, as EasyUCS does."""
    ordered = list(artifacts)
    if query.get("order_by_attribute") == ["timestamp"]:
        ordered.sort(key=lambda a: a.timestamp, reverse=query.get("order_by_direction") == ["desc"])
    if "page_size" in query:
        ordered = ordered[: int(query["page_size"][0])]
    uuid_key = "config_uuid" if collection == "configs" else "inventory_uuid"
    return {collection: [{uuid_key: a.uuid, "timestamp": a.timestamp} for a in ordered]}


def _handler_for(fake: FakeEasyUCS) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            self._dispatch("POST")

        def _dispatch(self, method: str) -> None:
            parts = urlsplit(self.path)
            status, body = fake.handle(method, parts.path, parse_qs(parts.query))
            payload = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/octet-stream" if isinstance(body, bytes) else "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler
