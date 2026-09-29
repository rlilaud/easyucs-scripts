"""Extraction orchestrator. It reports results to its caller and renders nothing itself."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional, Sequence, Union

from easyucs_scripts.client import Device, EasyUCSClient, EasyUCSError
from easyucs_scripts.instances import Instance
from easyucs_scripts.output import CONFIG_FILENAME, INVENTORY_FILENAME, RunFolder


@dataclass(frozen=True)
class DeviceResult:
    instance: Instance
    device: Device
    folder: Optional[Path] = None
    failure: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.failure is None


@dataclass(frozen=True)
class InstanceFailed:
    """The Instance's Devices could not even be listed."""

    instance: Instance
    reason: str


Result = Union[DeviceResult, InstanceFailed]


def extract_instance(instance: Instance, run: RunFolder, *, poll_interval: float, timeout: float) -> Iterator[Result]:
    """Fetch and save the Config and Inventory of every real Device of `instance`, one by one.

    `timeout` bounds each Device's Fetch, in seconds. Failures are reported as results, never raised.
    """
    client = EasyUCSClient(instance.url)
    try:
        devices = client.list_devices()
    except EasyUCSError as exc:
        yield InstanceFailed(instance=instance, reason=str(exc))
        return
    for device in devices:
        if device.is_catalog:
            continue
        try:
            client.fetch(device, poll_interval=poll_interval, timeout=timeout)
            config = client.download_latest_config(device)
            inventory = client.download_latest_inventory(device)
            folder = run.save_device(instance.name, device.name, config, inventory)
        except EasyUCSError as exc:
            yield DeviceResult(instance=instance, device=device, failure=str(exc))
        except OSError as exc:
            yield DeviceResult(instance=instance, device=device, failure=f"Could not save files: {exc}")
        else:
            yield DeviceResult(instance=instance, device=device, folder=folder)


def all_succeeded(results: Sequence[Result]) -> bool:
    return all(isinstance(r, DeviceResult) and r.succeeded for r in results)


def build_summary(
    parameters: Mapping[str, Any], instances: Sequence[Instance], results: Sequence[Result], run: RunFolder
) -> dict[str, Any]:
    """The machine-readable summary of a run. `parameters` must not contain secrets."""
    instance_failures = {r.instance.name: r.reason for r in results if isinstance(r, InstanceFailed)}
    return {
        "parameters": dict(parameters),
        "succeeded": all_succeeded(results),
        "instances": [
            {
                "name": instance.name,
                "url": instance.url,
                "outcome": "failed" if instance.name in instance_failures else "succeeded",
                "reason": instance_failures.get(instance.name),
            }
            for instance in instances
        ],
        "devices": [_device_summary(r, run) for r in results if isinstance(r, DeviceResult)],
    }


def _device_summary(result: DeviceResult, run: RunFolder) -> dict[str, Any]:
    files = {}
    if result.folder is not None:
        files = {
            "config": run.relative_path(result.folder / CONFIG_FILENAME),
            "inventory": run.relative_path(result.folder / INVENTORY_FILENAME),
        }
    return {
        "instance": result.instance.name,
        "name": result.device.name,
        "type": result.device.type,
        "outcome": "succeeded" if result.succeeded else "failed",
        "reason": result.failure,
        "files": files,
    }
