"""Find the Python files to analyse."""

from __future__ import annotations

import contextlib
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


def _excluded(path: Path, base: Path, patterns: Sequence[str]) -> bool:
    """Match against the path relative to the scanned directory and to the working directory,
    so `exclude = ["bench/*"]` in pyproject.toml works whichever directory is scanned."""
    rels = {path.relative_to(base).as_posix()}
    with contextlib.suppress(ValueError):
        rels.add(path.relative_to(Path.cwd().resolve()).as_posix())
    return any(fnmatch.fnmatch(r, p) or fnmatch.fnmatch(r, p.rstrip("/") + "/*") for r in rels for p in patterns)


def _skip_dir(name: str) -> bool:
    # Hidden directories (.git, .venv, .tox, ...) are never project source.
    return name in SKIP_DIRS or name.startswith(".") or name.endswith(".egg-info")


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
            here = Path(dirpath)
            dirnames[:] = sorted(d for d in dirnames if not _skip_dir(d) and not _excluded(here / d, base, exclude))
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                path = here / name
                if path.is_symlink() or _excluded(path, base, exclude):
                    continue
                found.add(path)
                if len(found) > MAX_FILES:
                    raise RuntimeError(f"more than {MAX_FILES} Python files; narrow the path or use --exclude")
    return sorted(found)
