"""`eucs extract`: save the Config and Inventory of every Device of an Instance."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape

from easyucs_scripts.client import EasyUCSError
from easyucs_scripts.extraction import extract_instance
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
) -> None:
    """Fetch and save the Config and Inventory of every Device of an EasyUCS Instance."""
    try:
        instance = instance_from_url(url)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--url") from exc

    run = RunFolder.create(output)
    console.print(f"Run folder: {escape(str(run.path))}")
    try:
        for result in extract_instance(instance, run):
            console.print(
                f"[green]OK[/green] {escape(instance.name)} / {escape(result.device.name)}"
                f" ({escape(result.device.type)}) saved to {escape(str(result.folder))}"
            )
    except EasyUCSError as exc:
        console.print(f"[red]Error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=1) from exc
