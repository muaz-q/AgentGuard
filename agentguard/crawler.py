"""Project Crawler — recursively finds all candidate agentic files."""

import os
from pathlib import Path
from typing import List

SUPPORTED_EXTENSIONS = {".py", ".js", ".ts"}

SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".mypy_cache",
    "dist",
    "build",
    ".cache",
    ".next",
    "coverage",
    "env",
}

MAX_FILES = 5000  # safety guard


def crawl(root_dir: str) -> List[Path]:
    """Recursively traverse root_dir and return all candidate files."""
    root = Path(root_dir).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {root_dir}")

    candidates = []

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for fname in filenames:
            path = Path(dirpath) / fname

            if path.is_symlink():
                continue

           
            if path.suffix in SUPPORTED_EXTENSIONS:
                candidates.append(path)

            if len(candidates) >= MAX_FILES:
                print(f"⚠ Reached file scan limit ({MAX_FILES}). Stopping early.")
                return sorted(candidates)

    return sorted(candidates)