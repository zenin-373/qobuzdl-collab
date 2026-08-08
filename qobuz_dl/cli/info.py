"""
cli/info.py — The `info` command: show album or track details without downloading.
"""

from __future__ import annotations

from typing import Tuple

import click
from rich.panel import Panel
from rich.table import Table

from ..api import QobuzAPI
from ..config import load_config
from ..utils import console, get_artists, get_quality_tag, get_year, parse_targets
from .completions import _complete_id_prefixes


@click.command()
@click.argument(
    "target", nargs=-1, required=True,
    metavar="URL | PREFIX ID",
    shell_complete=_complete_id_prefixes,
)
def info(target: Tuple[str, ...]) -> None:
    """Show detailed info about an album or track without downloading.

    \b
    Accepts a Qobuz URL or a prefixed ID (al-id, tr-id):

      qobuzdl-collab info https://play.qobuz.com/album/0060253780948
      qobuzdl-collab info https://play.qobuz.com/track/23929921
      qobuzdl-collab info al-id 0060253780948
      qobuzdl-collab info tr-id 23929921
    """
    cfg  = load_config()
    api  = QobuzAPI(cfg)

    targets = parse_targets(target)
    if len(targets) != 1:
        raise click.ClickException("info accepts exactly one album or track target.")
    kind, id_ = targets[0]
    if kind == "artist":
        raise click.ClickException(
            "info does not support artist targets. Use an album or track URL/ID."
        )

    with console.status("Fetching info…"):
        try:
            if kind == "album":
                data = api.get_album(id_)
            elif kind == "track":
                data = api.get_track(id_)
            else:
                raise click.ClickException("Use an album or track URL with `info`.")
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc

    if kind == "album":
        tracks = data.get("tracks", {}).get("items", [])
        console.print(
            Panel(
                f"[bold]{get_artists(data)}[/] — [italic]{data.get('title', '')}[/]\n\n"
                f"Year     : {get_year(data)}\n"
                f"Genre    : {data.get('genre', {}).get('name', '')}\n"
                f"Label    : {data.get('label', {}).get('name', '')}\n"
                f"Tracks   : {len(tracks)}\n"
                f"Quality  : {get_quality_tag(data)}\n"
                f"UPC      : {data.get('upc', '')}\n"
                f"Streamable: {data.get('streamable', '?')}",
                title="Album Info",
                border_style="blue",
            )
        )
        t = Table(border_style="dim", show_lines=False)
        t.add_column("#",        justify="right", style="dim", no_wrap=True)
        t.add_column("D",        justify="center", style="dim")
        t.add_column("Title")
        t.add_column("Duration", justify="right", style="dim")
        t.add_column("Hi-Res",   justify="center")
        for tr in tracks:
            mins = tr.get("duration", 0) // 60
            secs = tr.get("duration", 0) % 60
            t.add_row(
                str(tr.get("track_number", "")),
                str(tr.get("media_number", 1)),
                tr.get("title", ""),
                f"{mins}:{secs:02d}",
                "✓" if tr.get("hires") else "",
            )
        console.print(t)
    else:
        album = data.get("album", {})
        mins  = data.get("duration", 0) // 60
        secs  = data.get("duration", 0) % 60
        console.print(
            Panel(
                f"[bold]{data.get('performer', {}).get('name', '')}[/] — "
                f"[italic]{data.get('title', '')}[/]\n\n"
                f"Album    : {album.get('title', '')}\n"
                f"Track #  : {data.get('track_number', '')}\n"
                f"Duration : {mins}:{secs:02d}\n"
                f"Hi-Res   : {data.get('hires', False)}\n"
                f"ISRC     : {data.get('isrc', '')}\n"
                f"Streamable: {data.get('streamable', '?')}",
                title="Track Info",
                border_style="magenta",
            )
        )
