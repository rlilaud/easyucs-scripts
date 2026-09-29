"""Extraction orchestrator. It reports results to its caller and renders nothing itself."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, Optional, Sequence, Union

from easyucs_scripts.client import Device, EasyUCSClient, EasyUCSError
from easyucs_scripts.instances import Instance

if TYPE_CHECKING:
    from easyucs_scripts.output import RunFolder


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
