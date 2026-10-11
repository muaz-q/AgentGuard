"""The rules AgentGuard checks, with their default severity and remediation text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

SEVERITIES = ("high", "medium", "low")
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    severity: str
    summary: str
    fix: str


RULES: Dict[str, Rule] = {
    r.id: r
    for r in [
        Rule(
            "AG001",
            "llm-call-in-unbounded-loop",
            "high",
            "LLM call inside a loop with no detectable iteration cap.",
            "Bound the loop with a step counter (e.g. `for step in range(MAX_STEPS)`) "
            "or an explicit `if step >= MAX_STEPS: break`.",
        ),
        Rule(
            "AG002",
            "unbounded-context-growth",
            "high",
            "Conversation history grows every iteration and is re-sent on every call, "
            "so input tokens grow quadratically with the number of turns.",
            "Keep a sliding window (`messages[-k:]`), summarise old turns, or use "
            "server-side compaction/context editing where the provider offers it.",
        ),
        Rule(
            "AG003",
            "llm-call-in-nested-loop",
            "medium",
            "LLM call inside nested loops; the call count is the product of the loop sizes.",
            "Flatten the work into one batch, or cap the inner loop.",
        ),
        Rule(
            "AG004",
            "llm-call-per-item",
            "low",
            "One LLM call per item of a collection; cost scales with the input size.",
            "If results are not needed immediately, the OpenAI and Anthropic Batch APIs "
            "bill at 50%; otherwise process several items per call.",
        ),
        Rule(
            "AG005",
            "unbounded-llm-recursion",
            "high",
            "Function that makes LLM calls calls itself with no depth parameter.",
            "Thread a `depth` argument through the recursion and stop at a fixed maximum.",
        ),
        Rule(
            "AG006",
            "missing-max-tokens",
            "low",
            "LLM call sets no output-token cap, so a single response can be as long as the model allows.",
            "Pass `max_tokens` / `max_completion_tokens` / `max_output_tokens`.",
        ),
        Rule(
            "AG007",
            "uncached-large-prompt-in-loop",
            "medium",
            "A large static prompt is re-sent on every loop iteration to Anthropic without prompt caching.",
            "Mark the static prefix with `cache_control` - cached reads bill at about 10% of the input price.",
        ),
    ]
}
