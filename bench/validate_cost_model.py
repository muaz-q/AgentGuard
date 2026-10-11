"""Check AgentGuard's token model against a real agent run.

1. Run AgentGuard on bench/ollama_agent.py and check it finds the growing-history loop.
2. Run that agent for TURNS turns on a local Ollama model, recording the input/output
   tokens Ollama reports for every call.
3. Calibrate the per-call sizes (system S, new input U) from the first two turns only,
   then predict the cumulative input tokens for every later turn count with AgentGuard's
   estimator, and compare with what was measured. The naive estimate - turn-1 prompt size
   times the number of calls, which is what you get without modelling history growth -
   is reported alongside.

Usage: python bench/validate_cost_model.py [--model llama3.2] [--turns 40]
Writes bench/results/cost_model_validation.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ollama_agent import run  # noqa: E402

from agentguard.analyzer import analyze_project  # noqa: E402
from agentguard.estimator import Assumptions, estimate  # noqa: E402
from agentguard.pricing import PriceTable  # noqa: E402

QUESTIONS = [
    "What happens next? One sentence.",
    "Describe the setting in detail, including the weather, the sounds and what the main character notices first.",
    "Who appears now?",
    "Write the next scene as a short dialogue between two characters, with at least four lines each.",
    "What is the main character afraid of, and why? Answer in two or three sentences.",
]
CONFIGS = [
    # Every reply hits the output cap and user turns are the same length: sizes are constant.
    {"max_tokens": 64, "topic": "a lighthouse keeper"},
    {"max_tokens": 128, "topic": "a robot learning to paint"},
    # Realistic: user turns of different lengths, replies that end on their own.
    {"max_tokens": 400, "topic": "a night market", "questions": QUESTIONS},
]


def check_detection() -> None:
    analysis = analyze_project([HERE / "ollama_agent.py"], HERE)
    (site,) = analysis.sites
    assert site.api == "ollama" and site.context_growth, site
    assert [f.rule for f in analysis.findings] == ["AG002"], analysis.findings
    print(f"detected: {site.api} call at line {site.line}, history growth -> AG002")


def predict(input_per_call: int, system: int, output: int, n: int) -> float:
    analysis = analyze_project([HERE / "ollama_agent.py"], HERE)
    a = Assumptions(
        system_tokens=system, input_tokens=input_per_call, output_min=output, output_max=output, depths=(n,)
    )
    return estimate(analysis, PriceTable.bundled(), a).total(n, "low").input


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3.2")
    ap.add_argument("--turns", type=int, default=40)
    args = ap.parse_args()

    check_detection()
    results = []
    for cfg in CONFIGS:
        t0 = time.time()
        usage = run(args.model, args.turns, cfg["max_tokens"], cfg["topic"], cfg.get("questions"))
        print(f"ran {args.turns} turns, max_tokens={cfg['max_tokens']} in {time.time() - t0:.0f}s")

        p1, p2, o1 = usage[0]["input"], usage[1]["input"], usage[0]["output"]
        u = p2 - p1 - o1  # new input per turn, including chat-template overhead
        s = p1 - u
        o = round(sum(x["output"] for x in usage[:2]) / 2)

        rows = []
        measured = 0
        for n in range(1, args.turns + 1):
            measured += usage[n - 1]["input"]
            pred = predict(u, s, o, n)
            naive = p1 * n
            rows.append(
                {
                    "turns": n,
                    "measured_input": measured,
                    "predicted_input": round(pred),
                    "naive_input": naive,
                    "error_pct": round(100 * (pred - measured) / measured, 2),
                    "naive_error_pct": round(100 * (naive - measured) / measured, 2),
                }
            )
        results.append(
            {
                "config": {k: v for k, v in cfg.items() if k != "questions"},
                "varied": "questions" in cfg,
                "calibration": {"system": s, "input": u, "output": o},
                "outputs": [x["output"] for x in usage],
                "rows": rows,
            }
        )
        for n in sorted({n for n in (10, 20, args.turns) if n <= args.turns}):
            r = rows[n - 1]
            print(
                f"  n={n:<3} measured {r['measured_input']:>7,}  agentguard {r['predicted_input']:>7,} "
                f"({r['error_pct']:+.1f}%)  naive {r['naive_input']:>6,} ({r['naive_error_pct']:+.1f}%)"
            )

    out = HERE / "results" / "cost_model_validation.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"model": args.model, "turns": args.turns, "runs": results}, indent=2) + "\n")
    print(f"wrote {out.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
