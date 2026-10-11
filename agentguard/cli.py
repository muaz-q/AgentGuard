#!/usr/bin/env python3
"""
AgentGuard CLI — Pre-execution cost estimator for agentic AI systems.

Usage:
    agentguard
    agentguard .
    agentguard ./my_project
    agentguard --root_dir ./my_project
    agentguard --model claude-3-5-sonnet
    agentguard --json --json_out report.json
    agentguard --input_tokens 400 --output_min 200 --output_max 800
"""

import argparse
import sys
import time
from pathlib import Path

from agentguard.crawler import crawl
from agentguard.analyzer import analyze
from agentguard.simulator import simulate, MODEL_PRICES, DEFAULT_MODEL
from agentguard.reporter import render


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agentguard",
        description="AgentGuard — Pre-execution cost estimator for agentic AI systems",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  agentguard
  agentguard .
  agentguard ./my_agent
  agentguard --root_dir ./my_agent
  agentguard --model claude-3-5-sonnet
  agentguard --json --json_out report.json
  agentguard --input_tokens 400 --output_min 200 --output_max 800 --dag
        """,
    )

    # ✅ Version support
    p.add_argument(
        "--version",
        action="version",
        version="agentguard 0.2.3"
    )

    # ✅ Positional root_dir (clean UX)
    p.add_argument(
        "root_dir",
        nargs="?",
        default=".",
        help="Project directory (default: current directory)",
    )

    # ✅ Backward compatibility flag (DO NOT BREAK EXISTING USERS)
    p.add_argument(
        "--root_dir",
        dest="root_dir_flag",
        help="Root directory of the project to analyze (overrides positional argument)",
    )

    p.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL,
        choices=list(MODEL_PRICES.keys()),
        help=f"LLM model for pricing (default: {DEFAULT_MODEL})",
    )

    p.add_argument(
        "--input_tokens", "-i",
        type=int,
        default=1200,
        help="Assumed input tokens per call (default: 200)",
    )

    p.add_argument(
        "--output_min",
        type=int,
        default=300,
        help="Minimum output tokens per call (default: 100)",
    )

    p.add_argument(
        "--output_max",
        type=int,
        default=3000,
        help="Maximum output tokens per call (default: 500)",
    )

    p.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of human-readable report",
    )

    p.add_argument(
        "--json_out",
        metavar="FILE",
        help="Save JSON report to file (can be combined with human-readable output)",
    )

    p.add_argument(
        "--dag",
        action="store_true",
        help="Include Mermaid DAG in output",
    )

    p.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Skip per-file details; show summary only",
    )

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    print("RUNNING MODIFIED AGENTGUARD 🚀")

    # ✅ Resolve correct root_dir (flag overrides positional)
    root_dir_input = args.root_dir_flag if args.root_dir_flag else args.root_dir
    root = Path(root_dir_input).resolve()

    if not root.exists():
        print(f"Error: Directory '{root_dir_input}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # ✅ Safe UX message (correctly detects current dir)
    if Path(root_dir_input).resolve() == Path(".").resolve() and not args.json:
        print("⚠️  No directory specified. Using current folder.\n")

    start = time.time()

    # 1. Crawl
    if not args.json:
        print(f"\n🔍  Scanning: {root}", flush=True)

    files = crawl(str(root))

    if not args.json:
        print(f"   Found {len(files)} candidate file(s)...", flush=True)

    # 2. Analyze
    analyses = []
    for f in files:
        analysis = analyze(f)
        analyses.append(analysis)
    for a in analyses:
        print(a.path.name, "context_growth =", a.context_growth)

    # 3. Simulate
    project_cost = simulate(
        analyses=analyses,
        model=args.model,
        input_tokens=args.input_tokens,
        output_tokens_min=args.output_min,
        output_tokens_max=args.output_max,
    )

    elapsed = time.time() - start

    if not args.json:
        print(f"   Analysis complete in {elapsed:.2f}s\n", flush=True)

    # 4. Report
    render(
        pc=project_cost,
        root_dir=str(root),
        json_output=args.json,
        json_path=args.json_out,
        show_dag=args.dag,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    main()