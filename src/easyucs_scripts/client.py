"""EasyUCS client: the only component that speaks HTTP to an Instance."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

API_PATH = "/api/v1"
REQUEST_TIMEOUT_SECONDS = 60


class EasyUCSError(Exception):
    """An Instance could not be reached, or did not do what was asked."""


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
        return [
            Device(
                uuid=device["device_uuid"],
                name=device["device_name"],
                type=device["device_type"],
                is_catalog=bool(device.get("is_system", False)),
            )
            for device in payload["devices"]
        ]

    def fetch(self, device: Device, *, poll_interval: float = 2.0) -> None:
        """Fetch a fresh Config and Inventory of `device`, and wait until the Instance has stored them."""
        response = self._request(
            "POST",
            f"/devices/{device.uuid}/actions/fetch_config_and_inventory",
            json={"force": False},
        )
        task_uuid = _json(response)["task"]
        while True:
            task = self._get_json(f"/tasks/{task_uuid}")
            status = task.get("status")
            if status == "successful":
                return
            if status != "in_progress":
                raise EasyUCSError(
                    f"Fetch of Device {device.name!r} ended with status {status!r}: {task.get('status_message')}"
                )
            time.sleep(poll_interval)

    def download_latest_config(self, device: Device) -> bytes:
        return self._download_latest(device, "configs", "config_uuid", "Config")

    def download_latest_inventory(self, device: Device) -> bytes:
        return self._download_latest(device, "inventories", "inventory_uuid", "Inventory")

    def _download_latest(self, device: Device, collection: str, uuid_key: str, label: str) -> bytes:
        listing = self._get_json(
            f"/devices/{device.uuid}/{collection}",
            params={"order_by_attribute": "timestamp", "order_by_direction": "desc", "page_size": 1},
        )
        items = listing.get(collection) or []
        if not items:
            raise EasyUCSError(f"Device {device.name!r} has no stored {label}")
        latest_uuid = items[0][uuid_key]
        return self._request("GET", f"/devices/{device.uuid}/{collection}/{latest_uuid}/actions/download").content

    def _get_json(self, path: str, **kwargs: Any) -> Any:
        return _json(self._request("GET", path, **kwargs))

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = self.api_url + path
        try:
            response = self._session.request(method, url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise EasyUCSError(f"{method} {url} failed: {exc}") from exc
        return response


def _json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise EasyUCSError(f"{response.request.method} {response.url} did not return JSON") from exc
