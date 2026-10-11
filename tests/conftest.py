import textwrap
from pathlib import Path
from typing import Dict

import pytest

from agentguard.analyzer import ProjectAnalysis, analyze_project


def write_project(root: Path, files: Dict[str, str]) -> None:
    for name, src in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(src).lstrip("\n"), encoding="utf-8")


@pytest.fixture
def project(tmp_path):
    """project({"a.py": src, ...}) -> ProjectAnalysis of those files."""

    def run(files: Dict[str, str]) -> ProjectAnalysis:
        write_project(tmp_path, files)
        paths = sorted(p for p in tmp_path.rglob("*.py"))
        return analyze_project(paths, tmp_path)

    return run


@pytest.fixture
def single(project):
    """single(src) -> ProjectAnalysis of one file named agent.py."""
    return lambda src: project({"agent.py": src})


def rules(analysis: ProjectAnalysis):
    return sorted(f.rule for f in analysis.findings)
