"""
cli/setup.py — Interactive first-time setup wizard.
"""

from __future__ import annotations

import click
from rich.panel import Panel

from ..config import load_config, save_config
from ..constants import (
    CONFIG_FILE,
    METADATA_FIELDS,
    PREVIEW_DURATION,
    PREVIEW_DURATION_TOLERANCE,
    QUALITY_MAP,
    QUALITY_LABELS,
    QUALITY_ORDER,
    TEMPLATE_HELP,
)
from ..utils import console


@click.command()
def setup() -> None:
    """Interactive first-time setup wizard."""
    cfg = load_config()

    console.print(
        Panel(
            "[bold]qobuzdl-collab setup[/]\n\n"
            "You will need an [cyan]app_id[/], [cyan]secret[/] and at least one "
            "[cyan]auth token[/].\n"
            "These come from reverse-engineering the Qobuz desktop or mobile app.",
            border_style="blue",
        )
    )

    cfg["app_id"] = click.prompt("App ID  ", default=cfg.get("app_id", ""))
    cfg["secret"] = click.prompt("Secret  ", default=cfg.get("secret", ""))

    existing   = ", ".join(cfg.get("auth_tokens", []))
    tokens_raw = click.prompt(
        "Auth token(s)  [comma-separated if multiple]",
        default=existing or "",
    )
    cfg["auth_tokens"] = [t.strip() for t in tokens_raw.split(",") if t.strip()]

    console.print()
    cfg["download_dir"] = click.prompt(
        "Default download directory",
        default=cfg.get("download_dir"),
    )

    console.print("\nAvailable quality levels:")
    for k, qid in QUALITY_MAP.items():
        console.print(f"  [cyan]{k:<14}[/] {QUALITY_LABELS[qid]}")

    cfg["quality"] = click.prompt(
        "\nDefault quality",
        default=cfg.get("quality", "hi-res-192"),
        type=click.Choice(list(QUALITY_MAP)),
    )

    # ── quality fallback ──────────────────────────────────────────────────────
    console.print()
    console.print(
        "Enable quality fallback on CDN errors?\n"
        "  [dim]If a hi-res file is broken on Qobuz's CDN (connection drops after\n"
        "  1 byte on every retry), automatically retry at the next lower quality\n"
        "  rather than skipping the track.[/]"
    )
    cfg["quality_fallback"] = click.confirm("  Quality fallback", default=cfg.get("quality_fallback", True))

    if cfg["quality_fallback"]:
        console.print(
            "\n[bold]Quality fallback path[/] — ordered list of qualities to try, "
            "highest first.\n"
            "[dim]The download starts at your configured quality and walks down\n"
            "this list until one succeeds or the list is exhausted.\n"
            "Truncate the list at the lowest quality you are willing to accept.\n"
            f"Available (highest → lowest): {', '.join(QUALITY_ORDER)}[/]\n"
        )
        current_path = ", ".join(
            cfg.get("quality_fallback_path", ["hi-res-192", "hi-res", "cd"])
        )
        while True:
            raw = click.prompt("Fallback path (comma-separated)", default=current_path)
            parsed = [q.strip() for q in raw.split(",") if q.strip() in QUALITY_ORDER]
            invalid = [q.strip() for q in raw.split(",") if q.strip() and q.strip() not in QUALITY_ORDER]
            if invalid:
                console.print(
                    f"  [yellow]⚠ Unrecognised quality name(s): {', '.join(invalid)}\n"
                    f"  Valid values: {', '.join(QUALITY_ORDER)}[/]"
                )
                continue
            if not parsed:
                console.print(
                    f"  [yellow]⚠ Path is empty — enter at least one quality name.[/]"
                )
                continue
            cfg["quality_fallback_path"] = parsed
            console.print(
                f"  [dim]Fallback path set to: {' → '.join(parsed)}[/]"
            )
            break

    # ── duration check ────────────────────────────────────────────────────────
    console.print()
    console.print(
        "Enable duration check for downloaded files?\n"
        f"  [dim]When an auth token expires, Qobuz returns a valid HTTP 200 response\n"
        f"  but serves a {PREVIEW_DURATION:.0f}-second preview clip instead of the full track.\n"
        f"  With this option on, every downloaded file is inspected with mutagen.\n"
        f"  If the file is within ±{PREVIEW_DURATION_TOLERANCE:.0f}s of {PREVIEW_DURATION:.0f}s but the track should be longer,\n"
        f"  qobuz-dl retries with each configured token in turn.\n"
        f"  If all tokens return previews, the track fails and on_final_failure applies.\n"
        f"  Adds a brief mutagen read after each track — negligible overhead.[/]"
    )
    cfg["duration_check"] = click.confirm(
        "  Duration check",
        default=cfg.get("duration_check", True),
    )

    # ── templates ─────────────────────────────────────────────────────────────
    console.print(TEMPLATE_HELP)

    cfg["folder_template"] = click.prompt(
        "Folder template",
        default=cfg.get("folder_template", "{main_artist}/{year} - {album}"),
    )
    cfg["track_template"] = click.prompt(
        "Track filename template  (no extension)",
        default=cfg.get("track_template", "{track:02d} - {title}"),
    )

    console.print()
    cfg["include_version"] = click.confirm(
        "Include edition/version in album and track titles?",
        default=cfg.get("include_version", True),
    )
    cfg["strip_feat_from_album_title"] = click.confirm(
        "Try to strip featured artists from album titles?",
        default=cfg.get("strip_feat_from_album_title", False),
    )
    cfg["strip_feat_from_track_title"] = click.confirm(
        "Try to strip featured artists from track titles?",
        default=cfg.get("strip_feat_from_track_title", False),
    )
    cfg["multi_disc"] = click.confirm(
        "Create Disc N/ subdirectories for multi-disc albums?",
        default=cfg.get("multi_disc", True),
    )
    cfg["embed_metadata"] = click.confirm(
        "Embed metadata tags in downloaded files?",
        default=cfg.get("embed_metadata", True),
    )

    if cfg["embed_metadata"]:
        cfg["force_main_album_artist"] = click.confirm(
            "  Set Album Artist tag to Main Artist only?",
            default=cfg.get("force_main_album_artist", False),
        )

        current_fields = {**METADATA_FIELDS, **cfg.get("metadata_fields", {})}
        console.print(
            "\n[bold]Metadata fields[/] — choose which tags to embed in audio files.\n"
            "[dim]Note: 'cover' here means art embedded inside the file;\n"
            "      cover.jpg on disk is controlled by 'Save cover.jpg?' below.[/]\n"
        )
        set_all = click.confirm("  Set all fields at once?", default=False)
        if set_all:
            enable_all = click.confirm("  Enable all metadata fields?", default=True)
            cfg["metadata_fields"] = {k: enable_all for k in METADATA_FIELDS}
        else:
            fields: dict = {}
            for field in METADATA_FIELDS:
                fields[field] = click.confirm(
                    f"  Embed {click.style(field, fg='cyan')}?",
                    default=current_fields.get(field, True),
                )
            cfg["metadata_fields"] = fields

    cfg["save_cover"] = click.confirm(
        "Save cover.jpg alongside tracks?",
        default=cfg.get("save_cover", True),
    )

    if cfg["save_cover"] or cfg.get("embed_metadata", True):
        from ..constants import COVER_SIZE_LABELS
        console.print("\n[bold]Cover art sizes[/]")
        console.print("[dim]Available sizes:[/]")
        for k, label in COVER_SIZE_LABELS.items():
            console.print(f"  [cyan]{k:<12}[/] {label}")
        console.print()

    if cfg["save_cover"]:
        cfg["cover_size"] = click.prompt(
            "  Size for cover.jpg saved to disk",
            default=cfg.get("cover_size", "original"),
            type=click.Choice(["thumbnail", "small", "large", "original"]),
        )

    if cfg.get("embed_metadata", True):
        embed_cover_enabled = {
            **METADATA_FIELDS, **cfg.get("metadata_fields", {})
        }.get("cover", True)
        if embed_cover_enabled:
            cfg["embed_cover_size"] = click.prompt(
                "  Size for cover art embedded inside audio files",
                default=cfg.get("embed_cover_size", "original"),
                type=click.Choice(["thumbnail", "small", "large", "original"]),
            )
            if cfg["embed_cover_size"] == "original":
                console.print(
                    "  [dim]Original images may exceed the 16 MiB FLAC metadata-block limit.[/]"
                )
                cfg["embed_cover_oversize_action"] = click.prompt(
                    "  If original image is too large for embedding",
                    default=cfg.get("embed_cover_oversize_action", "use_large"),
                    type=click.Choice(["use_large", "skip"]),
                )

    cfg["skip_existing"] = click.confirm(
        "Skip already-downloaded tracks?",
        default=cfg.get("skip_existing", True),
    )

    # ── filename truncation ───────────────────────────────────────────────────
    console.print()
    console.print("[bold]Filename truncation[/]")
    console.print(
        "[dim]Prevents 'File name too long' errors on filesystems with a 255-byte limit.\n"
        "Limits apply to individual path segments (folder names, filenames), not the full path.\n"
        "Byte lengths matter, not character counts — CJK/accented names can hit the limit sooner.[/]\n"
    )
    cfg["truncate_filename"] = click.confirm(
        "  Truncate track filenames that exceed the byte limit?",
        default=cfg.get("truncate_filename", True),
    )
    if not cfg["truncate_filename"]:
        console.print(
            "  [yellow]⚠ Warning: disabling filename truncation will cause a hard write failure\n"
            "    for any track whose filename exceeds the filesystem limit.[/]"
        )
    cfg["filename_truncate_pos"] = click.prompt(
        "  Where to truncate filenames",
        default=cfg.get("filename_truncate_pos", "end"),
        type=click.Choice(["end", "middle"]),
    )
    _fn_marker_hint    = (
        "recommended: '...'" if cfg["filename_truncate_pos"] == "middle"
        else "recommended: leave blank"
    )
    _fn_marker_current = cfg.get("filename_truncate_marker", "...")
    console.print(
        f"  Truncation marker at cut point  [{_fn_marker_hint}]\n"
        f"  [dim]Current value: {_fn_marker_current!r}[/]"
    )
    _fn_marker_raw = click.prompt(
        "  New value (Enter = keep current, single space = set to blank)",
        default="\x00",
        show_default=False,
    )
    if _fn_marker_raw == "\x00":
        cfg["filename_truncate_marker"] = _fn_marker_current
    elif _fn_marker_raw == " ":
        cfg["filename_truncate_marker"] = ""
    else:
        cfg["filename_truncate_marker"] = _fn_marker_raw
    cfg["filename_max_bytes"] = click.prompt(
        "  Maximum filename bytes  [255 = Linux/macOS limit; try 200 for SMB shares]",
        default=int(cfg.get("filename_max_bytes", 255)),
        type=click.IntRange(16, 255),
    )

    # ── folder truncation ─────────────────────────────────────────────────────
    console.print()
    console.print("[bold]Folder name truncation[/]")
    console.print(
        "[dim]Controls truncation of individual folder segments (not the full path).[/]\n"
    )
    cfg["truncate_folder"] = click.confirm(
        "  Truncate folder names that exceed the byte limit?",
        default=cfg.get("truncate_folder", True),
    )
    cfg["folder_truncate_pos"] = click.prompt(
        "  Where to truncate folder names",
        default=cfg.get("folder_truncate_pos", "end"),
        type=click.Choice(["end", "middle"]),
    )
    _fo_marker_hint    = (
        "recommended: '...'" if cfg["folder_truncate_pos"] == "middle"
        else "recommended: leave blank"
    )
    _fo_marker_current = cfg.get("folder_truncate_marker", "")
    console.print(
        f"  Truncation marker at cut point  [{_fo_marker_hint}]\n"
        f"  [dim]Current value: {_fo_marker_current!r}[/]"
    )
    _fo_marker_raw = click.prompt(
        "  New value (Enter = keep current, single space = set to blank)",
        default="\x00",
        show_default=False,
    )
    if _fo_marker_raw == "\x00":
        cfg["folder_truncate_marker"] = _fo_marker_current
    elif _fo_marker_raw == " ":
        cfg["folder_truncate_marker"] = ""
    else:
        cfg["folder_truncate_marker"] = _fo_marker_raw
    cfg["folder_max_bytes"] = click.prompt(
        "  Maximum folder name bytes  [255 = Linux/macOS limit; try 200 for SMB shares]",
        default=int(cfg.get("folder_max_bytes", 255)),
        type=click.IntRange(16, 255),
    )

    # ── network ───────────────────────────────────────────────────────────────
    console.print()
    cfg["retries"] = click.prompt(
        "Retries on network failure  [0 = no retries]",
        default=int(cfg.get("retries", 3)),
        type=click.IntRange(0, 20),
    )

    console.print(
        "\nOn final failure (after all retries and fallbacks are exhausted), "
        "what should happen?\n"
        "  [cyan]keep_partial[/]   — keep the partial file on disk (resume-friendly)\n"
        "  [cyan]delete_partial[/] — delete just the failed track and continue\n"
        "  [cyan]delete_album[/]   — delete every file downloaded for that album and continue"
    )
    cfg["on_final_failure"] = click.prompt(
        "On final failure",
        default=cfg.get("on_final_failure", "delete_partial"),
        type=click.Choice(["keep_partial", "delete_partial", "delete_album"]),
    )

    socks = click.prompt(
        "\nSOCKS5 proxy  [host:port — leave blank for none]",
        default=cfg.get("socks5_proxy", ""),
    )
    cfg["socks5_proxy"] = socks.strip()

    save_config(cfg)
    console.print(f"\n[bold green]✓[/] Config saved → {CONFIG_FILE}")
