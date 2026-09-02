"""Static pack configuration loaded only from this package's tracked resource."""
from __future__ import annotations

import json
from pathlib import Path


_RESOURCE = Path(__file__).with_name("config.json")
configurations = json.loads(_RESOURCE.read_text(encoding="utf-8"))

if not isinstance(configurations, dict):
    raise RuntimeError("pack config.json must contain an object")

__all__ = ["configurations"]
