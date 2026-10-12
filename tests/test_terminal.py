"""Terminal behaviour: the pretty report, progress, Ctrl+C, and refusing too-broad scans."""

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import write_project

from agentguard import cli
from agentguard.cli import EXIT_ERROR, EXIT_INTERRUPTED, EXIT_OK, _Progress, main
from agentguard.crawler import crawl, too_broad

AGENT = """
from openai import OpenAI
client = OpenAI()
messages = []
while True:
    r = client.chat.completions.create(model="gpt-4o", messages=messages, max_tokens=10)
    messages.append(r.choices[0].message)
"""


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    return tmp_path


def test_pretty_report_sections(repo, capsys):
    write_project(repo, {"agent.py": AGENT})
    main(["--pretty", "--no-color"])
    out = capsys.readouterr().out
    for section in ("FILE ANALYSIS", "COST SUMMARY", "TOP RISK FILES", "RECOMMENDATIONS"):
        assert section in out
    assert "/_/  |_" in out  # the banner
    assert "Risk: ⚠ CRITICAL" in out
    assert "line 5  AG001" in out
    assert "\033[" not in out


def test_pretty_report_colours(repo, capsys):
    write_project(repo, {"agent.py": AGENT})
    main(["--pretty", "--color"])
    assert "\033[1;91m" in capsys.readouterr().out


def test_clean_project_pretty(repo, capsys):
    write_project(repo, {"ok.py": "print('no llm here')\n"})
    assert main(["--pretty", "--no-color"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "No LLM API calls found" in out and "No cost risks found" in out


def test_plain_is_default_when_piped(repo, capsys):
    write_project(repo, {"agent.py": AGENT})
    main([])
    out = capsys.readouterr().out
    assert "agent.py:5:9: AG001 [high]" in out
    assert "FILE ANALYSIS" not in out


def test_plain_flag_overrides(repo, capsys, monkeypatch):
    write_project(repo, {"agent.py": AGENT})
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    main(["--plain", "--no-color"])
    assert "FILE ANALYSIS" not in capsys.readouterr().out


def test_refuses_home_directory(repo, capsys, monkeypatch):
    write_project(repo, {"agent.py": AGENT})
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: repo))
    assert main([]) == EXIT_ERROR
    assert "refusing to scan" in capsys.readouterr().err
    assert main(["--scan-anyway", "--fail-on", "never"]) == EXIT_OK


def test_too_broad():
    assert too_broad(Path.cwd().anchor)
    assert too_broad(str(Path.home()))
    assert not too_broad(str(Path(__file__).parent))


def test_ctrl_c_exits_cleanly(repo, capsys, monkeypatch):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "crawl", interrupted)
    monkeypatch.setattr(sys, "argv", ["agentguard"])
    with pytest.raises(SystemExit) as e:
        cli.entry()
    assert e.value.code == EXIT_INTERRUPTED
    err = capsys.readouterr().err
    assert "interrupted" in err and "Traceback" not in err


def test_progress_line():
    buf = io.StringIO()
    p = _Progress(buf, enabled=True, delay=0)
    p.update("analysing 5 / 10 files")
    assert buf.getvalue().startswith("\r") and "5 / 10" in buf.getvalue()
    p.clear()
    assert buf.getvalue().endswith("\r")

    quiet = io.StringIO()
    _Progress(quiet, enabled=False, delay=0).update("x")
    assert quiet.getvalue() == ""


@pytest.mark.skipif(os.name != "nt", reason="Windows file attributes")
def test_windows_hidden_folders_are_skipped(tmp_path):
    import ctypes

    write_project(tmp_path, {"a.py": "", "AppDataLike/b.py": ""})
    assert ctypes.windll.kernel32.SetFileAttributesW(str(tmp_path / "AppDataLike"), 0x2)
    assert [p.name for p in crawl([str(tmp_path)])] == ["a.py"]


def test_pretty_survives_narrow_console_encoding(repo):
    write_project(repo, {"agent.py": AGENT})
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    proc = subprocess.run([sys.executable, "-m", "agentguard", "--pretty"], capture_output=True, env=env, cwd=repo)
    assert proc.returncode == 1, proc.stderr.decode(errors="replace")
    assert b"Traceback" not in proc.stderr
    assert "FILE ANALYSIS" in proc.stdout.decode("utf-8")
