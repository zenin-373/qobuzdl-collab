"""
cli/config_cmd.py — The `config` command: view and set individual config values,
including dot-notation access for metadata_fields.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional

import click
from rich.table import Table

from ..config import load_config, save_config
from ..constants import DEFAULT_CONFIG, METADATA_FIELDS, QUALITY_ORDER
from ..utils import console


# ─────────────────────────────────────────────────────────────────────────────
# Shell-completion callbacks
# ─────────────────────────────────────────────────────────────────────────────

_BOOL_CONFIG_KEYS = {
    "embed_metadata", "save_cover", "skip_existing", "multi_disc",
    "include_version", "force_main_album_artist", "strip_feat_from_album_title",
    "strip_feat_from_track_title", "truncate_filename", "truncate_folder",
    "quality_fallback", "duration_check",
}


def _complete_config_key(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> List[Any]:
    from click.shell_completion import CompletionItem

    plain_keys = list(DEFAULT_CONFIG.keys())
    dot_keys   = (
        [f"metadata_fields.{f}" for f in METADATA_FIELDS]
        + ["metadata_fields.all"]
    )
    return [
        CompletionItem(k)
        for k in plain_keys + dot_keys
        if k.startswith(incomplete)
    ]


def _complete_config_value(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> List[Any]:
    from click.shell_completion import CompletionItem

    key = ctx.params.get("key") or ""

    if key == "quality":
        from ..constants import QUALITY_MAP
        return [CompletionItem(k) for k in QUALITY_MAP if k.startswith(incomplete)]

    if key == "quality_fallback_path":
        return [CompletionItem(q) for q in QUALITY_ORDER if q.startswith(incomplete)]

    if key in ("cover_size", "embed_cover_size"):
        from ..constants import COVER_SIZES
        return [
            CompletionItem(k) for k in COVER_SIZES if k.startswith(incomplete)
        ]

    if key == "embed_cover_oversize_action":
        return [
            CompletionItem(v)
            for v in ("use_large", "skip")
            if v.startswith(incomplete)
        ]

    if key == "on_final_failure":
        return [
            CompletionItem(v)
            for v in ("keep_partial", "delete_partial", "delete_album")
            if v.startswith(incomplete)
        ]

    if key in ("filename_truncate_pos", "folder_truncate_pos"):
        return [
            CompletionItem(v) for v in ("end", "middle") if v.startswith(incomplete)
        ]

    if key in _BOOL_CONFIG_KEYS or key.startswith("metadata_fields"):
        return [
            CompletionItem(v) for v in ("true", "false") if v.startswith(incomplete)
        ]

    return []


# ─────────────────────────────────────────────────────────────────────────────
# Command
# ─────────────────────────────────────────────────────────────────────────────

@click.command("config")
@click.argument("key",   required=False, shell_complete=_complete_config_key)
@click.argument("value", required=False, shell_complete=_complete_config_value)
def config_cmd(key: Optional[str], value: Optional[str]) -> None:
    """View or set a configuration value.

    \b
    Examples:
      qobuz-dl config                                 # print all settings
      qobuz-dl config download_dir                    # print one value
      qobuz-dl config download_dir ~/Music            # set a value
      qobuz-dl config quality cd
      qobuz-dl config folder_template "{artist}/{year} - {album}"
      qobuz-dl config quality_fallback true
      qobuz-dl config quality_fallback_path "hi-res-192, hi-res, cd"
      qobuz-dl config duration_check true

    \b
    Metadata fields use dot notation:
      qobuz-dl config metadata_fields                 # show all field toggles
      qobuz-dl config metadata_fields.copyright       # show one field
      qobuz-dl config metadata_fields.copyright false # disable copyright tag
      qobuz-dl config metadata_fields.all true        # enable every field
      qobuz-dl config metadata_fields.all false       # disable every field
    """
    cfg = load_config()

    # ── dot-notation: metadata_fields.FIELD ──────────────────────────────────
    if key and "." in key:
        parent, sub = key.split(".", 1)
        if parent != "metadata_fields":
            raise click.ClickException(
                f"Dot notation is only supported for metadata_fields, got '{parent}'"
            )

        fields: dict = {**METADATA_FIELDS, **cfg.get("metadata_fields", {})}

        if value is None:
            if sub == "all":
                t = Table(title="metadata_fields", border_style="blue", show_lines=False)
                t.add_column("Field",   style="cyan", no_wrap=True)
                t.add_column("Enabled", justify="center")
                for fname, fval in fields.items():
                    t.add_row(fname, "[green]✓[/]" if fval else "[red]✗[/]")
                console.print(t)
            else:
                if sub not in METADATA_FIELDS:
                    raise click.ClickException(
                        f"Unknown metadata field '{sub}'. "
                        f"Valid fields: {', '.join(METADATA_FIELDS)}"
                    )
                enabled = fields.get(sub, True)
                console.print(f"[cyan]metadata_fields.{sub}[/] = {json.dumps(enabled)}")
            return

        bool_val = value.lower() in ("true", "1", "yes", "on")
        if sub == "all":
            cfg["metadata_fields"] = {k: bool_val for k in METADATA_FIELDS}
            save_config(cfg)
            state = "enabled" if bool_val else "disabled"
            console.print(f"[green]✓[/] All metadata fields {state}.")
        else:
            if sub not in METADATA_FIELDS:
                raise click.ClickException(
                    f"Unknown metadata field '{sub}'. "
                    f"Valid fields: {', '.join(METADATA_FIELDS)}"
                )
            fields[sub] = bool_val
            cfg["metadata_fields"] = fields
            save_config(cfg)
            console.print(f"[green]✓[/] metadata_fields.{sub} = {json.dumps(bool_val)}")
        return

    # ── plain key ─────────────────────────────────────────────────────────────
    if key is None:
        table = Table(title="qobuz-dl config", border_style="blue", show_lines=False)
        table.add_column("Key",   style="cyan", no_wrap=True)
        table.add_column("Value", overflow="fold")
        for k, v in cfg.items():
            table.add_row(k, json.dumps(v))
        console.print(table)
        return

    if key == "metadata_fields" and value is None:
        fields = {**METADATA_FIELDS, **cfg.get("metadata_fields", {})}
        t = Table(title="metadata_fields", border_style="blue", show_lines=False)
        t.add_column("Field",   style="cyan", no_wrap=True)
        t.add_column("Enabled", justify="center")
        for fname, fval in fields.items():
            t.add_row(fname, "[green]✓[/]" if fval else "[red]✗[/]")
        console.print(t)
        return

    if value is None:
        console.print(f"[cyan]{key}[/] = {json.dumps(cfg.get(key, '<not set>'))}")
        return

    # ── type-aware coercion ───────────────────────────────────────────────────
    if key == "auth_tokens":
        cfg[key] = [t.strip() for t in value.split(",") if t.strip()]
    elif key == "quality_fallback_path":
        parsed = [q.strip() for q in value.split(",") if q.strip() in QUALITY_ORDER]
        invalid = [q.strip() for q in value.split(",") if q.strip() and q.strip() not in QUALITY_ORDER]
        if invalid:
            raise click.ClickException(
                f"Unrecognised quality name(s): {', '.join(invalid)}\n"
                f"Valid values: {', '.join(QUALITY_ORDER)}"
            )
        if not parsed:
            raise click.ClickException(
                f"No valid quality keys found in {value!r}.\n"
                f"Valid values: {', '.join(QUALITY_ORDER)}"
            )
        cfg[key] = parsed
    elif key in _BOOL_CONFIG_KEYS or key in (
        "strip_feat_from_album_title", "strip_feat_from_track_title"
    ):
        cfg[key] = value.lower() in ("true", "1", "yes", "on")
    elif key in ("filename_max_bytes", "folder_max_bytes", "retries"):
        try:
            cfg[key] = int(value)
        except ValueError:
            raise click.ClickException(f"{key} must be an integer, got {value!r}")
    elif key == "filename_truncate_pos":
        if value not in ("end", "middle"):
            raise click.ClickException("filename_truncate_pos must be 'end' or 'middle'")
        cfg[key] = value
    elif key == "folder_truncate_pos":
        if value not in ("end", "middle"):
            raise click.ClickException("folder_truncate_pos must be 'end' or 'middle'")
        cfg[key] = value
    elif key in ("cover_size", "embed_cover_size"):
        from ..constants import COVER_SIZES
        if value not in COVER_SIZES:
            raise click.ClickException(
                f"{key} must be one of: {', '.join(COVER_SIZES)}"
            )
        cfg[key] = value
    elif key == "embed_cover_oversize_action":
        if value not in ("use_large", "skip"):
            raise click.ClickException(
                "embed_cover_oversize_action must be 'use_large' or 'skip'"
            )
        cfg[key] = value
    elif key == "on_final_failure":
        valid = ("keep_partial", "delete_partial", "delete_album")
        if value not in valid:
            raise click.ClickException(
                f"on_final_failure must be one of: {', '.join(valid)}"
            )
        cfg[key] = value
    else:
        cfg[key] = value

    save_config(cfg)
    console.print(f"[green]✓[/] {key} = {json.dumps(cfg[key])}")
