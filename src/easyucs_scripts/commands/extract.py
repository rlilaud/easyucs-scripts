"""`eucs extract`: save the Config and Inventory of the selected Devices of one or more Instances."""

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
from easyucs_scripts.instances import InstanceDefinitionError, resolve_instances
from easyucs_scripts.output import RunFolder

console = Console(soft_wrap=True)


class DeviceType(str, Enum):
    ucsm = "ucsm"
    cimc = "cimc"
    imm_domain = "imm_domain"
    ucsc = "ucsc"
    intersight = "intersight"


def extract(
    instances_file: Annotated[
        Optional[Path],
        typer.Option(
            "--instances",
            help="YAML or JSON Instances file listing the EasyUCS Instances to extract.",
            show_default=False,
        ),
    ] = None,
    urls: Annotated[
        Optional[list[str]],
        typer.Option(
            "--url",
            help=(
                "Root URL of an EasyUCS Instance, as typed in a browser (e.g. http://10.0.0.5:5010)."
                " Repeat to extract several Instances; combines with --instances."
            ),
            show_default=False,
        ),
    ] = None,
    types: Annotated[
        Optional[list[DeviceType]],
        typer.Option(
            "--type",
            help="Only extract Devices of this type. Repeat to select several types.",
            show_default=False,
        ),
    ] = None,
    names: Annotated[
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
    """Fetch and save the Config and Inventory of every Device of the given EasyUCS Instances,
    or only of those selected with --type and --device."""
    if instances_file is None and not urls:
        raise typer.BadParameter("give at least one Instance to extract", param_hint="'--instances' / '--url'")
    try:
        instances = resolve_instances(instances_file, urls or [])
    except InstanceDefinitionError as exc:
        raise typer.BadParameter(str(exc)) from exc
    try:
        timeout_seconds = parse_duration(timeout)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--timeout") from exc

    device_filter = DeviceFilter(types=frozenset(t.value for t in types or ()), names=frozenset(names or ()))

    run = RunFolder.create(output)
    console.print(f"Run folder: {escape(str(run.path))}")
    results: list[Result] = []
    for instance in instances:
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
            _print_result(result, device_filter)

    parameters = {
        "instances_file": None if instances_file is None else str(instances_file),
        "urls": list(urls or []),
        "device_types": sorted(device_filter.types),
        "device_names": sorted(device_filter.names),
        "output": str(output),
        "no_fetch": no_fetch,
        "force": force,
        "timeout_seconds": timeout_seconds,
    }
    summary_path = run.write_summary(parameters, instances, results)
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


def _print_result(result: Result, device_filter: DeviceFilter) -> None:
    if isinstance(result, InstanceFailed):
        console.print(f"[red]FAILED[/red] {escape(result.instance.name)}: {escape(result.reason)}")
        return
    if isinstance(result, NoDeviceSelected):
        name = escape(result.instance.name)
        if device_filter.narrows:
            console.print(f"[yellow]No Device of Instance {name} matches --type / --device[/yellow]")
        else:
            console.print(f"[yellow]Instance {name} has no Device to extract[/yellow]")
        return
    label = f"{escape(result.instance.name)} / {escape(result.device.name)} ({escape(result.device.type)})"
    if result.succeeded:
        console.print(f"[green]OK[/green] {label} saved to {escape(str(result.folder))}")
    else:
        console.print(f"[red]FAILED[/red] {label}: {escape(str(result.failure))}")
