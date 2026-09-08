"""Album / track / artist download logic for qobuz-dl."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
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

from .constants import EXT_MAP, QUALITY_LABELS, QUALITY_MAP, QUALITY_ORDER
from .metadata import embed_flac_metadata, embed_mp3_metadata, fetch_cover, fetch_cover_for_embed
from .utils import (
    apply_version_to_title,
    console,
    get_artists,
    get_main_artist,
    get_quality_tag,
    get_year,
    safe_format,
    strip_feat_from_album_title,
    strip_feat_from_track_title,
    truncate_name,
)


def _quality_chain(cfg: Dict[str, Any], start_qid: str) -> List[str]:
    if not cfg.get("quality_fallback", True):
        return [start_qid]
    path = cfg.get("quality_fallback_path") or QUALITY_ORDER
    ids: List[str] = []
    for name in path:
        qid = QUALITY_MAP.get(name, name)
        if qid not in ids:
            ids.append(qid)
    if start_qid not in ids:
        ids.insert(0, start_qid)
    if start_qid in ids:
        ids = ids[ids.index(start_qid) :]
    return ids or [start_qid]


def _download_file(session, url, dest, progress, retries) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    last_err = None
    for attempt in range(max(1, retries + 1)):
        try:
            with session.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length") or 0)
                task = None
                if progress is not None:
                    task = progress.add_task(dest.name, total=total or None)
                written = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=256 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        written += len(chunk)
                        if progress is not None and task is not None:
                            progress.update(task, completed=written)
                if total and written < total * 0.95:
                    raise IOError(f"incomplete download {written}/{total}")
            tmp.replace(dest)
            return True
        except Exception as e:
            last_err = e
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            time.sleep(min(2 ** attempt, 8))
    if last_err:
        console.print(f"  [red]✗ download failed: {last_err}[/]")
    return False


def _embed(path, track, cover, meta_fields, force_main_album_artist, override_main_artist):
    if meta_fields is None:
        return
    if path.suffix.lower() == ".mp3":
        embed_mp3_metadata(path, track, cover, meta_fields, force_main_album_artist, override_main_artist)
    else:
        embed_flac_metadata(path, track, cover, meta_fields, force_main_album_artist, override_main_artist)


def download_single_track(
    api, track, out_dir, track_tmpl, quality_id, cover, meta_fields, skip_existing,
    progress, cfg, retries=3, on_final_failure="delete_partial",
    force_main_album_artist=False, override_main_artist=None,
) -> bool:
    album = track.get("album") or {}
    title = track.get("title") or f"track-{track.get('id')}"
    track_no = track.get("track_number") or ""
    disc_no = track.get("media_number") or 1
    artist = get_artists(album) or track.get("performer", {}).get("name", "")
    main_artist = override_main_artist or get_main_artist(album) or artist
    fname = safe_format(
        track_tmpl, title=title, track_number=track_no, disc_number=disc_no,
        artist=artist, main_artist=main_artist, album=album.get("title", ""),
        year=get_year(album), quality=get_quality_tag(album),
    )
    try:
        fname = truncate_name(fname, cfg, "track")
    except TypeError:
        pass
    chain = _quality_chain(cfg, str(quality_id))
    last_path = None
    for qid in chain:
        ext = EXT_MAP.get(str(qid), "flac")
        dest = out_dir / f"{fname}.{ext}"
        last_path = dest
        if skip_existing and dest.exists() and dest.stat().st_size > 1024:
            console.print(f"  [dim]skip existing[/] {dest.name}")
            return True
        try:
            url = api.get_track_url(int(track["id"]), str(qid))
        except Exception as e:
            console.print(f"  [yellow]URL fetch failed for '{title}': {e}[/]")
            ok_url = False
            for tok in getattr(api, "all_tokens", lambda: [])() or []:
                try:
                    url = api.get_track_url_with_token(int(track["id"]), str(qid), tok)
                    ok_url = True
                    break
                except Exception:
                    continue
            if not ok_url:
                continue
        console.print(f"  ↓ {dest.name}  ({QUALITY_LABELS.get(str(qid), qid)})")
        if _download_file(api.session, url, dest, progress, retries):
            if cfg.get("embed_metadata", True):
                _embed(dest, track, cover, meta_fields, force_main_album_artist, override_main_artist)
            console.print(f"  [green]✓[/] {dest.name}")
            return True
        if on_final_failure == "delete_partial" and dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass
    if on_final_failure == "delete_partial" and last_path and last_path.exists():
        try:
            last_path.unlink()
        except OSError:
            pass
    return False


def download_album(
    api, album_id, cfg, quality_id, root_dir, folder_tmpl, track_tmpl,
    override_main_artist=None, global_artist_id=None, auto_override_id=False,
) -> Optional[str]:
    try:
        album = api.get_album(str(album_id))
    except Exception as e:
        console.print(f"[red]✗ Could not fetch album {album_id}: {e}[/]")
        return None
    if cfg.get("include_version", False):
        apply_version_to_title(album)
    if cfg.get("strip_feat_from_album_title", False):
        strip_feat_from_album_title(album)
    artist = get_artists(album)
    main_artist = override_main_artist or get_main_artist(album) or artist
    year = get_year(album)
    quality_tag = get_quality_tag(album)
    genre = (album.get("genre") or {}).get("name", "")
    folder_name = safe_format(
        folder_tmpl, artist=artist, main_artist=main_artist,
        album=album.get("title", ""), year=year, genre=genre, quality=quality_tag,
    )
    try:
        folder_name = truncate_name(folder_name, cfg, "folder")
    except TypeError:
        pass
    out_dir = Path(root_dir) / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)
    tracks = album.get("tracks", {}).get("items") or album.get("tracks") or []
    if isinstance(tracks, dict):
        tracks = tracks.get("items") or []
    console.print(Panel(
        f"[bold]{main_artist}[/] — [italic]{album.get('title', '')}[/]  ({year})\n"
        f"{genre}  ·  {len(tracks)} track(s)  ·  {QUALITY_LABELS.get(str(quality_id), quality_id)}",
        title="[bold blue]Downloading Album[/]", border_style="blue",
    ))
    cover_bytes = None
    cover_for_embed = None
    if cfg.get("save_cover", True) or cfg.get("embed_metadata", True):
        try:
            if cfg.get("save_cover", True):
                cover_bytes = fetch_cover(album, api.session, cfg.get("cover_size", "original"))
                if cover_bytes:
                    (out_dir / "cover.jpg").write_bytes(cover_bytes)
                    console.print("  [green]✓[/] cover.jpg")
            cover_for_embed = fetch_cover_for_embed(
                album, api.session, cfg.get("embed_cover_size", "large"),
                cfg.get("embed_cover_oversize_action", "use_large"),
            )
        except Exception as e:
            console.print(f"  [yellow]cover error: {e}[/]")
    from .config import get_meta_fields
    meta_fields = get_meta_fields(cfg)
    ok_count = 0
    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), BarColumn(),
        DownloadColumn(), TransferSpeedColumn(), TimeRemainingColumn(),
        console=console, transient=True,
    ) as progress:
        for tr in tracks:
            tr = dict(tr)
            tr["album"] = album
            if cfg.get("include_version", False):
                apply_version_to_title(tr)
            if cfg.get("strip_feat_from_track_title", False):
                strip_feat_from_track_title(tr)
            if download_single_track(
                api=api, track=tr, out_dir=out_dir, track_tmpl=track_tmpl,
                quality_id=quality_id, cover=cover_for_embed or cover_bytes,
                meta_fields=meta_fields, skip_existing=cfg.get("skip_existing", True),
                progress=progress, cfg=cfg, retries=int(cfg.get("retries", 3)),
                on_final_failure=cfg.get("on_final_failure", "delete_partial"),
                force_main_album_artist=cfg.get("force_main_album_artist", False),
                override_main_artist=override_main_artist,
            ):
                ok_count += 1
    console.print(f"\n[bold green]✓ Done![/]  {ok_count}/{len(tracks)} →  {out_dir}\n")
    aid = str((album.get("artist") or {}).get("id") or "")
    return aid or None


def dry_run_album(
    api, album_id, cfg, quality_id, root_dir, folder_tmpl, track_tmpl,
    override_main_artist=None, global_artist_id=None, auto_override_id=False,
) -> Optional[str]:
    try:
        album = api.get_album(str(album_id))
    except Exception as e:
        console.print(f"[red]✗ Could not fetch album {album_id}: {e}[/]")
        return None
    artist = get_artists(album)
    main_artist = override_main_artist or get_main_artist(album) or artist
    year = get_year(album)
    tracks = album.get("tracks", {}).get("items") or []
    if isinstance(tracks, dict):
        tracks = tracks.get("items") or []
    folder_name = safe_format(
        folder_tmpl, artist=artist, main_artist=main_artist,
        album=album.get("title", ""), year=year,
        genre=(album.get("genre") or {}).get("name", ""), quality=get_quality_tag(album),
    )
    console.print(
        f"[yellow]DRY[/] {main_artist} — {album.get('title')} ({year}) "
        f"· {len(tracks)} tracks · would write under {root_dir / folder_name}"
    )
    return str((album.get("artist") or {}).get("id") or "") or None


def download_artist_discography(
    api, artist_id: str, cfg: Dict[str, Any], quality_id: str, root_dir: Path,
    folder_tmpl: str, track_tmpl: str, override_main_artist: Optional[str] = None,
    global_artist_id: Optional[str] = None, auto_override_id: bool = False,
    dry_run: bool = False,
) -> Optional[str]:
    """Download every release type for an artist (all pages, deduped)."""
    release_types = (
        "album", "epSingle", "single", "live", "compilation",
        "various-artist", "download",
    )
    seen: set = set()
    album_ids: list = []

    def _add(aid):
        if aid is None:
            return
        s = str(aid)
        if s and s not in seen:
            seen.add(s)
            album_ids.append(s)

    for release_type in release_types:
        offset = 0
        page_size = 100
        while True:
            try:
                page = api.get_artist_releases(
                    artist_id, release_type=release_type, limit=page_size, offset=offset,
                )
            except Exception as e:
                console.print(f"[dim]{release_type}@{offset}: {e}[/]")
                break
            if not isinstance(page, dict):
                break
            items = page.get("items") or []
            if not items:
                break
            for stub in items:
                if isinstance(stub, dict):
                    _add(stub.get("id") or stub.get("qobuz_id"))
            console.print(
                f"[bold]{release_type}[/] offset={offset} page={len(items)} "
                f"unique_total={len(album_ids)}"
            )
            has_more = bool(page.get("has_more"))
            if has_more or len(items) >= page_size:
                offset += page_size
                if offset > 5000:
                    break
                continue
            break

    try:
        for aid in api.get_artist_album_ids(artist_id):
            _add(aid)
    except Exception as e:
        console.print(f"[dim]artist album ids merge: {e}[/]")

    console.print(f"\n[bold green]Total unique releases: {len(album_ids)}[/]\n")
    last_artist = None
    for aid in album_ids:
        if dry_run:
            res = dry_run_album(
                api, aid, cfg, quality_id, root_dir, folder_tmpl, track_tmpl,
                override_main_artist, global_artist_id, auto_override_id,
            )
        else:
            res = download_album(
                api, aid, cfg, quality_id, root_dir, folder_tmpl, track_tmpl,
                override_main_artist, global_artist_id, auto_override_id,
            )
        if res:
            last_artist = res
    return last_artist
