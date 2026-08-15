"""
constants.py — Static constants and default configuration values.
No local imports; safe to import from anywhere in the package.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Any

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

CONFIG_DIR  = Path.home() / ".config" / "qobuz-dl"
CONFIG_FILE = CONFIG_DIR / "config.json"

# ─────────────────────────────────────────────────────────────────────────────
# URL patterns
# ─────────────────────────────────────────────────────────────────────────────

ALBUM_URL_RE  = re.compile(r"https?://(?:play|open)\.qobuz\.com/album/([a-zA-Z0-9]+)")
TRACK_URL_RE  = re.compile(r"https?://(?:play|open)\.qobuz\.com/track/(\d+)")
ARTIST_URL_RE = re.compile(r"https?://(?:play|open)\.qobuz\.com/artist/(\d+)")

# ─────────────────────────────────────────────────────────────────────────────
# Quality maps
# ─────────────────────────────────────────────────────────────────────────────

QUALITY_MAP: Dict[str, str] = {
    "mp3":        "5",
    "cd":         "6",
    "hi-res":     "7",
    "hi-res-192": "27",
}

QUALITY_LABELS: Dict[str, str] = {
    "5":  "MP3 320 kbps",
    "6":  "FLAC 16-bit / 44.1 kHz  (CD)",
    "7":  "FLAC 24-bit / up to 96 kHz",
    "27": "FLAC 24-bit / up to 192 kHz",
}

EXT_MAP: Dict[str, str] = {
    "5":  "mp3",
    "6":  "flac",
    "7":  "flac",
    "27": "flac",
}

# Descending quality order used for fallback chains.
QUALITY_ORDER: list[str] = ["hi-res-192", "hi-res", "cd", "mp3"]

# ─────────────────────────────────────────────────────────────────────────────
# Cover art sizes
# ─────────────────────────────────────────────────────────────────────────────

COVER_SIZES: Dict[str, str] = {
    "thumbnail": "50",
    "small":     "230",
    "large":     "600",
    "original":  "org",
}

COVER_SIZE_LABELS: Dict[str, str] = {
    "thumbnail": "50×50  (thumbnail)",
    "small":     "230×230",
    "large":     "600×600",
    "original":  "Original resolution (Usually 1400×1400 or 3000×3000)",
}

COVER_EMBED_MAX_BYTES: int = 16 * 1024 * 1024  # 16 MiB

ILLEGAL_CHARS = r'/\\?:*"<>|'

METADATA_FIELDS: Dict[str, bool] = {
    "title":        True,
    "artist":       True,
    "album_artist": True,
    "album":        True,
    "track_number": True,
    "disc_number":  True,
    "date":         True,
    "year":         True,
    "genre":        True,
    "label":        True,
    "copyright":    True,
    "isrc":         True,
    "upc":          True,
    "cover":        True,
}

PREVIEW_DURATION: float = 30.0
PREVIEW_DURATION_TOLERANCE: float = 2.0

DEFAULT_CONFIG: Dict[str, Any] = {
    "app_id":          "",
    "auth_tokens":     [],
    "secret":          "",
    "api_base":        "https://www.qobuz.com/api.json/0.2/",
    "download_dir":    str(Path.home() / "Music" / "Qobuz"),
    "quality":         "hi-res-192",
    "folder_template": "{main_artist}/{album} - {year} [{quality}]",
    "track_template":  "{title}",
    "multi_disc":      True,
    "save_cover":      True,
    "cover_size":      "original",
    "embed_cover_size": "original",
    "embed_cover_oversize_action": "use_large",
    "embed_metadata":  True,
    "metadata_fields": dict(METADATA_FIELDS),
    "skip_existing":   True,
    "retries":         3,
    "on_final_failure": "delete_partial",
    "socks5_proxy":    "",
    "include_version": True,
    "force_main_album_artist": False,
    "strip_feat_from_album_title": False,
    "strip_feat_from_track_title": False,
    "quality_fallback":      True,
    "quality_fallback_path": ["hi-res-192", "hi-res", "cd"],
    "duration_check": True,
    "truncate_folder":          True,
    "folder_truncate_pos":      "end",
    "folder_truncate_marker":   "",
    "folder_max_bytes":         255,
    "truncate_filename":        True,
    "filename_truncate_pos":    "end",
    "filename_truncate_marker": "...",
    "filename_max_bytes":       255,
}

TEMPLATE_HELP = """
\b
Template variables
──────────────────
  Folder:  {artist}     {main_artist}  {album}  {year}  {genre}  {label}  {quality}
           {artist_id}  {album_id}
  Track:   {track}      {disc}     {title}    {artist} {album}  {year}
           {track_id}

Use Python format specs — e.g. {track:02d} for zero-padded track numbers.

Examples
─────────
  Folder template:  {main_artist}/{album} - {year} [{quality}]
  Track  template:  {title}
"""
