"""`eucs extract`: save the Config and Inventory of the selected Devices of one or more Instances."""

from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.markup import escape
from rich.progress import BarColumn, Progress, TaskID, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from easyucs_scripts.durations import parse_duration
from easyucs_scripts.extraction import (
    DeviceFilter,
    DeviceProgress,
    DeviceResult,
    DevicesSelected,
    Event,
    InstanceFailed,
    NoDeviceSelected,
    Result,
    all_succeeded,
    extract_instances,
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
    workers: Annotated[
        int,
        typer.Option(
            "--workers",
            min=1,
            help="Maximum number of Devices extracted at the same time in each Instance (default: 4).",
            show_default=False,
        ),
    ] = 4,
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

    run = RunFolder.create(output, [instance.name for instance in instances])
    console.print(f"Run folder: {escape(str(run.path))}")
    with _progress_bars() as progress:
        results = extract_instances(
            instances,
            run,
            device_filter=device_filter,
            fetch=not no_fetch,
            force=force,
            poll_interval=poll_interval,
            timeout=timeout_seconds,
            workers=workers,
            on_event=_ProgressDisplay(progress, device_filter),
        )

    parameters = {
        "instances_file": None if instances_file is None else str(instances_file),
        "urls": list(urls or []),
        "device_types": sorted(device_filter.types),
        "device_names": sorted(device_filter.names),
        "output": str(output),
        "no_fetch": no_fetch,
        "force": force,
        "timeout_seconds": timeout_seconds,
        "workers": workers,
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


def _progress_bars() -> Progress:
    return Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TextColumn("{task.fields[status]}"),
        console=console,
    )


class _ProgressDisplay:
    """Renders the Extraction's events as one progress bar per Device."""

    def __init__(self, progress: Progress, device_filter: DeviceFilter) -> None:
        self._progress = progress
        self._device_filter = device_filter
        self._bars: dict[tuple[str, str], TaskID] = {}

    def __call__(self, event: Event) -> None:
        if isinstance(event, DevicesSelected):
            for device in event.devices:
                label = f"{escape(event.instance.name)} / {escape(device.name)} ({escape(device.type)})"
                self._bars[event.instance.name, device.uuid] = self._progress.add_task(
                    label, total=100, status="waiting"
                )
        elif isinstance(event, DeviceProgress):
            bar = self._bars[event.instance.name, event.device.uuid]
            self._progress.update(bar, completed=event.percent, status=escape(event.step))
        elif isinstance(event, DeviceResult):
            bar = self._bars[event.instance.name, event.device.uuid]
            if event.succeeded:
                self._progress.update(bar, completed=100, status="[green]succeeded[/green]")
            else:
                self._progress.update(bar, status="[red]failed[/red]")
            self._progress.stop_task(bar)
        elif isinstance(event, InstanceFailed):
            console.print(f"[red]FAILED[/red] {escape(event.instance.name)}: {escape(event.reason)}")
        else:
            name = escape(event.instance.name)
            if self._device_filter.narrows:
                console.print(f"[yellow]No Device of Instance {name} matches --type / --device[/yellow]")
            else:
                console.print(f"[yellow]Instance {name} has no Device to extract[/yellow]")
