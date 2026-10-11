"""Reporter — renders the AgentGuard analysis as CLI output and JSON."""

import json
import sys
from pathlib import Path
from typing import Optional

from agentguard.simulator import ProjectCost, FileCost, DEPTH_LEVELS

# ─── ANSI colors ──────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[91m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
MAGENTA= "\033[95m"
WHITE  = "\033[97m"

def _c(text, *codes):
    """Apply ANSI codes if stdout is a tty."""
    if not sys.stdout.isatty():
        return str(text)
    return "".join(codes) + str(text) + RESET

def _fmt_cost(cost: float) -> str:
    if cost == 0:
        return "$0.00"
    if cost < 0.001:
        return f"${cost:.6f}"
    if cost < 1:
        return f"${cost:.4f}"
    return f"${cost:.2f}"

def _risk_label(flags) -> str:
    if not flags:
        return _c("✓ LOW", GREEN, BOLD)
    if len(flags) >= 3 or any("context" in f.lower() or "quadratic" in f.lower() for f in flags):
        return _c("⚠ CRITICAL", RED, BOLD)
    return _c("⚡ MEDIUM", YELLOW, BOLD)

BANNER = r"""
    ___                    __  ______                     __
   /   | ____ ____  ____  / /_/ ____/_  ______ __________/ /
  / /| |/ __ `/ _ \/ __ \/ __/ / __/ / / / __ `/ ___/ __  /
 / ___ / /_/ /  __/ / / / /_/ /_/ / /_/ / /_/ / /  / /_/ /
/_/  |_\__, /\___/_/ /_/\__/\____/\__,_/\__,_/_/   \__,_/
       /____/
"""

def _separator(char="─", width=72):
    return _c(char * width, DIM)

def _header(title: str, width=72):
    pad = (width - len(title) - 4) // 2
    return _c("┌" + "─"*pad + "  " + title + "  " + "─"*pad + "┐", CYAN)


# ─── File-level report ────────────────────────────────────────────────────────

def _render_file(fc: FileCost, rel_root: Optional[str] = None) -> str:
    lines = []
    path_str = str(fc.path)
    if rel_root:
        try:
            path_str = str(Path(fc.path).relative_to(rel_root))
        except ValueError:
            pass

    lang_badge = {"python": "🐍 py", "javascript": "🟨 js", "typescript": "🔷 ts"}.get(fc.language, fc.language)

    lines.append("")
    lines.append(_c(f"  {path_str}", BOLD, WHITE) + f"  [{lang_badge}]")

    if fc.errors:
        for e in fc.errors:
            lines.append(_c(f"    ⚠ Parse error: {e}", YELLOW))

    if fc.api_calls == 0:
        lines.append(_c("    No LLM API calls detected", DIM))
        return "\n".join(lines)

    lines.append(f"    Calls: {_c(fc.api_calls, CYAN, BOLD)}  •  Loops: {_c(fc.loop_count, CYAN)}  •  Risk: {_risk_label(fc.risk_flags)}")

    if fc.depth_costs:
        lines.append("")
        lines.append(_c("    Loop Depth Simulation:", DIM))
        for dc in fc.depth_costs:
            bk = _c(" ⚠️  BANKRUPTCY RISK", RED, BOLD) if dc.bankruptcy_risk else ""
            depth_str = _c(f"N={dc.depth:>3}", MAGENTA)
            cost_str = f"{_c(_fmt_cost(dc.cost_min), GREEN)} → {_c(_fmt_cost(dc.cost_max), RED)}"
            calls_str = _c(f"({dc.total_calls} calls)", DIM)
            lines.append(f"      {depth_str}  {cost_str}  {calls_str}{bk}")

    if fc.risk_flags:
        lines.append("")
        lines.append(_c("    Risk Flags:", YELLOW, BOLD))
        for flag in fc.risk_flags:
            lines.append(_c(f"    ⚡ {flag}", YELLOW))

    if fc.optimization_tips:
        lines.append("")
        lines.append(_c("    Optimizations:", GREEN, BOLD))
        for tip in fc.optimization_tips:
            lines.append(_c(f"    → {tip}", GREEN))

    return "\n".join(lines)


# ─── Project summary ──────────────────────────────────────────────────────────

def _render_summary(pc: ProjectCost) -> str:
    lines = []
    lines.append("")
    lines.append(_c("  COST SUMMARY", BOLD, WHITE))
    lines.append(_separator())

    def row(label, value, color=WHITE):
        lines.append(f"  {_c(label, DIM):<40} {_c(value, color, BOLD)}")

    row("Model:", pc.model)
    row("Files scanned:", str(pc.total_files))
    row("Files with LLM activity:", str(pc.analyzed_files))
    lines.append(_separator())

    row("Total Cost Range (N=1 → N=100):",
        f"{_fmt_cost(pc.total_min)}  →  {_fmt_cost(pc.total_max)}")
    row("Upper Bound (worst case, no opt):", _fmt_cost(pc.upper_bound_naive), RED)
    row("Optimized Estimate (w/ caching):", _fmt_cost(pc.optimized_estimate), GREEN)
    row("Savings Alpha:", f"{_fmt_cost(pc.savings_alpha)} ({int(pc.savings_alpha / max(pc.upper_bound_naive, 0.0001) * 100)}%)", CYAN)

    return "\n".join(lines)


# ─── Risk summary ─────────────────────────────────────────────────────────────

def _render_risks(pc: ProjectCost) -> str:
    risk_files = [fc for fc in pc.file_costs if fc.risk_flags]
    if not risk_files:
        return _c("\n  ✓ No high-risk files detected.", GREEN, BOLD)

    lines = []
    lines.append("")
    lines.append(_c("  TOP RISK FILES", BOLD, RED))
    lines.append(_separator())

    for fc in sorted(risk_files, key=lambda f: -len(f.risk_flags))[:10]:
        path_str = Path(fc.path).name
        lines.append(f"\n  {_c(path_str, BOLD, RED)}  ({len(fc.risk_flags)} risk flags)")
        for flag in fc.risk_flags:
            lines.append(_c(f"    ⚡ {flag}", YELLOW))

    return "\n".join(lines)


# ─── Recommendations ─────────────────────────────────────────────────────────

def _render_recommendations(pc: ProjectCost) -> str:
    # Deduplicate tips across all files
    seen = set()
    all_tips = []
    for fc in pc.file_costs:
        for tip in fc.optimization_tips:
            if tip not in seen and "No critical" not in tip:
                seen.add(tip)
                all_tips.append(tip)

    if not all_tips:
        return ""

    lines = []
    lines.append("")
    lines.append(_c("  RECOMMENDATIONS", BOLD, CYAN))
    lines.append(_separator())
    for i, tip in enumerate(all_tips, 1):
        lines.append(_c(f"  {i}. {tip}", CYAN))
    return "\n".join(lines)


# ─── DAG (Mermaid) ───────────────────────────────────────────────────────────

def build_mermaid_dag(pc: ProjectCost) -> str:
    lines = ["graph TD"]
    lines.append('    Project["🛡 AgentGuard Project"]')
    for i, fc in enumerate(fc for fc in pc.file_costs if fc.api_calls > 0):
        name = Path(fc.path).name.replace(".", "_").replace("-", "_")
        node_id = f"F{i}_{name}"
        label = f"{Path(fc.path).name}\\n{fc.api_calls} calls"
        if fc.risk_flags:
            lines.append(f'    {node_id}["{label}"] --> Risk_{i}["⚡ {len(fc.risk_flags)} risks"]')
            lines.append(f"    Project --> {node_id}")
        else:
            lines.append(f'    Project --> {node_id}["{label}"]')
    return "\n".join(lines)


# ─── JSON output ─────────────────────────────────────────────────────────────

def build_json(pc: ProjectCost) -> dict:
    return {
        "model": pc.model,
        "summary": {
            "total_files": pc.total_files,
            "analyzed_files": pc.analyzed_files,
            "cost_min": round(pc.total_min, 6),
            "cost_max": round(pc.total_max, 6),
            "upper_bound_naive": round(pc.upper_bound_naive, 6),
            "optimized_estimate": round(pc.optimized_estimate, 6),
            "savings_alpha": round(pc.savings_alpha, 6),
        },
        "files": [
            {
                "path": fc.path,
                "language": fc.language,
                "api_calls": fc.api_calls,
                "loop_count": fc.loop_count,
                "caching_eligible": fc.caching_eligible,
                "high_complexity": fc.high_complexity,
                "risk_flags": fc.risk_flags,
                "optimization_tips": fc.optimization_tips,
                "depth_costs": [
                    {
                        "depth": dc.depth,
                        "cost_min": round(dc.cost_min, 6),
                        "cost_avg": round(dc.cost_avg, 6),
                        "cost_max": round(dc.cost_max, 6),
                        "total_calls": dc.total_calls,
                        "bankruptcy_risk": dc.bankruptcy_risk,
                    }
                    for dc in fc.depth_costs
                ],
                "errors": fc.errors,
            }
            for fc in pc.file_costs
        ],
        "mermaid_dag": build_mermaid_dag(pc),
    }


# ─── Master render ────────────────────────────────────────────────────────────

def render(
    pc: ProjectCost,
    root_dir: Optional[str] = None,
    json_output: bool = False,
    json_path: Optional[str] = None,
    show_dag: bool = False,
    quiet: bool = False,
) -> None:
    if json_output:
        payload = build_json(pc)
        out = json.dumps(payload, indent=2)
        if json_path:
            Path(json_path).write_text(out)
            print(f"JSON saved to: {json_path}")
        else:
            print(out)
        return

    # Human-readable
    print(_c(BANNER, CYAN, BOLD))
    print(_c("  Pre-execution Cost Estimator for Agentic AI Systems", DIM))
    print(_separator("═"))

    if not quiet:
        # Per-file breakdown
        print(_c("\n  FILE ANALYSIS", BOLD, WHITE))
        print(_separator())
        active = [fc for fc in pc.file_costs if fc.api_calls > 0]
        if active:
            for fc in active:
                print(_render_file(fc, rel_root=root_dir))
        else:
            print(_c("\n  No LLM API calls detected in any file.", DIM))

    print("\n" + _separator("═"))
    print(_render_summary(pc))
    print("\n" + _separator("═"))
    print(_render_risks(pc))
    print("\n" + _separator("═"))
    print(_render_recommendations(pc))

    if show_dag:
        print("\n" + _separator("═"))
        print(_c("\n  DEPENDENCY DAG (Mermaid)\n", BOLD, MAGENTA))
        print(build_mermaid_dag(pc))

    if json_path:
        payload = build_json(pc)
        Path(json_path).write_text(json.dumps(payload, indent=2))
        print(_c(f"\n  📄 JSON report saved → {json_path}", GREEN))

    print("\n" + _separator("═") + "\n")