import json
import os
import subprocess
import sys

import pytest
from conftest import write_project

from agentguard.cli import EXIT_ERROR, EXIT_FINDINGS, EXIT_OK, main

UNBOUNDED = """
from openai import OpenAI
client = OpenAI()
while True:
    client.chat.completions.create(model="gpt-4o", messages=[], max_tokens=10)
"""
CLEAN = """
from openai import OpenAI
client = OpenAI()
for i in range(3):
    client.chat.completions.create(model="gpt-4o", messages=[], max_tokens=10)
"""


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NO_COLOR", raising=False)
    return tmp_path


def test_json_is_valid_and_alone_on_stdout(repo, capsys):
    # Regression: 0.2.x printed debug lines before the JSON.
    write_project(repo, {"agent.py": UNBOUNDED})
    code = main(["--format", "json", "."])
    data = json.loads(capsys.readouterr().out)
    assert code == EXIT_FINDINGS
    assert [f["rule"] for f in data["findings"]] == ["AG001"]
    assert data["findings"][0]["path"] == "agent.py"
    assert set(data["estimate"]["totals"]) == {"1", "10", "100"}


def test_legacy_flags(repo, capsys):
    write_project(repo, {"agent.py": CLEAN})
    code = main(["--root_dir", ".", "--json", "--json_out", "r.json", "-q"])
    assert code == EXIT_OK
    assert json.loads((repo / "r.json").read_text())["summary"]["call_sites"] == 1


def test_sarif(repo, capsys):
    write_project(repo, {"src/agent.py": UNBOUNDED})
    main(["-f", "sarif", "-o", "out.sarif"])
    sarif = json.loads((repo / "out.sarif").read_text(encoding="utf-8"))
    run = sarif["runs"][0]
    assert sarif["version"] == "2.1.0"
    assert {r["id"] for r in run["tool"]["driver"]["rules"]} >= {"AG001", "AG007"}
    (res,) = run["results"]
    assert res["ruleId"] == "AG001" and res["level"] == "error"
    loc = res["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "src/agent.py"
    assert loc["region"]["startLine"] == 4


def test_markdown(repo, capsys):
    write_project(repo, {"agent.py": UNBOUNDED})
    main(["-f", "markdown"])
    out = capsys.readouterr().out
    assert "| 🔴 | `AG001` | `agent.py:4` |" in out
    assert "Estimated cost per run" in out


def test_text_has_locations_and_costs(repo, capsys):
    write_project(repo, {"agent.py": UNBOUNDED})
    main(["--no-color"])
    out = capsys.readouterr().out
    assert "agent.py:4:5: AG001 [high]" in out
    assert "N=100" in out
    assert "\033[" not in out


@pytest.mark.parametrize(
    "args, code",
    [
        ([], EXIT_FINDINGS),
        (["--fail-on", "never"], EXIT_OK),
        (["--ignore", "AG001"], EXIT_OK),
        (["--select", "AG006"], EXIT_OK),
    ],
)
def test_exit_codes(repo, capsys, args, code):
    write_project(repo, {"agent.py": UNBOUNDED})
    assert main(args) == code


def test_fail_on_low(repo, capsys):
    write_project(
        repo, {"agent.py": "from openai import OpenAI\nOpenAI().chat.completions.create(model='x', messages=[])\n"}
    )
    assert main([]) == EXIT_OK
    assert main(["--fail-on", "low"]) == EXIT_FINDINGS


def test_pyproject_config(repo, capsys):
    write_project(
        repo,
        {
            "agent.py": UNBOUNDED,
            "pyproject.toml": '[tool.agentguard]\nignore = ["AG001"]\nmodel = "gpt-4o-mini"\n',
        },
    )
    assert main(["-f", "json"]) == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["estimate"]["assumptions"]["default_model"] == "gpt-4o-mini"


def test_bad_config_key(repo, capsys):
    write_project(repo, {"agent.py": CLEAN, "pyproject.toml": "[tool.agentguard]\nnope = 1\n"})
    assert main([]) == EXIT_ERROR
    assert "unknown [tool.agentguard] key" in capsys.readouterr().err


def test_missing_path(repo, capsys):
    assert main(["does-not-exist"]) == EXIT_ERROR


def test_unknown_model(repo, capsys):
    write_project(repo, {"agent.py": CLEAN})
    assert main(["--model", "nope"]) == EXIT_ERROR


def test_list_commands(repo, capsys):
    assert main(["--list-rules"]) == EXIT_OK
    assert "AG005" in capsys.readouterr().out
    assert main(["--list-models"]) == EXIT_OK
    assert "claude-opus-5-5" in capsys.readouterr().out


def test_bad_rule_id(repo, capsys):
    with pytest.raises(SystemExit):
        main(["--select", "AG999"])


def test_narrow_console_encoding_does_not_crash(repo):
    # Regression: 0.2.x died with UnicodeEncodeError when stdout was cp1252.
    write_project(repo, {"agent.py": UNBOUNDED})
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    for fmt in ("text", "markdown", "json"):
        proc = subprocess.run([sys.executable, "-m", "agentguard", "-f", fmt], capture_output=True, env=env, cwd=repo)
        assert proc.returncode == EXIT_FINDINGS, proc.stderr.decode(errors="replace")
        assert b"Traceback" not in proc.stderr
