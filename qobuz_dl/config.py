"""
config.py — Config file load/save and per-field metadata gate resolver.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .constants import CONFIG_FILE, CONFIG_DIR, DEFAULT_CONFIG, METADATA_FIELDS
from .utils import dbg


def load_config() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        dbg(f"Loading config from {CONFIG_FILE}")
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        dbg(f"Config loaded — quality={cfg.get('quality')!r}  download_dir={cfg.get('download_dir')!r}")
        return cfg
    dbg("No config file found — using built-in defaults")
    return dict(DEFAULT_CONFIG)


def save_config(cfg: Dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def get_meta_fields(cfg: Dict[str, Any]) -> Optional[Dict[str, bool]]:
    """Return the resolved per-field metadata gates, or None if embedding is disabled.

    Merges METADATA_FIELDS defaults with whatever is stored in cfg so that
    fields added in future versions are enabled by default for existing configs.
    """
    if not cfg.get("embed_metadata", True):
        return None
    resolved = dict(METADATA_FIELDS)
    resolved.update(cfg.get("metadata_fields", {}))
    return resolved
