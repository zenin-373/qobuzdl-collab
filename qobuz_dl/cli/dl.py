"""
cli/dl.py — The `dl` command: download albums, tracks, and artist discographies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import click
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from ..api import QobuzAPI
from ..config import get_meta_fields, load_config
from ..constants import DEFAULT_CONFIG, EXT_MAP, QUALITY_LABELS, QUALITY_MAP
from ..downloader import download_album, download_artist_discography, download_single_track, dry_run_album
from ..metadata import fetch_cover, fetch_cover_for_embed
from ..utils import (
    apply_version_to_title,
    clean_name,
    console,
    get_artists,
    get_main_artist,
    get_quality_tag,
    get_year,
    parse_targets,
    safe_format,
    strip_feat_from_album_title,
    strip_feat_from_track_title,
    truncate_name,
)
from .completions import _complete_id_prefixes


@click.command("dl")
@click.argument(
    "urls", nargs=-1, required=True,
    metavar="URL [URL …]",
    shell_complete=_complete_id_prefixes,
)
@click.option("-d", "--dir", "download_dir",
              default=None, type=click.Path(file_okay=False, dir_okay=True),
              help="Override download directory")
@click.option("-q", "--quality",
              default=None, type=click.Choice(list(QUALITY_MAP)),
              help="Audio quality")
@click.option("-F", "--folder-template",
              default=None, help="Folder naming template")
@click.option("-f", "--track-template",
              default=None, help="Track filename template  (no extension)")
@click.option("-M", "--no-metadata", "no_metadata",
              is_flag=True, help="Skip metadata embedding")
@click.option("-C", "--no-cover", "no_cover",
              is_flag=True, help="Skip saving cover.jpg")
@click.option("-S", "--no-skip", "no_skip",
              is_flag=True, help="Re-download even if file exists")
@click.option("-n", "--dry-run", "dry_run",
              is_flag=True, help="Preview what would be downloaded — no files written")
@click.option("-r", "--retries",
              default=None, type=int, help="Override retry count on network failure")
@click.option("-a", "--override-main-artist",
              default=None, help="Override the main artist (Album Artist) for this run")
@click.option("-i", "--override-artist-id", is_flag=True, help=(
    "Force a single artist_id across all downloads in this run. "
    "The ID is taken from the first artist URL / ar-id target supplied; "
    "if no artist target is given it is inferred from the first album or track processed. "
))
@click.pass_context
def dl(
    ctx: click.Context,
    urls: Tuple[str, ...],
    download_dir: Optional[str],
    quality: Optional[str],
    folder_template: Optional[str],
    track_template: Optional[str],
    no_metadata: bool,
    no_cover: bool,
    no_skip: bool,
    dry_run: bool,
    retries: Optional[int],
    override_main_artist: Optional[str],
    override_artist_id: bool,
) -> None:
    """Download albums, tracks, or entire artist discographies."""
    cfg = load_config()
    effective_cfg = dict(cfg)
    if download_dir:
        effective_cfg["download_dir"] = download_dir
    if quality:
        effective_cfg["quality"] = quality
    if folder_template:
        effective_cfg["folder_template"] = folder_template
    if track_template:
        effective_cfg["track_template"] = track_template
    if no_metadata:
        effective_cfg["embed_metadata"] = False
    if no_cover:
        effective_cfg["save_cover"] = False
    if no_skip:
        effective_cfg["skip_existing"] = False
    if retries is not None:
        effective_cfg["retries"] = retries

    quality_name = effective_cfg.get("quality", "hi-res-192")
    quality_id = QUALITY_MAP.get(quality_name, QUALITY_MAP.get("hi-res-192", "27"))
    root_dir = Path(effective_cfg.get("download_dir", DEFAULT_CONFIG["download_dir"]))
    f_tmpl = effective_cfg.get("folder_template", DEFAULT_CONFIG["folder_template"])
    t_tmpl = effective_cfg.get("track_template", DEFAULT_CONFIG["track_template"])

    api = QobuzAPI(effective_cfg)
    targets = parse_targets(urls)

    auto_override_id: bool = override_artist_id or bool(override_main_artist)
    global_artist_id: Optional[str] = None
    if auto_override_id:
        explicit_artist_ids = {id_ for kind, id_ in targets if kind == "artist"}
        if len(explicit_artist_ids) > 1:
            raise click.ClickException(
                f"Multiple different artist IDs provided ({', '.join(explicit_artist_ids)}). "
                "Aborting to prevent collision."
            )
        global_artist_id = explicit_artist_ids.pop() if explicit_artist_ids else None

    for kind, id_ in targets:
        if kind == "album":
            if dry_run:
                res_id = dry_run_album(
                    api, id_, effective_cfg, quality_id, root_dir, f_tmpl, t_tmpl,
                    override_main_artist, global_artist_id, auto_override_id,
                )
            else:
                res_id = download_album(
                    api, id_, effective_cfg, quality_id, root_dir, f_tmpl, t_tmpl,
                    override_main_artist, global_artist_id, auto_override_id,
                )
            if auto_override_id and not global_artist_id and res_id:
                global_artist_id = res_id

        elif kind == "track":
            console.print("\n[bold]Fetching track info…[/]")
            try:
                track = api.get_track(id_)
                album = track.get("album", {})
                if album.get("id"):
                    try:
                        full_album = api.get_album(str(album["id"]))
                        track["album"] = full_album
                        album = full_album
                    except Exception:
                        pass

                if effective_cfg.get("include_version", False):
                    apply_version_to_title(track)
                    apply_version_to_title(album)
                if effective_cfg.get("strip_feat_from_track_title", False):
                    strip_feat_from_track_title(track)
                if effective_cfg.get("strip_feat_from_album_title", False):
                    strip_feat_from_album_title(album)

                artist = get_artists(album) or track.get("performer", {}).get("name", "")
                main_artist = override_main_artist or get_main_artist(album) or track.get("performer", {}).get("name", "")
                actual_artist_id = str(album.get("artist", {}).get("id", ""))
                used_artist_id = (global_artist_id or actual_artist_id) if auto_override_id else actual_artist_id

                folder = truncate_name(safe_format(
                    f_tmpl,
                    artist=artist,
                    main_artist=main_artist,
                    album=album.get("title", ""),
                    year=get_year(album),
                    genre=album.get("genre", {}).get("name", ""),
                    quality=get_quality_tag(album),
                    artist_id=used_artist_id,
                    album_id=str(album.get("id", "")),
                ), effective_cfg, "folder") if True else ""
                try:
                    folder = truncate_name(safe_format(
                        f_tmpl,
                        artist=artist,
                        main_artist=main_artist,
                        album=album.get("title", ""),
                        year=get_year(album),
                        genre=album.get("genre", {}).get("name", ""),
                        quality=get_quality_tag(album),
                        artist_id=used_artist_id,
                        album_id=str(album.get("id", "")),
                    ), effective_cfg, "folder")
                except TypeError:
                    folder = safe_format(
                        f_tmpl,
                        artist=artist,
                        main_artist=main_artist,
                        album=album.get("title", ""),
                        year=get_year(album),
                        genre=album.get("genre", {}).get("name", ""),
                        quality=get_quality_tag(album),
                    )
                out_dir = root_dir / folder
                out_dir.mkdir(parents=True, exist_ok=True)

                cover_for_embed = None
                if effective_cfg.get("embed_metadata", True):
                    try:
                        cover_for_embed = fetch_cover_for_embed(
                            album, api.session,
                            effective_cfg.get("embed_cover_size", "large"),
                            effective_cfg.get("embed_cover_oversize_action", "use_large"),
                        )
                    except Exception:
                        pass
                if effective_cfg.get("save_cover", True):
                    try:
                        cover = fetch_cover(album, api.session, effective_cfg.get("cover_size", "original"))
                        if cover:
                            (out_dir / "cover.jpg").write_bytes(cover)
                    except Exception:
                        pass

                track_meta_flds = get_meta_fields(effective_cfg)
                console.print(Panel(
                    f"[bold]{artist}[/] — [italic]{track.get('title', '')}[/]",
                    title="[bold blue]Downloading Track[/]", border_style="blue",
                ))
                with Progress(
                    SpinnerColumn(), TextColumn("{task.description}"),
                    BarColumn(), DownloadColumn(), TransferSpeedColumn(),
                    TimeRemainingColumn(), console=console, transient=True,
                ) as progress:
                    ok = download_single_track(
                        api=api, track=track, out_dir=out_dir, track_tmpl=t_tmpl,
                        quality_id=quality_id, cover=cover_for_embed,
                        meta_fields=track_meta_flds,
                        skip_existing=effective_cfg.get("skip_existing", True),
                        progress=progress, cfg=effective_cfg,
                        retries=int(effective_cfg.get("retries", 3)),
                        on_final_failure=effective_cfg.get("on_final_failure", "delete_partial"),
                        force_main_album_artist=effective_cfg.get("force_main_album_artist", False),
                        override_main_artist=override_main_artist,
                    )
                if ok:
                    console.print(f"\n[bold green]✓ Done![/]  →  {out_dir}\n")
                else:
                    console.print("\n[yellow]⚠ Track download failed.[/]\n")
                if auto_override_id and not global_artist_id and actual_artist_id:
                    global_artist_id = actual_artist_id
            except Exception as exc:
                console.print(f"[red]✗ {exc}[/]")

        elif kind == "artist":
            console.print("\n[bold]Fetching artist discography (all types)…[/]")
            try:
                res_id = download_artist_discography(
                    api, id_, effective_cfg, quality_id, root_dir, f_tmpl, t_tmpl,
                    override_main_artist, global_artist_id, auto_override_id, dry_run,
                )
                if auto_override_id and not global_artist_id and res_id:
                    global_artist_id = res_id
            except Exception as exc:
                console.print(f"[red]✗ Artist download error: {exc}[/]")

    if dry_run:
        console.print("\n[bold yellow]Dry run complete — nothing was downloaded.[/]\n")
