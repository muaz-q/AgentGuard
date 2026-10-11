"""Run AgentGuard over well-known open-source agent projects at pinned commits.

Two sets: TUNING was hand-reviewed while developing the rules (false positives found
there were fixed), so its precision is optimistic. HOLDOUT was only looked at after the
rules were frozen, so its precision is the honest estimate.

Usage: python bench/real_world.py --set {tuning,holdout} [--sample N]
Clones into bench/.repos (git-ignored), writes bench/results/<set>.json, and with --sample
writes up to N findings per rule to bench/results/<set>_review.md for hand review.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import time
from collections import Counter
from pathlib import Path

from agentguard.analyzer import analyze_project
from agentguard.crawler import crawl

HERE = Path(__file__).resolve().parent
REPOS_DIR = HERE / ".repos"
# Test suites are excluded: they call mocks, not models.
EXCLUDE = ["tests", "test", "*/tests", "*/test", "*/tests/*", "*/test/*", "*_test.py", "test_*.py", "*/test_*.py"]

TUNING = [
    ("Aider-AI/aider", "5dc9490bb35f9729ef2c95d00a19ccd30c26339c"),
    ("AntonOsika/gpt-engineer", "a90fcd543eedcc0ff2c34561bc0785d2ba83c47e"),
    ("OpenInterpreter/open-interpreter", "ac1fcc8fe57aba51fcc3c79afd57a0883237fe87"),
    ("SWE-agent/SWE-agent", "3ea751c087f32b16e039a2233dd6eefecef325d5"),
    ("TransformerOptimus/SuperAGI", "c3c1982e7bd6a11cfed53c5a193ea502f924b1b6"),
    ("assafelovic/gpt-researcher", "3582a6841fe7dc801e2a34e34ee408641aea9bce"),
    ("crewAIInc/crewAI", "6b93fa0e25a926215ca7bb52a95d4db7d9d7262d"),
    ("geekan/MetaGPT", "11cdf466d042aece04fc6cfd13b28e1a70341b1f"),
    ("huggingface/smolagents", "96f33faaf028479119ec8d34507b47694cf14e34"),
    ("langchain-ai/open_deep_research", "1b7d2e80db9faa586165c60e09096dbbfd483a64"),
    ("openai/openai-agents-python", "125efa029b4bfd84238bd2c4fd69c3406f802663"),
    ("openai/swarm", "6af0b4caf37dca4526dfd98e9fbd8ce36e7eeb22"),
    ("stanfordnlp/dspy", "f1260ff14610286cb295c7d3a5ee2cbfd0ba5cb9"),
    ("yoheinakajima/babyagi", "fa8930ebe72a82e5ad57b356e7cbec96290e5bb2"),
]

HOLDOUT = [
    ("browser-use/browser-use", "c75e8476e26d18b7617643bc2ae082fae8eae431"),
    ("qodo-ai/pr-agent", "cf76f708a1ac58cc8d0e26dde26fa53cc4b8819e"),
    ("mem0ai/mem0", "b7ad69afda6b6ed030347c66d48a13e4de9dec08"),
    ("camel-ai/camel", "24fde60ad739b4be8f8f533fea9ba54256fbc4a2"),
    ("Significant-Gravitas/AutoGPT", "4473fbbcb1951471df0a05374d47c93c4e39bea6"),
    ("khoj-ai/khoj", "ae229ca894c0b80ad84664afcfdde523b5e87057"),
    ("pydantic/pydantic-ai", "69ea1e57201ed59e7d30fbe4a7590d193acecce0"),
    ("microsoft/TaskWeaver", "d44ddef23f90059fb17999d3095db4240e98f955"),
]


def checkout(repo: str, sha: str) -> Path:
    dest = REPOS_DIR / repo.replace("/", "_")
    if not dest.exists():
        subprocess.run(
            ["git", "clone", "-q", "--filter=blob:none", f"https://github.com/{repo}.git", str(dest)], check=True
        )
    head = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != sha:
        subprocess.run(["git", "-C", str(dest), "fetch", "-q", "--depth", "1", "origin", sha], check=True)
        subprocess.run(["git", "-C", str(dest), "checkout", "-q", sha], check=True)
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["tuning", "holdout"], required=True)
    ap.add_argument("--sample", type=int, default=0, help="findings per rule to sample for hand review")
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    rows, all_findings = [], []
    for repo, sha in TUNING if args.set == "tuning" else HOLDOUT:
        root = checkout(repo, sha)
        t0 = time.perf_counter()
        files = crawl([str(root)], exclude=EXCLUDE)
        analysis = analyze_project(files, root)
        secs = time.perf_counter() - t0
        lines = sum(len(f.read_bytes().splitlines()) for f in files)
        by_rule = Counter(f.rule for f in analysis.findings)
        rows.append(
            {
                "repo": repo,
                "commit": sha,
                "files": len(files),
                "lines": lines,
                "parse_errors": sum(1 for f in analysis.files if f.error),
                "call_sites": len(analysis.sites),
                "indirect_sites": sum(1 for s in analysis.sites if s.target),
                "findings": dict(sorted(by_rule.items())),
                "seconds": round(secs, 2),
            }
        )
        for f in analysis.findings:
            all_findings.append((repo, sha, root, f))
        print(
            f"{repo:<36} {len(files):>5} files {lines:>8,} lines {len(analysis.sites):>4} sites "
            f"{sum(by_rule.values()):>4} findings  {secs:5.1f}s  {dict(sorted(by_rule.items()))}"
        )

    total_lines = sum(r["lines"] for r in rows)
    total_secs = sum(r["seconds"] for r in rows)
    print(
        f"total: {sum(r['files'] for r in rows):,} files, {total_lines:,} lines in {total_secs:.1f}s "
        f"({total_lines / total_secs:,.0f} lines/s)"
    )

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / f"{args.set}.json").write_text(json.dumps({"set": args.set, "repos": rows}, indent=2) + "\n")

    if args.sample:
        rng = random.Random(args.seed)
        by_rule = {}
        for item in all_findings:
            by_rule.setdefault(item[3].rule, []).append(item)
        md = [
            f"# {args.set} set: findings for hand review",
            "",
            f"Seed {args.seed}; up to {args.sample} per rule. Verdicts are recorded in labels.csv.",
            "",
        ]
        for rule in sorted(by_rule):
            items = by_rule[rule]
            for repo, sha, root, f in rng.sample(items, min(args.sample, len(items))):
                rel = f.path.relative_to(root).as_posix()
                src = f.path.read_text(encoding="utf-8", errors="replace").splitlines()
                lo, hi = max(0, f.line - 25), min(len(src), f.line + 8)
                snippet = "\n".join(f"{i + 1:>5}{'>' if i + 1 == f.line else ' '} {src[i]}" for i in range(lo, hi))
                md += [
                    f"## {rule} {repo} {rel}:{f.line}",
                    "",
                    f"https://github.com/{repo}/blob/{sha}/{rel}#L{f.line}",
                    "",
                    f"> {f.message}",
                    "",
                    "```python",
                    snippet,
                    "```",
                    "",
                ]
        (out / f"{args.set}_review.md").write_text("\n".join(md), encoding="utf-8")
        print(f"wrote {sum(min(args.sample, len(v)) for v in by_rule.values())} sampled findings")


if __name__ == "__main__":
    main()
