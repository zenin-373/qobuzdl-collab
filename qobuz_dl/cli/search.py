"""
cli/search.py — The `search` command: search Qobuz for albums, tracks, artists.
"""

from __future__ import annotations

import click
from rich.table import Table

from ..api import QobuzAPI
from ..config import load_config
from ..utils import console, get_artists, get_year


@click.command()
@click.argument("query")
@click.option("-n", "--limit", default=10, show_default=True, help="Results per category")
@click.option(
    "-t", "--type", "search_type",
    type=click.Choice(["all", "albums", "tracks", "artists"]),
    default="all", show_default=True,
    help="Filter result type",
)
def search(query: str, limit: int, search_type: str) -> None:
    """Search Qobuz for albums, tracks, or artists.

    \b
    Examples:
      qobuzdl-collab search "Steve Roden"
      qobuzdl-collab search "Salmon Run" -t albums -n 5
      qobuzdl-collab search "djinns não são bons para trabalhos de amor" -t tracks
    """
    cfg = load_config()
    api = QobuzAPI(cfg)

    with console.status("Searching…"):
        try:
            results = api.search(query, limit=limit)
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc

    shown = 0

    if search_type in ("all", "albums"):
        items = results.get("albums", {}).get("items", [])
        if items:
            shown += 1
            t = Table(title="Albums", border_style="blue", show_lines=True)
            t.add_column("#",       justify="right", style="dim", no_wrap=True)
            t.add_column("Artist",  style="cyan", max_width=28)
            t.add_column("Title",   max_width=35)
            t.add_column("Year",    justify="center", no_wrap=True)
            t.add_column("Quality", justify="center", no_wrap=True)
            t.add_column("Tracks",  justify="center", no_wrap=True)
            t.add_column("URL",     style="dim", overflow="fold")
            for i, a in enumerate(items, 1):
                bits = a.get("maximum_bit_depth", 0)
                rate = a.get("maximum_sampling_rate", 0)
                q    = f"{bits}b/{int(rate)}k" if bits and rate else "—"
                url  = f"https://play.qobuz.com/album/{a['id']}"
                t.add_row(
                    str(i),
                    get_artists(a),
                    a.get("title", ""),
                    get_year(a),
                    q,
                    str(a.get("tracks_count", "?")),
                    url,
                )
            console.print(t)

    if search_type in ("all", "tracks"):
        items = results.get("tracks", {}).get("items", [])
        if items:
            shown += 1
            t = Table(title="Tracks", border_style="magenta", show_lines=True)
            t.add_column("#",      justify="right", style="dim", no_wrap=True)
            t.add_column("Artist", style="cyan", max_width=28)
            t.add_column("Title",  max_width=35)
            t.add_column("Album",  max_width=28)
            t.add_column("URL",    style="dim", overflow="fold")
            for i, tr in enumerate(items, 1):
                url = f"https://play.qobuz.com/track/{tr['id']}"
                t.add_row(
                    str(i),
                    tr.get("performer", {}).get("name", ""),
                    tr.get("title", ""),
                    tr.get("album", {}).get("title", ""),
                    url,
                )
            console.print(t)

    if search_type in ("all", "artists"):
        items = results.get("artists", {}).get("items", [])
        if items:
            shown += 1
            t = Table(title="Artists", border_style="green", show_lines=True)
            t.add_column("#",      justify="right", style="dim", no_wrap=True)
            t.add_column("Name",   style="cyan")
            t.add_column("Albums", justify="center", no_wrap=True)
            t.add_column("URL",    style="dim", overflow="fold")
            for i, a in enumerate(items, 1):
                url = f"https://play.qobuz.com/artist/{a['id']}"
                t.add_row(str(i), a.get("name", ""), str(a.get("albums_count", "?")), url)
            console.print(t)

    if not shown:
        console.print("[yellow]No results found.[/]")
