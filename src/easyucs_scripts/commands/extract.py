"""`eucs extract`: save the Config and Inventory of every Device of an Instance."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from easyucs_scripts.durations import parse_duration
from easyucs_scripts.extraction import InstanceFailed, Result, all_succeeded, build_summary, extract_instance
from easyucs_scripts.instances import instance_from_url
from easyucs_scripts.output import RunFolder

console = Console(soft_wrap=True)


def extract(
    url: Annotated[
        str,
        typer.Option(
            "--url",
            help="Root URL of the EasyUCS Instance, as typed in a browser (e.g. http://10.0.0.5:5010).",
        ),
    ],
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

    run = RunFolder.create(output)
    console.print(f"Run folder: {escape(str(run.path))}")
    results: list[Result] = []
    for result in extract_instance(instance, run, poll_interval=poll_interval, timeout=timeout_seconds):
        results.append(result)
        _print_result(result)

    parameters = {"urls": [instance.url], "output": str(output), "timeout_seconds": timeout_seconds}
    summary_path = run.write_summary(build_summary(parameters, [instance], results, run))
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
        else:
            table.add_row(
                escape(result.instance.name),
                escape(result.device.name),
                escape(result.device.type),
                "[green]succeeded[/green]" if result.succeeded else failed,
                escape(result.failure or ""),
            )
    return table


def _print_result(result: Result) -> None:
    if isinstance(result, InstanceFailed):
        console.print(f"[red]FAILED[/red] {escape(result.instance.name)}: {escape(result.reason)}")
        return
    label = f"{escape(result.instance.name)} / {escape(result.device.name)} ({escape(result.device.type)})"
    if result.succeeded:
        console.print(f"[green]OK[/green] {label} saved to {escape(str(result.folder))}")
    else:
        console.print(f"[red]FAILED[/red] {label}: {escape(str(result.failure))}")
