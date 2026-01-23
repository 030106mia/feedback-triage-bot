from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict


DEFAULT_SETTINGS_PATH = "out/settings.json"


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def load_settings(path: str = DEFAULT_SETTINGS_PATH) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(settings: Dict[str, Any], path: str = DEFAULT_SETTINGS_PATH) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = dict(settings)
    payload["updated_at"] = _utc_now()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def merge_settings(partial: Dict[str, Any], path: str = DEFAULT_SETTINGS_PATH) -> Dict[str, Any]:
    cur = load_settings(path=path)
    out = dict(cur)
    for k, v in partial.items():
        out[k] = v
    return save_settings(out, path=path)

