"""MCP server: lets coding agents (Claude Code, Cursor, ...) run AgentGuard as a tool.

Install with `pip install "agentguard[mcp]"` and register the `agentguard-mcp` command
as a stdio server, e.g. `claude mcp add agentguard -- agentguard-mcp`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from agentguard import __version__, config
from agentguard.analyzer import analyze_project
from agentguard.crawler import crawl
from agentguard.estimator import Assumptions, estimate
from agentguard.pricing import DEFAULT_MODEL, PriceTable
from agentguard.reporter import build_json
from agentguard.rules import RULES

try:
    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations
except ImportError as e:  # pragma: no cover
    raise SystemExit('the MCP server needs the "mcp" extra: pip install "agentguard[mcp]"') from e

INSTRUCTIONS = """AgentGuard statically analyses Python code for patterns that make LLM agents
expensive: loops with no iteration cap around model calls, conversation history that grows
and is re-sent every turn, calls inside nested loops, recursion without a depth limit, and
calls with no output-token cap. Use `scan` after writing or changing code that calls an LLM,
and fix high-severity findings before finishing. Use `explain_rule` for a rule's details."""

server = MCPServer("agentguard", version=__version__, instructions=INSTRUCTIONS)


def scan_report(path: str, model: Optional[str] = None, ignore: Optional[List[str]] = None) -> Dict[str, Any]:
    target = Path(path).expanduser()
    if not target.exists():
        raise ValueError(f"no such file or directory: {path}")
    cfg = config.load(config.find_pyproject(target))
    files = crawl([str(target)], exclude=list(cfg.get("exclude", [])))
    root = target.resolve() if target.is_dir() else target.resolve().parent
    analysis = analyze_project(files, root)
    skip = set(ignore or cfg.get("ignore") or [])
    for fr in analysis.files:
        fr.findings = [f for f in fr.findings if f.rule not in skip]
    a = Assumptions(model=model or cfg.get("model", DEFAULT_MODEL))
    return build_json(analysis, estimate(analysis, PriceTable.load(cfg.get("prices")), a))


@server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def scan(path: str = ".", model: Optional[str] = None, ignore: Optional[List[str]] = None) -> Dict[str, Any]:
    """Scan a Python file or directory for LLM cost risks.

    Returns findings (rule, severity, file, line, message, fix) and a cost estimate per run.
    Reads [tool.agentguard] from the nearest pyproject.toml.

    Args:
        path: File or directory to scan.
        model: Model to price calls at when the code names none (e.g. "gpt-4.1-mini").
        ignore: Rule ids to skip, e.g. ["AG004", "AG006"].
    """
    return scan_report(path, model, ignore)


@server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def explain_rule(rule_id: str) -> Dict[str, str]:
    """Explain an AgentGuard rule (AG001-AG007): what it detects, its severity and the fix."""
    rule = RULES.get(rule_id.strip().upper())
    if rule is None:
        raise ValueError(f"unknown rule {rule_id!r}; known: {', '.join(RULES)}")
    return {"id": rule.id, "name": rule.name, "severity": rule.severity, "detects": rule.summary, "fix": rule.fix}


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
