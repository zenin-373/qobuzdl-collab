"""
api.py — Qobuz API client.  Handles authentication, request signing, and
all API endpoints used by the downloader.
"""

from __future__ import annotations

import hashlib
import random
import time
from typing import Any, Dict, List

import click
import requests

from .constants import DEFAULT_CONFIG
from .utils import dbg


class QobuzAPI:
    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.cfg     = cfg
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "qobuz-dl/1.0"})
        if cfg.get("socks5_proxy"):
            proxy = f"socks5://{cfg['socks5_proxy']}"
            self.session.proxies = {"http": proxy, "https": proxy}

    # ── authentication ────────────────────────────────────────────────────────

    @property
    def token(self) -> str:
        tokens = self.cfg.get("auth_tokens", [])
        if not tokens:
            raise click.ClickException(
                "No auth tokens configured. Run [bold]qobuz-dl setup[/bold]."
            )
        return random.choice(tokens)

    @property
    def all_tokens(self) -> List[str]:
        """Return all configured auth tokens (deduplicated, order preserved)."""
        seen: set = set()
        result: List[str] = []
        for t in self.cfg.get("auth_tokens", []):
            if t not in seen:
                seen.add(t)
                result.append(t)
        return result

    def _headers(self) -> Dict[str, str]:
        return {
            "x-app-id":          self.cfg["app_id"],
            "x-user-auth-token": self.token,
        }

    def _headers_for_token(self, token: str) -> Dict[str, str]:
        return {
            "x-app-id":          self.cfg["app_id"],
            "x-user-auth-token": token,
        }

    # ── request ───────────────────────────────────────────────────────────────

    def _get(self, endpoint: str, **params: Any) -> Any:
        base = self.cfg.get("api_base", DEFAULT_CONFIG["api_base"]).rstrip("/")
        url  = f"{base}/{endpoint.lstrip('/')}"
        safe_params = {k: ("***" if k == "request_sig" else v) for k, v in params.items()}
        dbg(f"GET {url}  params={safe_params}")
        r = self.session.get(url, headers=self._headers(), params=params, timeout=30)
        dbg(f"→ HTTP {r.status_code}  ({len(r.content)} bytes)")
        r.raise_for_status()
        return r.json()

    # ── endpoints ─────────────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 10, offset: int = 0) -> Dict:
        return self._get("catalog/search", query=query, limit=limit, offset=offset)

    def get_album(self, album_id: str) -> Dict:
        return self._get("album/get", album_id=album_id, extra="track_ids")

    def get_track(self, track_id: str) -> Dict:
        return self._get("track/get", track_id=track_id)

    def get_artist(self, artist_id: str) -> Dict:
        return self._get("artist/page", artist_id=artist_id, sort="release_date")

    def get_artist_releases(
        self,
        artist_id: str,
        release_type: str = "album",
        limit: int = 500,
        offset: int = 0,
    ) -> Dict:
        return self._get(
            "artist/getReleasesList",
            artist_id=artist_id,
            release_type=release_type,
            limit=limit,
            offset=offset,
            sort="release_date",
            track_size=1000,
        )

    def _sign_track_url_params(self, track_id: int, quality: str) -> Dict[str, Any]:
        """Build the signed parameters for track/getFileUrl (token-agnostic)."""
        secret  = self.cfg["secret"]
        ts      = int(time.time())
        r_sig   = (
            f"trackgetFileUrlformat_id{quality}"
            f"intentstreamtrack_id{track_id}{ts}{secret}"
        )
        sig_md5 = hashlib.md5(r_sig.encode()).hexdigest()
        return dict(
            format_id=quality,
            intent="stream",
            track_id=track_id,
            request_ts=ts,
            request_sig=sig_md5,
        )

    def get_track_url(self, track_id: int, quality: str) -> str:
        """Fetch a signed stream URL using a randomly-chosen auth token."""
        params = self._sign_track_url_params(track_id, quality)
        dbg(f"Requesting file URL — track_id={track_id}  format_id={quality}  ts={params['request_ts']}")
        data = self._get("track/getFileUrl", **params)
        dbg(
            f"File URL obtained — mime={data.get('mime_type')!r}  "
            f"sampling_rate={data.get('sampling_rate')}  bit_depth={data.get('bit_depth')}"
        )
        return data["url"]

    def get_track_url_with_token(self, track_id: int, quality: str, token: str) -> str:
        """Fetch a signed stream URL using a *specific* auth token.

        Used by the duration-check retry loop to cycle through each configured
        token individually rather than picking one at random.
        """
        params = self._sign_track_url_params(track_id, quality)
        dbg(
            f"Requesting file URL (token override) — track_id={track_id}  "
            f"format_id={quality}  ts={params['request_ts']}"
        )
        base = self.cfg.get("api_base", DEFAULT_CONFIG["api_base"]).rstrip("/")
        url  = f"{base}/track/getFileUrl"
        r = self.session.get(
            url,
            headers=self._headers_for_token(token),
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        dbg(
            f"File URL obtained (token override) — mime={data.get('mime_type')!r}  "
            f"sampling_rate={data.get('sampling_rate')}  bit_depth={data.get('bit_depth')}"
        )
        return data["url"]
