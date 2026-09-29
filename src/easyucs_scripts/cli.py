"""Root `eucs` command. Each feature is a subcommand registered here explicitly."""

from typing import Annotated, Optional

import typer

from easyucs_scripts import __version__
from easyucs_scripts.commands import extract

app = typer.Typer(
    help="Command-line tools for EasyUCS Instances.",
    no_args_is_help=True,
    add_completion=False,
)
app.command("extract")(extract.extract)


def _print_version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            callback=_print_version,
            is_eager=True,
            help="Print the eucs version and exit.",
        ),
    ] = None,
) -> None:
    """Command-line tools for EasyUCS Instances."""
