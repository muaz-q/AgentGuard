"""Recall against a syntactic baseline: of the calls that are unmistakably direct SDK calls
(by the shape of the call expression), how many does AgentGuard report as call sites?

This is a lower bar than true recall - it cannot see calls through wrappers or frameworks -
but it catches detection gaps such as re-exported modules and unusual client setups.

Usage: python bench/pattern_recall.py   (after real_world.py has cloned the projects)
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from real_world import EXCLUDE, HOLDOUT, REPOS_DIR, TUNING

from agentguard.analyzer import analyze_project
from agentguard.crawler import crawl

SUFFIXES = (
    "chat.completions.create",
    "chat.completions.parse",
    "responses.create",
    "messages.create",
    "messages.stream",
    "litellm.completion",
    "litellm.acompletion",
    "generate_content",
)


def baseline(files):
    hits = set()
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8-sig", errors="replace"))
        except (SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                try:
                    text = ast.unparse(node.func)
                except Exception:
                    continue
                parts = text.split(".")
                if any(parts[-len(sfx.split(".")) :] == sfx.split(".") for sfx in SUFFIXES) and "batches" not in parts:
                    hits.add((f.resolve(), node.lineno))
    return hits


def main() -> None:
    rows, all_missed = [], []
    for set_name, repos in (("tuning", TUNING), ("holdout", HOLDOUT)):
        for repo, _sha in repos:
            root = REPOS_DIR / repo.replace("/", "_")
            files = crawl([str(root)], exclude=EXCLUDE)
            expected = baseline(files)
            found = {(s.path.resolve(), s.line) for s in analyze_project(files, root).sites}
            missed = sorted(expected - found)
            rows.append(
                {"set": set_name, "repo": repo, "baseline": len(expected), "found": len(expected) - len(missed)}
            )
            all_missed += [f"{repo}: {p.relative_to(root.resolve()).as_posix()}:{line}" for p, line in missed]
            print(f"{set_name:<8} {repo:<36} {len(expected) - len(missed):>4}/{len(expected):<4}")
    total = sum(r["baseline"] for r in rows)
    found = sum(r["found"] for r in rows)
    print(f"total {found}/{total}")
    for m in all_missed:
        print("  missed", m)
    out = Path(__file__).resolve().parent / "results" / "pattern_recall.json"
    out.write_text(json.dumps({"suffixes": SUFFIXES, "repos": rows, "missed": all_missed}, indent=2) + "\n")


if __name__ == "__main__":
    main()
