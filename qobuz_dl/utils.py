"""
utils.py — Pure helper functions: debug logging, filesystem/string utilities,
Qobuz data extractors, URL/ID parsing.  No network calls, no file I/O.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import click
from rich.console import Console

from .constants import (
    ALBUM_URL_RE,
    ARTIST_URL_RE,
    ILLEGAL_CHARS,
    TRACK_URL_RE,
)

console = Console()

# ─────────────────────────────────────────────────────────────────────────────
# Verbose / debug helpers
# ─────────────────────────────────────────────────────────────────────────────

# Module-level flag — set to True by the --verbose CLI option before any
# subcommand runs.  All code can call dbg() without passing state around.
_VERBOSE: bool = False


def dbg(msg: str) -> None:
    """Print a debug line when --verbose is active.  Silently a no-op otherwise."""
    if _VERBOSE:
        console.print(f"[dim][DEBUG][/dim] {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Filesystem / string helpers
# ─────────────────────────────────────────────────────────────────────────────

def clean_name(name: str) -> str:
    """Strip filesystem-illegal characters from a name segment."""
    for ch in ILLEGAL_CHARS:
        name = name.replace(ch, "_")
    return name.strip(". ")


def _utf8_trailing_len(data: bytes) -> int:
    """Return how many bytes to strip from the *end* of *data* to avoid splitting
    a multi-byte UTF-8 sequence.  Returns 0 if the last byte is already valid."""
    strip = 0
    for byte in reversed(data):
        if (byte & 0xC0) == 0x80:   # continuation byte
            strip += 1
        else:
            expected = 0
            if   (byte & 0x80) == 0x00: expected = 0   # ASCII
            elif (byte & 0xE0) == 0xC0: expected = 1   # 2-byte seq
            elif (byte & 0xF0) == 0xE0: expected = 2   # 3-byte seq
            elif (byte & 0xF8) == 0xF0: expected = 3   # 4-byte seq
            if expected > strip:
                strip += 1   # incomplete sequence — strip the lead byte too
            else:
                strip = 0    # sequence is complete — don't strip anything
            break
    return strip


def _utf8_leading_len(data: bytes) -> int:
    """Return how many bytes to strip from the *start* of *data* to avoid starting
    in the middle of a multi-byte UTF-8 sequence."""
    for i, byte in enumerate(data):
        if (byte & 0xC0) != 0x80:   # not a continuation byte — valid start
            return i
    return len(data)


def _truncate_bytes(text: str, max_bytes: int, pos: str, marker: str) -> str:
    """Truncate *text* so that its UTF-8 encoding fits within *max_bytes* bytes.

    *pos*    — where to cut: "end" removes a suffix, "middle" removes the centre.
    *marker* — inserted at the cut point (its own byte cost is included in the budget).
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text

    marker_bytes = marker.encode("utf-8")
    marker_len   = len(marker_bytes)

    if marker_len >= max_bytes:
        clipped = bytearray()
        for byte in marker_bytes:
            if len(clipped) + 1 > max_bytes:
                break
            clipped.append(byte)
        return clipped.decode("utf-8", errors="ignore")

    budget = max_bytes - marker_len

    if pos == "middle":
        half_front = budget // 2
        half_back  = budget - half_front

        front_raw = encoded[:half_front]
        front_raw = front_raw[: len(front_raw) - _utf8_trailing_len(front_raw)]

        back_raw  = encoded[-half_back:]
        back_raw  = back_raw[_utf8_leading_len(back_raw):]

        result = front_raw.decode("utf-8") + marker + back_raw.decode("utf-8")
    else:
        # "end" — keep the beginning, drop the tail
        front_raw = encoded[:budget]
        front_raw = front_raw[: len(front_raw) - _utf8_trailing_len(front_raw)]
        result    = front_raw.decode("utf-8") + marker

    return result


def truncate_name(name: str, cfg: Dict[str, Any], kind: str) -> str:
    """Apply configured truncation to a folder segment or filename stem+ext.

    *kind* is either ``"folder"`` or ``"filename"``.

    For filenames the extension is preserved verbatim; only the stem is subject
    to truncation so the file remains openable by its correct application.
    """
    if kind == "filename":
        enabled = cfg.get("truncate_filename", True)
        pos     = cfg.get("filename_truncate_pos",    "end")
        marker  = cfg.get("filename_truncate_marker", "...")
        budget  = int(cfg.get("filename_max_bytes",   255))

        if not enabled:
            return name

        dot = name.rfind(".")
        if dot > 0:
            stem = name[:dot]
            ext  = name[dot:]
        else:
            stem = name
            ext  = ""

        ext_bytes   = len(ext.encode("utf-8"))
        stem_budget = budget - ext_bytes
        if stem_budget <= 0:
            dbg(f"truncate_name: extension alone ({ext_bytes}B) ≥ budget ({budget}B) — returning as-is")
            return name

        stem = _truncate_bytes(stem, stem_budget, pos, marker)
        return stem + ext

    else:  # "folder"
        enabled = cfg.get("truncate_folder", True)
        pos     = cfg.get("folder_truncate_pos",    "end")
        marker  = cfg.get("folder_truncate_marker", "")
        budget  = int(cfg.get("folder_max_bytes",   255))

        if not enabled:
            return name

        return _truncate_bytes(name, budget, pos, marker)


def safe_format(template: str, **kwargs: Any) -> str:
    """Apply a template, sanitising every string value."""
    safe: Dict[str, Any] = {}
    for k, v in kwargs.items():
        safe[k] = clean_name(str(v)) if isinstance(v, str) else v
    try:
        return template.format_map(safe)
    except (KeyError, ValueError) as exc:
        raise click.ClickException(f"Template error: {exc}") from exc


def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} TB"


# ─────────────────────────────────────────────────────────────────────────────
# Qobuz data extractors
# ─────────────────────────────────────────────────────────────────────────────

def get_artists(album: Dict) -> str:
    artists = album.get("artists") or []
    if artists:
        return ", ".join(a["name"] for a in artists)
    return album.get("artist", {}).get("name", "Various Artists")


def get_main_artist(album: Dict) -> str:
    """Return only the primary artist of the album."""
    return album.get("artist", {}).get("name", "Unknown Artist")


def get_year(album: Dict) -> str:
    date = album.get("release_date_original", "")
    return date[:4] if date else "????"


def get_quality_tag(album: Dict) -> str:
    bits = album.get("maximum_bit_depth", 0)
    rate = album.get("maximum_sampling_rate", 0)
    if bits and rate:
        return f"FLAC {bits}bit {int(rate)}kHz"
    return "FLAC"


# ─────────────────────────────────────────────────────────────────────────────
# Title manipulation
# ─────────────────────────────────────────────────────────────────────────────

def apply_version_to_title(data: Dict) -> None:
    """Append the 'version' (edition) to the 'title' if present."""
    version = data.get("version")
    if version and version.strip():
        title = data.get("title", "")
        if f"({version})" not in title:
            data["title"] = f"{title} ({version.strip()})"


# Matches "(feat. ...)", "[ft. ...]", "{featuring ...}" etc. at the end of a title.
_FEAT_RE = re.compile(
    r"(?i)\s*[(\[{]\s*(?:feat\.?|ft\.?|featuring|featured)\s+([^()\[\]{}]+)[)\]}]\s*$"
)


def _track_has_featured_artist(track: Dict) -> bool:
    """Return True if Qobuz's performers string explicitly lists a FeaturedArtist role."""
    performers = track.get("performers", "")
    return bool(performers) and "FeaturedArtist" in performers


def strip_feat_from_track_title(track: Dict) -> None:
    """Remove '(feat. ...)' from a track's title. In-place."""
    if not _track_has_featured_artist(track):
        return
    track["title"] = _FEAT_RE.sub("", track.get("title", "")).strip()


def strip_feat_from_album_title(album: Dict) -> None:
    """Remove '(feat. ...)' from an album's title. In-place."""
    album["title"] = _FEAT_RE.sub("", album.get("title", "")).strip()


# ─────────────────────────────────────────────────────────────────────────────
# URL / ID parsing
# ─────────────────────────────────────────────────────────────────────────────

def resolve_url(token: str) -> Tuple[str, str]:
    """Return (kind, id) from a Qobuz URL."""
    m = ALBUM_URL_RE.search(token)
    if m:
        return "album", m.group(1)
    m = TRACK_URL_RE.search(token)
    if m:
        return "track", m.group(1)
    m = ARTIST_URL_RE.search(token)
    if m:
        return "artist", m.group(1)
    raise click.ClickException(
        f"Unrecognised URL: {token!r}\n"
        "  Only Qobuz URLs (https://play.qobuz.com/…) are accepted here."
    )


_ID_PREFIXES: Dict[str, str] = {
    "ar-id": "artist",
    "al-id": "album",
    "tr-id": "track",
}


def parse_targets(tokens: Tuple[str, ...]) -> List[Tuple[str, str]]:
    """Convert a flat CLI token list into (kind, id) pairs.

    Every token must be either a full Qobuz URL or preceded by a type prefix.
    Bare IDs without a prefix are rejected with a descriptive error.

        ar-id 707261 4698030  → [("artist", "707261"), ("artist", "4698030")]
        al-id 0060253780948   → [("album",  "0060253780948")]
        tr-id 23929921        → [("track",  "23929921")]
        https://play.qobuz.com/album/xyz  → [("album", "xyz")]
        123456                → ClickException (bare ID, no prefix)
    """
    targets: List[Tuple[str, str]] = []
    i = 0
    current_prefix = None

    while i < len(tokens):
        tok = tokens[i].strip()

        if tok in _ID_PREFIXES:
            current_prefix = _ID_PREFIXES[tok]
            i += 1
            if i >= len(tokens):
                raise click.ClickException(
                    f"'{tok}' must be followed by at least one ID."
                )
            continue

        if tok.startswith("http://") or tok.startswith("https://"):
            current_prefix = None
            targets.append(resolve_url(tok))
        else:
            if current_prefix:
                targets.append((current_prefix, tok))
            else:
                raise click.ClickException(
                    f"Bare ID {tok!r} has no type prefix.\n"
                    "  Use one of the key prefixes before your ID:\n"
                    "    ar-id <id>   — artist\n"
                    "    al-id <id>   — album\n"
                    "    tr-id <id>   — track\n"
                    "  Or pass a full Qobuz URL (https://play.qobuz.com/…)."
                )

        i += 1

    return targets
