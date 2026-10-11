"""Settings from ``[tool.agentguard]`` in pyproject.toml."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

KEYS = {
    "model": str,
    "prices": str,
    "fail_on": str,
    "exclude": list,
    "ignore": list,
    "select": list,
    "system_tokens": int,
    "input_tokens": int,
    "output_tokens": str,
    "depths": list,
}


def find_pyproject(start: Path) -> Optional[Path]:
    start = start.resolve()
    for d in [start, *start.parents] if start.is_dir() else start.parents:
        candidate = d / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def load(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {}
    with open(path, "rb") as f:
        data = tomllib.load(f)
    section = data.get("tool", {}).get("agentguard", {})
    out = {}
    for key, value in section.items():
        key = key.replace("-", "_")
        if key not in KEYS:
            raise ValueError(f"{path}: unknown [tool.agentguard] key {key!r}")
        if not isinstance(value, KEYS[key]):
            raise ValueError(f"{path}: [tool.agentguard] {key} must be a {KEYS[key].__name__}")
        out[key] = value
    return out
