from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml


def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def ensure_dir(path: str) -> str:
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def env(key: str, default: str) -> str:
    return os.getenv(key, default)
