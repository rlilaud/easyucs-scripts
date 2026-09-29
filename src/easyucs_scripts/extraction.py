"""Extraction orchestrator. It reports results to its caller and renders nothing itself."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from easyucs_scripts.client import Device, EasyUCSClient
from easyucs_scripts.instances import Instance
from easyucs_scripts.output import RunFolder


@dataclass(frozen=True)
class DeviceExtracted:
    device: Device
    folder: Path


def extract_instance(instance: Instance, run: RunFolder) -> Iterator[DeviceExtracted]:
    """Fetch and save the Config and Inventory of every real Device of `instance`, one by one."""
    client = EasyUCSClient(instance.url)
    for device in client.list_devices():
        if device.is_catalog:
            continue
        client.fetch(device)
        config = client.download_latest_config(device)
        inventory = client.download_latest_inventory(device)
        folder = run.save_device(instance.name, device.name, config, inventory)
        yield DeviceExtracted(device=device, folder=folder)
