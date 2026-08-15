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

# Maps user-facing size names to the URL suffix used by Qobuz's CDN.
# The API's album.image object uses "thumbnail" (_50), "small" (_230),
# and "large" (_600) keys; "original" (_org) is derived by replacing the
# suffix on the large URL.
COVER_SIZES: Dict[str, str] = {
    "thumbnail": "50",
    "small":     "230",
    "large":     "600",
    "original":  "org",
}

# Human-readable descriptions shown in setup / help text.
COVER_SIZE_LABELS: Dict[str, str] = {
    "thumbnail": "50×50  (thumbnail)",
    "small":     "230×230",
    "large":     "600×600",
    "original":  "Original resolution (Usually 1400×1400 or 3000×3000)",
}

# Maximum safe byte size for cover art embedded inside an audio file.
# FLAC's metadata block size is capped at 16 MiB by the spec; stay slightly
# under to leave room for other metadata blocks.
COVER_EMBED_MAX_BYTES: int = 16 * 1024 * 1024  # 16 MiB

# ─────────────────────────────────────────────────────────────────────────────
# Filesystem
# ─────────────────────────────────────────────────────────────────────────────

ILLEGAL_CHARS = r'/\\?:*"<>|'

# ─────────────────────────────────────────────────────────────────────────────
# Metadata
# ─────────────────────────────────────────────────────────────────────────────

# Canonical metadata field names and their defaults.
# "cover" controls embedded album art inside the audio file (separate from cover.jpg).
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
    "cover":        True,   # embedded cover art inside the audio file
}

# ─────────────────────────────────────────────────────────────────────────────
# Duration check
# ─────────────────────────────────────────────────────────────────────────────

# Qobuz serves a 30-second preview when an auth token has expired.  The server
# returns HTTP 200 and a valid audio file, so there is no HTTP-level signal —
# the only way to detect this is to measure the downloaded file's duration.
#
# A file is considered a preview when ALL of the following are true:
#   1. Its measured duration is within PREVIEW_DURATION_TOLERANCE seconds of
#      PREVIEW_DURATION (30 s).
#   2. The track's expected duration (from the API) exceeds
#      PREVIEW_DURATION + PREVIEW_DURATION_TOLERANCE, i.e. the track is
#      genuinely longer than 30 s and could not have been a real 30-second track.
PREVIEW_DURATION: float = 30.0          # seconds Qobuz uses for previews
PREVIEW_DURATION_TOLERANCE: float = 2.0 # ± seconds allowed when comparing

# ─────────────────────────────────────────────────────────────────────────────
# Default config
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_CONFIG: Dict[str, Any] = {
    "app_id":          "",
    "auth_tokens":     [],
    "secret":          "",
    "api_base":        "https://www.qobuz.com/api.json/0.2/",
    "download_dir":    str(Path.home() / "Music" / "Qobuz"),
    "quality":         "hi-res-192",
    "folder_template": "{main_artist}/{year} - {album}",
    "track_template":  "{title}",
    "multi_disc":      True,
    "save_cover":      True,
    # Size of the cover.jpg saved alongside tracks.
    # One of: "thumbnail", "small", "large", "original"
    "cover_size":      "original",
    # Size of the cover art embedded inside audio files.
    # One of: "thumbnail", "small", "large", "original"
    "embed_cover_size": "original",
    # What to do when the chosen embed size is "original" and the image
    # exceeds the 16 MiB FLAC metadata-block limit.
    # "use_large"    — fall back to the "large" (600×600) image
    # "skip"         — skip embedding cover art for that track
    "embed_cover_oversize_action": "use_large",
    "embed_metadata":  True,
    "metadata_fields": dict(METADATA_FIELDS),
    "skip_existing":   True,
    "retries":         3,
    "on_final_failure": "delete_partial",  # "keep_partial" | "delete_partial" | "delete_album"
    "socks5_proxy":    "",
    "include_version": True,
    "force_main_album_artist": False,
    "strip_feat_from_album_title": False,
    "strip_feat_from_track_title": False,
    # ── quality fallback ──────────────────────────────────────────────────────
    # When a track fails with a CDN IncompleteRead(1 bytes read, …) error on
    # every retry attempt, automatically retry at successively lower qualities.
    # Only CDN-broken errors trigger fallback; plain network errors do not.
    "quality_fallback":      True,
    # Ordered list of quality keys to attempt, highest first.  The download
    # starts at the user's configured quality (or -q override) and walks down
    # this list.  Truncate the list to stop at the lowest quality you accept.
    "quality_fallback_path": ["hi-res-192", "hi-res", "cd"],
    # ── duration check ────────────────────────────────────────────────────────
    # When True, every successfully downloaded file is inspected with mutagen.
    # If the file's audio duration is within PREVIEW_DURATION_TOLERANCE seconds
    # of PREVIEW_DURATION (30 s) AND the track's expected duration is longer,
    # Qobuz has returned a 30-second preview — the token is likely expired.
    # qobuz-dl retries with each remaining configured auth token in turn.
    # If every token produces a preview, on_final_failure is applied.
    "duration_check": True,
    # ── name truncation ───────────────────────────────────────────────────────
    "truncate_folder":          True,
    "folder_truncate_pos":      "end",    # "middle" | "end"
    "folder_truncate_marker":   "",
    "folder_max_bytes":         255,
    "truncate_filename":        True,
    "filename_truncate_pos":    "end",    # "middle" | "end"
    "filename_truncate_marker": "...",
    "filename_max_bytes":       255,
}

# ─────────────────────────────────────────────────────────────────────────────
# Help text
# ─────────────────────────────────────────────────────────────────────────────

TEMPLATE_HELP = """
\b
Template variables
──────────────────
  Folder:  {artist}     {album}    {year}     {genre}  {label}  {quality}
           {artist_id}  {album_id}
  Track:   {track}      {disc}     {title}    {artist} {album}  {year}
           {track_id}

Use Python format specs — e.g. {track:02d} for zero-padded track numbers.
Include {album_id} / {artist_id} / {track_id} to avoid collisions when two
releases share the same name.

Examples
─────────
  Folder template:  {main_artist}/{year} - {album}
  Track  template:  {title}
"""
