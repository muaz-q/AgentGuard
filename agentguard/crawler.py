"""Find the Python files to analyse."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterable, List, Sequence

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".env",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".cache",
    ".next",
    "coverage",
    "site-packages",
    ".eggs",
}
MAX_FILES = 20_000


def _excluded(rel: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, p.rstrip("/") + "/*") for p in patterns)


def crawl(paths: Iterable[str], exclude: Sequence[str] = ()) -> List[Path]:
    """Python files under each path (files are taken as given), sorted and de-duplicated."""
    found = set()
    for raw in paths:
        p = Path(raw)
        if not p.exists():
            raise FileNotFoundError(f"no such file or directory: {raw}")
        if p.is_file():
            found.add(p.resolve())
            continue
        base = p.resolve()
        for dirpath, dirnames, filenames in os.walk(base):
            rel_dir = Path(dirpath).relative_to(base).as_posix()
            dirnames[:] = sorted(
                d
                for d in dirnames
                if d not in SKIP_DIRS
                and not d.endswith(".egg-info")
                and not _excluded(f"{rel_dir}/{d}".lstrip("./"), exclude)
            )
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                path = Path(dirpath) / name
                if path.is_symlink() or _excluded(path.relative_to(base).as_posix(), exclude):
                    continue
                found.add(path)
                if len(found) > MAX_FILES:
                    raise RuntimeError(f"more than {MAX_FILES} Python files; narrow the path or use --exclude")
    return sorted(found)
