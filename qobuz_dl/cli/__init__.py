"""
cli/__init__.py — Top-level Click group and --verbose flag.
Imports all sub-commands so Click registers them onto the group.
"""

from __future__ import annotations

import click

from .. import utils as _utils_module
from ..utils import console


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option("0.1.0", prog_name="qobuzdl-collab")
@click.option(
    "-v", "--verbose",
    is_flag=True,
    default=False,
    help="Enable verbose/debug output (API calls, file paths, metadata decisions).",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Download music from Qobuz via the official API.

    \b
    Quick start
    ───────────
      1.  qobuzdl-collab setup                          Configure credentials & preferences
      2.  qobuzdl-collab search "Death in June"         Find albums, tracks, artists
      3.  qobuzdl-collab dl al-id <id>                  Download by ID
          qobuzdl-collab dl https://play.qobuz.com/…   Download by URL

    \b
    Debug output
    ────────────
      qobuzdl-collab --verbose dl https://play.qobuz.com/album/…
      qobuzdl-collab -v search "Merzbow"
    """
    _utils_module._VERBOSE = verbose
    if verbose:
        console.print("[dim][DEBUG] Verbose mode enabled[/dim]")


# Register sub-commands
from .setup import setup                  # noqa: E402
from .config_cmd import config_cmd        # noqa: E402
from .search import search                # noqa: E402
from .dl import dl                        # noqa: E402
from .info import info                    # noqa: E402
from .completions import completions_cmd  # noqa: E402

cli.add_command(setup)
cli.add_command(config_cmd, name="config")
cli.add_command(search)
cli.add_command(dl)
cli.add_command(info)
cli.add_command(completions_cmd, name="completions")
