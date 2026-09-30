"""EasyUCS client: the only component that speaks HTTP to an Instance."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import requests

from easyucs_scripts.durations import format_duration

API_PATH = "/api/v1"
REQUEST_TIMEOUT_SECONDS = 60
_UNFINISHED_TASK_STATUSES = ("pending", "in_progress")


class EasyUCSError(Exception):
    """An Instance could not be reached, or did not do what was asked."""


class NothingStoredError(EasyUCSError):
    """A Device has no stored Config or Inventory to download."""


@dataclass(frozen=True)
class Device:
    uuid: str
    name: str
    type: str
    is_catalog: bool


class EasyUCSClient:
    def __init__(self, root_url: str) -> None:
        # The `servers` URL in EasyUCS's published spec is wrong, so the API root is
        # always derived from the root URL the operator gives.
        self.api_url = root_url.rstrip("/") + API_PATH
        self._session = requests.Session()

    def list_devices(self) -> list[Device]:
        payload = self._get_json("/devices")
        with _expected_shape("GET /devices"):
            return [
                Device(
                    uuid=device["device_uuid"],
                    name=device["device_name"],
                    type=device["device_type"],
                    is_catalog=bool(device.get("is_system", False)),
                )
                for device in payload["devices"]
            ]

    def fetch(self, device: Device, *, force: bool, poll_interval: float, timeout: float) -> None:
        """Fetch a fresh Config and Inventory of `device`, and wait until the Instance has stored them.

        With `force`, EasyUCS carries on past failed SDK objects or Intersight license validation,
        so the Config may be incomplete. Raises EasyUCSError if both are not stored within `timeout` seconds.
        """
        deadline = time.monotonic() + timeout
        # The combined `fetch_config_and_inventory` action is refused for some device types
        # (Intersight: "Unsupported device type"), so Config and Inventory are fetched separately.
        for collection, label in (("configs", "Config"), ("inventories", "Inventory")):
            path = f"/devices/{device.uuid}/{collection}/actions/fetch"
            response = self._request("POST", path, json={"force": force})
            with _expected_shape(f"POST {path}"):
                task_uuid = _json(response)["task"]
            description = f"{label} Fetch of Device {device.name!r}"
            self._wait_for_task(task_uuid, description, poll_interval, deadline, timeout)

    def _wait_for_task(
        self, task_uuid: str, description: str, poll_interval: float, deadline: float, timeout: float
    ) -> None:
        while True:
            payload = self._get_json(f"/tasks/{task_uuid}")
            with _expected_shape(f"GET /tasks/{task_uuid}"):
                task = payload["task"]
                status = task.get("status")
            if status == "successful":
                return
            if status not in _UNFINISHED_TASK_STATUSES:
                raise EasyUCSError(f"{description} ended with status {status!r}: {task.get('status_message')}")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise EasyUCSError(
                    f"{description} did not finish within {format_duration(timeout)} (last status {status!r})"
                )
            time.sleep(min(poll_interval, remaining))

    def download_latest_config(self, device: Device) -> bytes:
        return self._download_latest(device, "configs", "Config")

    def download_latest_inventory(self, device: Device) -> bytes:
        return self._download_latest(device, "inventories", "Inventory")

    def _download_latest(self, device: Device, collection: str, label: str) -> bytes:
        path = f"/devices/{device.uuid}/{collection}"
        listing = self._get_json(
            path, params={"order_by_attribute": "timestamp", "order_by_direction": "desc", "page_size": 1}
        )
        with _expected_shape(f"GET {path}"):
            items = listing.get(collection) or []
            if not items:
                raise NothingStoredError(f"Device {device.name!r} has no stored {label}")
            latest_uuid = items[0]["uuid"]
        return self._request("GET", f"/devices/{device.uuid}/{collection}/{latest_uuid}/actions/download").content

    def _get_json(self, path: str, **kwargs: Any) -> Any:
        return _json(self._request("GET", path, **kwargs))

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = self.api_url + path
        try:
            response = self._session.request(method, url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
        except requests.RequestException as exc:
            raise EasyUCSError(f"{method} {url} failed: {exc}") from exc
        if not response.ok:
            raise EasyUCSError(f"{method} {url} failed: HTTP {response.status_code}: {_error_message(response)}")
        return response


@contextmanager
def _expected_shape(endpoint: str) -> Iterator[None]:
    """Turn a response that lacks the expected fields into an EasyUCSError."""
    try:
        yield
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise EasyUCSError(f"{endpoint} returned an unexpected response ({type(exc).__name__}: {exc})") from exc


def _error_message(response: requests.Response) -> str:
    try:
        message = response.json().get("message")
    except (ValueError, AttributeError):
        message = None
    return message if isinstance(message, str) else response.reason


def _json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise EasyUCSError(f"{response.request.method} {response.url} did not return JSON") from exc
