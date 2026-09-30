"""Extraction orchestrator. It reports results to its caller and renders nothing itself."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, Optional, Sequence, Union

from easyucs_scripts.client import Device, EasyUCSClient, EasyUCSError, NothingStoredError
from easyucs_scripts.instances import Instance

if TYPE_CHECKING:
    from easyucs_scripts.output import RunFolder


@dataclass(frozen=True)
class DeviceFilter:
    """Selects the real Devices to extract. Empty `types` or `names` do not narrow the selection."""

    types: frozenset[str] = frozenset()
    names: frozenset[str] = frozenset()

    def selects(self, device: Device) -> bool:
        return (
            not device.is_catalog
            and (not self.types or device.type in self.types)
            and (not self.names or device.name in self.names)
        )


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

    @property
    def succeeded(self) -> bool:
        return False


@dataclass(frozen=True)
class NoDeviceSelected:
    """The Instance has no Device that the filter selects. This is not a failure."""

    instance: Instance

    @property
    def succeeded(self) -> bool:
        return True


Result = Union[DeviceResult, InstanceFailed, NoDeviceSelected]


def extract_instance(
    instance: Instance,
    run: RunFolder,
    *,
    device_filter: DeviceFilter,
    fetch: bool,
    force: bool,
    poll_interval: float,
    timeout: float,
) -> Iterator[Result]:
    """Fetch and save the Config and Inventory of every Device of `instance` that `device_filter` selects, one by one.

    Without `fetch`, the most recent stored Config and Inventory are saved instead. `force` is
    passed to each Fetch and `timeout` bounds it, in seconds. Failures are reported as results,
    never raised.
    """
    client = EasyUCSClient(instance.url)
    try:
        devices = [device for device in client.list_devices() if device_filter.selects(device)]
    except EasyUCSError as exc:
        yield InstanceFailed(instance=instance, reason=str(exc))
        return
    if not devices:
        yield NoDeviceSelected(instance=instance)
    for device in devices:
        try:
            if fetch:
                client.fetch(device, force=force, poll_interval=poll_interval, timeout=timeout)
            config = client.download_latest_config(device)
            inventory = client.download_latest_inventory(device)
            folder = run.save_device(instance.name, device.name, config, inventory)
        except NothingStoredError as exc:
            hint = "" if fetch else "; run without --no-fetch to Fetch it"
            yield DeviceResult(instance=instance, device=device, failure=f"{exc}{hint}")
        except EasyUCSError as exc:
            yield DeviceResult(instance=instance, device=device, failure=str(exc))
        except OSError as exc:
            yield DeviceResult(instance=instance, device=device, failure=f"Could not save files: {exc}")
        else:
            yield DeviceResult(instance=instance, device=device, folder=folder)


def all_succeeded(results: Sequence[Result]) -> bool:
    return all(r.succeeded for r in results)
