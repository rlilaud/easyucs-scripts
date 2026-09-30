"""Extraction orchestrator. It reports results to its caller and renders nothing itself."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, Sequence, Union

from easyucs_scripts.client import Device, EasyUCSClient, EasyUCSError, NothingStoredError
from easyucs_scripts.instances import Instance

if TYPE_CHECKING:
    from easyucs_scripts.output import RunFolder


@dataclass(frozen=True)
class DeviceFilter:
    """Selects the real Devices to extract. Empty `types` or `names` do not narrow the selection."""

    types: frozenset[str] = frozenset()
    names: frozenset[str] = frozenset()

    @property
    def narrows(self) -> bool:
        return bool(self.types or self.names)

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


@dataclass(frozen=True)
class DevicesSelected:
    """The Devices of the Instance that will be extracted, reported before any of them starts."""

    instance: Instance
    devices: tuple[Device, ...]


@dataclass(frozen=True)
class DeviceProgress:
    """A Device's Extraction reached `step`, with `percent` of it done if known."""

    instance: Instance
    device: Device
    step: str
    percent: Optional[float] = None


Event = Union[DevicesSelected, DeviceProgress, DeviceResult, InstanceFailed, NoDeviceSelected]


@dataclass(frozen=True)
class _Options:
    run: RunFolder
    device_filter: DeviceFilter
    fetch: bool
    force: bool
    poll_interval: float
    timeout: float
    workers: int
    report: Callable[[Event], None]


def extract_instances(
    instances: Sequence[Instance],
    run: RunFolder,
    *,
    device_filter: DeviceFilter,
    fetch: bool,
    force: bool,
    poll_interval: float,
    timeout: float,
    workers: int,
    on_event: Callable[[Event], None],
) -> list[Result]:
    """Fetch and save the Config and Inventory of every Device that `device_filter` selects in
    each of `instances`.

    All Instances are processed at once, each with at most `workers` Devices in flight. Without
    `fetch`, the most recent stored Config and Inventory are saved instead. `force` is passed to
    each Fetch and `timeout` bounds it, in seconds. Failures are reported as results, never raised.

    `on_event` is called from worker threads, one call at a time, as the Extraction advances.
    The results are returned in the order of `instances`, then of the Devices each Instance lists.
    """
    lock = threading.Lock()

    def report(event: Event) -> None:
        with lock:
            on_event(event)

    options = _Options(run, device_filter, fetch, force, poll_interval, timeout, workers, report)
    with ThreadPoolExecutor(max_workers=max(len(instances), 1)) as pool:
        per_instance = list(pool.map(lambda instance: _extract_instance(instance, options), instances))
    return [result for results in per_instance for result in results]


def _extract_instance(instance: Instance, options: _Options) -> list[Result]:
    client = EasyUCSClient(instance.url, verify_tls=instance.verify_tls, ca_bundle=instance.ca_bundle)
    try:
        listed = client.list_devices()
    except EasyUCSError as exc:
        failed = InstanceFailed(instance=instance, reason=str(exc))
        options.report(failed)
        return [failed]
    devices = tuple(device for device in listed if options.device_filter.selects(device))
    if not devices:
        nothing = NoDeviceSelected(instance=instance)
        options.report(nothing)
        return [nothing]
    options.report(DevicesSelected(instance=instance, devices=devices))
    folders = options.run.device_folders(instance.name, [device.name for device in devices])
    with ThreadPoolExecutor(max_workers=options.workers) as pool:
        return list(
            pool.map(
                lambda device, folder: _extract_device(client, instance, device, folder, options), devices, folders
            )
        )


def _extract_device(
    client: EasyUCSClient, instance: Instance, device: Device, folder: Path, options: _Options
) -> DeviceResult:
    def progress(step: str, percent: Optional[float] = None) -> None:
        options.report(DeviceProgress(instance=instance, device=device, step=step, percent=percent))

    try:
        if options.fetch:
            client.fetch(
                device,
                force=options.force,
                poll_interval=options.poll_interval,
                timeout=options.timeout,
                on_progress=progress,
            )
        progress("Downloading")
        config = client.download_latest_config(device)
        inventory = client.download_latest_inventory(device)
        options.run.save_device(folder, config, inventory)
    except NothingStoredError as exc:
        hint = "" if options.fetch else "; run without --no-fetch to Fetch it"
        result = DeviceResult(instance=instance, device=device, failure=f"{exc}{hint}")
    except EasyUCSError as exc:
        result = DeviceResult(instance=instance, device=device, failure=str(exc))
    except OSError as exc:
        result = DeviceResult(instance=instance, device=device, failure=f"Could not save files: {exc}")
    else:
        result = DeviceResult(instance=instance, device=device, folder=folder)
    options.report(result)
    return result


def all_succeeded(results: Sequence[Result]) -> bool:
    return all(r.succeeded for r in results)
