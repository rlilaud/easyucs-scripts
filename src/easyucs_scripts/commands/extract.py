"""`eucs extract`: save the Config and Inventory of every Device of an Instance."""

from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from easyucs_scripts.durations import parse_duration
from easyucs_scripts.extraction import (
    DeviceFilter,
    InstanceFailed,
    NoDeviceSelected,
    Result,
    all_succeeded,
    extract_instance,
)
from easyucs_scripts.instances import instance_from_url
from easyucs_scripts.output import RunFolder

console = Console(soft_wrap=True)


class DeviceType(str, Enum):
    ucsm = "ucsm"
    cimc = "cimc"
    imm_domain = "imm_domain"
    ucsc = "ucsc"
    intersight = "intersight"


def extract(
    url: Annotated[
        str,
        typer.Option(
            "--url",
            help="Root URL of the EasyUCS Instance, as typed in a browser (e.g. http://10.0.0.5:5010).",
        ),
    ],
    types: Annotated[
        Optional[list[DeviceType]],
        typer.Option(
            "--type",
            help="Only extract Devices of this type. Repeat to select several types.",
            show_default=False,
        ),
    ] = None,
    devices: Annotated[
        Optional[list[str]],
        typer.Option(
            "--device",
            help="Only extract the Device with this name. Repeat to select several Devices.",
            show_default=False,
        ),
    ] = None,
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help="Directory in which a new timestamped run folder is created (default: ./extractions).",
            show_default=False,
        ),
    ] = Path("extractions"),
    timeout: Annotated[
        str,
        typer.Option(
            "--timeout",
            help="Maximum time to wait for each Device's Fetch, e.g. 90s, 30m, 1h (default: 30m).",
            show_default=False,
        ),
    ] = "30m",
    no_fetch: Annotated[
        bool,
        typer.Option(
            "--no-fetch",
            help="Skip the Fetch and save the most recent Config and Inventory already stored in EasyUCS.",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help=(
                "Ask EasyUCS to carry on the Fetch past failed SDK objects or Intersight license"
                " validation. The saved Config may then be incomplete."
            ),
        ),
    ] = False,
    poll_interval: Annotated[float, typer.Option("--poll-interval", hidden=True)] = 2.0,
) -> None:
    """Fetch and save the Config and Inventory of every Device of an EasyUCS Instance."""
    try:
        instance = instance_from_url(url)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--url") from exc
    try:
        timeout_seconds = parse_duration(timeout)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--timeout") from exc

    device_types = sorted({t.value for t in types or ()})
    device_names = sorted(set(devices or ()))
    device_filter = DeviceFilter(types=frozenset(device_types), names=frozenset(device_names))

    run = RunFolder.create(output)
    console.print(f"Run folder: {escape(str(run.path))}")
    results: list[Result] = []
    for result in extract_instance(
        instance,
        run,
        device_filter=device_filter,
        fetch=not no_fetch,
        force=force,
        poll_interval=poll_interval,
        timeout=timeout_seconds,
    ):
        results.append(result)
        _print_result(result, filtered=bool(device_types or device_names))

    parameters = {
        "urls": [instance.url],
        "device_types": device_types,
        "device_names": device_names,
        "output": str(output),
        "no_fetch": no_fetch,
        "force": force,
        "timeout_seconds": timeout_seconds,
    }
    summary_path = run.write_summary(parameters, [instance], results)
    console.print(_summary_table(results))
    console.print(f"Summary: {escape(str(summary_path))}")
    if not all_succeeded(results):
        raise typer.Exit(code=1)


def _summary_table(results: list[Result]) -> Table:
    table = Table(title="Extraction summary")
    for column in ("Instance", "Device", "Type", "Outcome"):
        table.add_column(column, no_wrap=True)
    table.add_column("Reason")
    failed = "[red]failed[/red]"
    for result in results:
        if isinstance(result, InstanceFailed):
            table.add_row(escape(result.instance.name), "-", "-", failed, escape(result.reason))
        elif isinstance(result, NoDeviceSelected):
            table.add_row(escape(result.instance.name), "-", "-", "[yellow]no Device[/yellow]", "")
        else:
            table.add_row(
                escape(result.instance.name),
                escape(result.device.name),
                escape(result.device.type),
                "[green]succeeded[/green]" if result.succeeded else failed,
                escape(result.failure or ""),
            )
    return table


def _print_result(result: Result, *, filtered: bool) -> None:
    if isinstance(result, InstanceFailed):
        console.print(f"[red]FAILED[/red] {escape(result.instance.name)}: {escape(result.reason)}")
        return
    if isinstance(result, NoDeviceSelected):
        name = escape(result.instance.name)
        if filtered:
            console.print(f"[yellow]No Device of Instance {name} matches --type / --device[/yellow]")
        else:
            console.print(f"[yellow]Instance {name} has no Device to extract[/yellow]")
        return
    label = f"{escape(result.instance.name)} / {escape(result.device.name)} ({escape(result.device.type)})"
    if result.succeeded:
        console.print(f"[green]OK[/green] {label} saved to {escape(str(result.folder))}")
    else:
        console.print(f"[red]FAILED[/red] {label}: {escape(str(result.failure))}")
