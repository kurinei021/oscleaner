from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "age_days_tmp_cleanup": 7,
    "max_largest_entries": 8,
    "json_indent": 2,
    "protected_path_names": [],
    "excluded_path_fragments": [],
    "optional_cleanup": {
        "homebrew": False,
        "package_cache": False,
        "system_temp": False,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return DEFAULT_CONFIG.copy()
    with path.open("r", encoding="utf-8") as handle:
        user_config = json.load(handle)
    return _deep_merge(DEFAULT_CONFIG, user_config)
