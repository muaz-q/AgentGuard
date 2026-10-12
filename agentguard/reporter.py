"""Render findings and cost estimates as text, JSON, SARIF or Markdown."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO

from agentguard import __version__
from agentguard.analyzer import Finding, ProjectAnalysis
from agentguard.estimator import Estimate, SiteEstimate
from agentguard.rules import RULES, SEVERITY_RANK

FORMATS = ("text", "json", "sarif", "markdown")
SARIF_LEVEL = {"high": "error", "medium": "warning", "low": "note"}
REPO_URL = "https://github.com/muaz-q/AgentGuard"


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def fmt_cost(x: float) -> str:
    if x == 0:
        return "$0"
    if x < 0.01:
        return f"${x:.4f}"
    if x < 100:
        return f"${x:,.2f}"
    return f"${x:,.0f}"


def _site_label(s: SiteEstimate) -> str:
    site = s.site
    where = f"{display_path(site.path)}:{site.line}"
    if site.target:
        return f"{where} -> {site.target.split(':', 1)[1]}()"
    return f"{where} {site.api} [{s.model}{'*' if s.model_assumed else ''}]"


def _top_sites(est: Estimate, n: int = 5) -> List[SiteEstimate]:
    worst = est.depths[-1]
    return sorted(est.sites, key=lambda s: s.high[worst].cost, reverse=True)[:n]


# ─── Text ─────────────────────────────────────────────────────────────────────


class _Style:
    def __init__(self, enabled: bool):
        self.enabled = enabled

    def __call__(self, text: object, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else str(text)


def use_color(stream: TextIO, flag: Optional[bool]) -> bool:
    if flag is not None:
        return flag
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(stream, "isatty") and stream.isatty()


def render_text(
    analysis: ProjectAnalysis, est: Estimate, out: TextIO, color: bool = False, show_costs: bool = True
) -> None:
    c = _Style(color)
    sev_color = {"high": "1;31", "medium": "1;33", "low": "36"}
    findings = analysis.findings

    for r in analysis.files:
        if r.error:
            out.write(f"{c(display_path(r.path), '1')}: {c('skipped', '33')} ({r.error})\n")
    for f in findings:
        loc = c(f"{display_path(f.path)}:{f.line}:{f.col}", "1")
        out.write(f"{loc}: {c(f.rule, sev_color[f.severity])} [{f.severity}] {f.message}\n")
        out.write(c(f"    fix: {f.fix}\n", "2"))

    n_files = len(analysis.files)
    n_sites = len(analysis.sites)
    counts = {s: sum(1 for f in findings if f.severity == s) for s in ("high", "medium", "low")}
    out.write("\n")
    summary = f"{len(findings)} finding(s) ({counts['high']} high, {counts['medium']} medium, {counts['low']} low)"
    out.write(f"{summary} in {n_files} file(s), {n_sites} LLM call site(s).\n")

    if not show_costs or not est.sites:
        return
    a = est.assumptions
    out.write("\n" + c("Estimated cost per run", "1") + "\n")
    out.write(f"  loops with no constant bound evaluated at N = {', '.join(map(str, est.depths))}\n")
    for d in est.depths:
        lo, hi = est.total(d, "low"), est.total(d, "high")
        out.write(
            f"  N={d:<5} {fmt_cost(lo.cost):>12} - {fmt_cost(hi.cost):<12} "
            f"({hi.calls:,.0f} calls, {hi.input + hi.output:,.0f} tokens at most)\n"
        )
    out.write("\n" + c("Largest cost drivers", "1") + f" (at N={est.depths[-1]}, high end)\n")
    for s in _top_sites(est):
        worst = s.high[est.depths[-1]]
        out.write(f"  {fmt_cost(worst.cost):>12}  {_site_label(s)}\n")
    out.write(
        c(
            f"\n  assumptions: {a.system_tokens} system + {a.input_tokens} input tokens per call, "
            f"{a.output_min}-{a.output_max} output tokens; default model {a.model}; prices as of {est.prices_as_of}\n",
            "2",
        )
    )
    if any(s.model_assumed for s in est.sites):
        out.write(c("  * model not found in code or price table; priced as the default model\n", "2"))
    if est.unknown_models:
        out.write(
            c(f"  unpriced models in code: {', '.join(sorted(est.unknown_models))} (add them with --prices)\n", "2")
        )


# ─── Pretty terminal report (the default on a terminal) ───────────────────────

BANNER = r"""
    ___                    __  ______                     __
   /   | ____ ____  ____  / /_/ ____/_  ______ __________/ /
  / /| |/ __ `/ _ \/ __ \/ __/ / __/ / / / __ `/ ___/ __  /
 / ___ / /_/ /  __/ / / / /_/ /_/ / /_/ / /_/ / /  / /_/ /
/_/  |_\__, /\___/_/ /_/\__/\____/\__,_/\__,_/_/   \__,_/
      /____/"""

_WIDTH = 72
_SEV_STYLE = {"high": ("⚠", "1;91"), "medium": ("⚡", "1;93"), "low": ("•", "96")}
_RISK = {
    "high": ("⚠ CRITICAL", "1;91"),
    "medium": ("⚡ MEDIUM", "1;93"),
    "low": ("• LOW", "1;96"),
    None: ("✓ CLEAN", "1;92"),
}
_SPEND_WARNING = 10.0  # USD per run


def render_pretty(
    analysis: ProjectAnalysis, est: Estimate, out: TextIO, color: bool = False, show_costs: bool = True
) -> None:
    c = _Style(color)
    w = out.write

    def rule(ch: str = "─") -> None:
        w(c(ch * _WIDTH, "2") + "\n")

    def section(title: str, code: str = "1;97") -> None:
        w("\n" + c(f"  {title}", code) + "\n")
        rule()

    w(c(BANNER, "1;96") + "\n")
    w(c(f"  Find LLM cost risks in agent code, before it runs  ·  v{__version__}", "2") + "\n")
    rule("═")

    findings_by_file: Dict[Path, List[Finding]] = {}
    for f in analysis.findings:
        findings_by_file.setdefault(f.path, []).append(f)
    est_by_file: Dict[Path, List[SiteEstimate]] = {}
    for s in est.sites:
        est_by_file.setdefault(s.site.path, []).append(s)

    active = [r for r in analysis.files if r.sites or findings_by_file.get(r.path)]
    section("FILE ANALYSIS")
    if not active:
        w(c("\n  No LLM API calls found.\n", "2"))
    for r in active:
        found = sorted(findings_by_file.get(r.path, []), key=lambda f: (-SEVERITY_RANK[f.severity], f.line))
        worst = found[0].severity if found else None
        label, code = _RISK[worst]
        loops = {lp.line for s in r.sites for lp in s.loops}
        w("\n" + c(f"  {display_path(r.path)}", "1;97") + c("  [🐍 py]", "2") + "\n")
        w(f"    Call sites: {c(len(r.sites), '1;96')}  •  Loops: {c(len(loops), '96')}  •  Risk: {c(label, code)}\n")
        if found:
            w(c("\n    Findings:", "1;93") + "\n")
            for f in found:
                icon, scode = _SEV_STYLE[f.severity]
                w(f"    {c(icon, scode)} {c(f'line {f.line}', '95')}  {c(f.rule, scode)}  {f.message}\n")
                w(c(f"        → {f.fix}", "92") + "\n")
        sites = est_by_file.get(r.path, [])
        if show_costs and sites:
            w(c("\n    Cost per run by loop depth (N = iterations of open-ended loops):", "2") + "\n")
            for d in est.depths:
                lo = sum(s.low[d].cost for s in sites)
                hi = sum(s.high[d].cost for s in sites)
                calls = sum(s.high[d].calls for s in sites)
                warn = c(f"  ⚠ over ${_SPEND_WARNING:.0f} per run", "1;91") if hi > _SPEND_WARNING else ""
                w(
                    f"      {c(f'N={d:>3}', '95')}  {c(fmt_cost(lo), '92')} → {c(fmt_cost(hi), '91')}"
                    f"  {c(f'({calls:,.0f} calls)', '2')}{warn}\n"
                )

    skipped = [r for r in analysis.files if r.error]
    if skipped:
        w(
            c(
                f"\n  Skipped {len(skipped)} file(s) that could not be parsed, e.g. {display_path(skipped[0].path)}",
                "33",
            )
            + "\n"
        )

    w("\n")
    rule("═")
    if show_costs and est.sites:
        section("COST SUMMARY")

        def row(label: str, value: str, code: str = "1;97") -> None:
            w(f"  {c(label.ljust(34), '2')} {c(value, code)}\n")

        row("Default model:", est.assumptions.model)
        row("Files scanned:", f"{len(analysis.files):,}")
        row("Files with LLM calls:", f"{len({s.path for s in analysis.sites}):,}")
        row("LLM call sites:", f"{len(analysis.sites):,}")
        rule()
        for d in est.depths:
            lo, hi = est.total(d, "low").cost, est.total(d, "high").cost
            row(
                f"Cost per run (N={d}):",
                f"{fmt_cost(lo)}  →  {fmt_cost(hi)}",
                "1;91" if hi > _SPEND_WARNING else "1;92",
            )
        a = est.assumptions
        w(
            c(
                f"\n  Assumes {a.system_tokens} system + {a.input_tokens} input tokens and {a.output_min}-{a.output_max}"
                f" output tokens per call; prices as of {est.prices_as_of}.",
                "2",
            )
            + "\n"
        )
        w("\n")
        rule("═")

    risky = sorted(
        findings_by_file.items(), key=lambda kv: (-max(SEVERITY_RANK[f.severity] for f in kv[1]), -len(kv[1]))
    )
    if risky:
        section("TOP RISK FILES", "1;91")
        for path, fs in risky[:5]:
            counts = ", ".join(
                f"{n} {sev}" for sev in ("high", "medium", "low") if (n := sum(1 for f in fs if f.severity == sev))
            )
            w(f"  {c(display_path(path), '1;91')}  ({counts})\n")
        w("\n")
        rule("═")
        section("RECOMMENDATIONS", "1;96")
        seen = sorted({f.rule for f in analysis.findings}, key=lambda r: (-SEVERITY_RANK[RULES[r].severity], r))
        for i, rid in enumerate(seen, 1):
            w(c(f"  {i}. [{rid}] {RULES[rid].fix}", "96") + "\n")
        w("\n")
        rule("═")
    else:
        w("\n" + c("  ✓ No cost risks found.", "1;92") + "\n\n")
        rule("═")

    n = len(analysis.findings)
    high = sum(1 for f in analysis.findings if f.severity == "high")
    w(
        c(f"  {n} finding(s), {high} high, in {len(analysis.files):,} file(s)", "1;91" if high else "1;92")
        + c("   ·   agentguard --list-rules for details", "2")
        + "\n\n"
    )


# ─── JSON ─────────────────────────────────────────────────────────────────────


def _usage(u) -> Dict[str, float]:
    return {
        "calls": round(u.calls, 2),
        "input_tokens": round(u.input),
        "output_tokens": round(u.output),
        "cached_input_tokens": round(u.cached),
        "cost_usd": round(u.cost, 6),
    }


def build_json(analysis: ProjectAnalysis, est: Estimate) -> Dict[str, Any]:
    a = est.assumptions
    return {
        "schema_version": 1,
        "tool": {"name": "agentguard", "version": __version__},
        "summary": {
            "files": len(analysis.files),
            "call_sites": len(analysis.sites),
            "findings": len(analysis.findings),
            "by_severity": {s: sum(1 for f in analysis.findings if f.severity == s) for s in ("high", "medium", "low")},
        },
        "findings": [
            {
                "rule": f.rule,
                "name": f.name,
                "severity": f.severity,
                "path": display_path(f.path),
                "line": f.line,
                "column": f.col,
                "message": f.message,
                "fix": f.fix,
            }
            for f in analysis.findings
        ],
        "errors": [{"path": display_path(r.path), "error": r.error} for r in analysis.files if r.error],
        "estimate": {
            "assumptions": {
                "system_tokens": a.system_tokens,
                "input_tokens": a.input_tokens,
                "output_tokens": [a.output_min, a.output_max],
                "depths": list(a.depths),
                "default_model": a.model,
                "prices_as_of": est.prices_as_of,
            },
            "totals": {
                str(d): {"low": _usage(est.total(d, "low")), "high": _usage(est.total(d, "high"))} for d in est.depths
            },
            "sites": [
                {
                    "path": display_path(s.site.path),
                    "line": s.site.line,
                    "api": s.site.api,
                    "calls": s.site.target.split(":", 1)[1] if s.site.target else None,
                    "model": s.model,
                    "model_assumed": s.model_assumed,
                    "loops": [{"line": lp.line, "kind": lp.kind, "count": lp.count} for lp in s.site.loops],
                    "context_growth": s.site.context_growth,
                    "cost": {
                        str(d): {"low": round(s.low[d].cost, 6), "high": round(s.high[d].cost, 6)} for d in est.depths
                    },
                }
                for s in est.sites
            ],
            "unknown_models": sorted(est.unknown_models),
        },
    }


# ─── SARIF 2.1.0 ──────────────────────────────────────────────────────────────


def build_sarif(analysis: ProjectAnalysis) -> Dict[str, Any]:
    rule_ids = list(RULES)

    def result(f: Finding) -> Dict[str, Any]:
        region = {"startLine": f.line, "startColumn": f.col}
        if f.end_line:
            region.update(endLine=f.end_line, endColumn=max(f.end_col, 1))
        return {
            "ruleId": f.rule,
            "ruleIndex": rule_ids.index(f.rule),
            "level": SARIF_LEVEL[f.severity],
            "message": {"text": f"{f.message}. {f.fix}"},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": display_path(f.path)},
                        "region": region,
                    }
                }
            ],
            "partialFingerprints": {"agentguard/v1": f"{f.rule}:{display_path(f.path)}:{f.message}"},
        }

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "AgentGuard",
                        "version": __version__,
                        "informationUri": REPO_URL,
                        "rules": [
                            {
                                "id": r.id,
                                "name": r.name,
                                "shortDescription": {"text": r.summary},
                                "fullDescription": {"text": f"{r.summary} {r.fix}"},
                                "help": {"text": r.fix, "markdown": f"**{r.summary}**\n\n{r.fix}"},
                                "helpUri": f"{REPO_URL}/blob/main/docs/rules.md#{r.id.lower()}",
                                "defaultConfiguration": {"level": SARIF_LEVEL[r.severity]},
                                "properties": {
                                    "tags": ["cost", "llm"],
                                    "security-severity": {"high": "7.0", "medium": "5.0", "low": "2.0"}[r.severity],
                                },
                            }
                            for r in RULES.values()
                        ],
                    }
                },
                "results": [result(f) for f in analysis.findings],
            }
        ],
    }


# ─── Markdown (PR comments / GitHub job summary) ──────────────────────────────


def build_markdown(analysis: ProjectAnalysis, est: Estimate) -> str:
    f = analysis.findings
    icon = {"high": "🔴", "medium": "🟠", "low": "🔵"}
    lines = ["## AgentGuard", ""]
    if f:
        lines += ["| | Rule | Location | Finding |", "|---|---|---|---|"]
        for x in sorted(f, key=lambda x: -SEVERITY_RANK[x.severity]):
            lines.append(f"| {icon[x.severity]} | `{x.rule}` | `{display_path(x.path)}:{x.line}` | {x.message} |")
    else:
        lines.append("No cost-risk findings.")
    if est.sites:
        lines += ["", "### Estimated cost per run", "", "| Loop iterations (N) | Low | High |", "|---|---|---|"]
        for d in est.depths:
            lines.append(f"| {d} | {fmt_cost(est.total(d, 'low').cost)} | {fmt_cost(est.total(d, 'high').cost)} |")
        a = est.assumptions
        lines += [
            "",
            f"<sub>{len(analysis.sites)} call sites. Assumes {a.system_tokens}+{a.input_tokens} input / "
            f"{a.output_min}-{a.output_max} output tokens per call, default model `{a.model}`, "
            f"prices as of {est.prices_as_of}. Loops with a constant bound use it.</sub>",
        ]
    return "\n".join(lines) + "\n"


def render(
    fmt: str,
    analysis: ProjectAnalysis,
    est: Estimate,
    out: TextIO = sys.stdout,
    color: bool = False,
    show_costs: bool = True,
    pretty: bool = False,
) -> None:
    if fmt == "text" and pretty:
        render_pretty(analysis, est, out, color, show_costs)
    elif fmt == "text":
        render_text(analysis, est, out, color, show_costs)
    elif fmt == "json":
        out.write(json.dumps(build_json(analysis, est), indent=2) + "\n")
    elif fmt == "sarif":
        out.write(json.dumps(build_sarif(analysis), indent=2) + "\n")
    elif fmt == "markdown":
        out.write(build_markdown(analysis, est))
    else:
        raise ValueError(f"unknown format {fmt!r}")
