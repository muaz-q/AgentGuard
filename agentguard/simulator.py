"""
Simulation Engine — deterministic cost estimator.

NO real API calls. NO token measurement. Pure math.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from agentguard.analyzer import FileAnalysis


# ─── Model pricing (per 1M tokens, USD) ──────────────────────────────────────

MODEL_PRICES = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
}

DEFAULT_MODEL = "claude-3-opus"

DEPTH_LEVELS = [1, 5, 20, 100]

TOKENIZER_INFLATION = 1.35

REASONING_LOW = 1.2
REASONING_HIGH = 20.0

CACHE_DISCOUNT = 0.10

DEFAULT_INPUT_TOKENS = 750
DEFAULT_OUTPUT_MIN = 300
DEFAULT_OUTPUT_MAX = 3000
DEFAULT_SYSTEM_PROMPT_TOKENS = 800


@dataclass
class DepthCost:
    depth: int
    cost_min: float
    cost_avg: float
    cost_max: float
    total_calls: int
    total_tokens_min: int
    total_tokens_max: int
    bankruptcy_risk: bool = False


@dataclass
class FileCost:
    path: str
    language: str
    api_calls: int
    loop_count: int
    depth_costs: List[DepthCost] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    optimization_tips: List[str] = field(default_factory=list)
    caching_eligible: bool = False
    high_complexity: bool = False
    errors: List[str] = field(default_factory=list)

    @property
    def cost_min(self) -> float:
        return self.depth_costs[0].cost_min if self.depth_costs else 0.0

    @property
    def cost_max(self) -> float:
        return self.depth_costs[-1].cost_max if self.depth_costs else 0.0


@dataclass
class ProjectCost:
    total_files: int
    analyzed_files: int
    file_costs: List[FileCost] = field(default_factory=list)
    model: str = DEFAULT_MODEL

    @property
    def total_min(self) -> float:
        return sum(fc.cost_min for fc in self.file_costs)

    @property
    def total_max(self) -> float:
        return sum(fc.cost_max for fc in self.file_costs)

    @property
    def upper_bound_naive(self) -> float:
        return sum(
            (fc.depth_costs[-1].cost_max if fc.depth_costs else 0.0)
            for fc in self.file_costs
        )

    @property
    def optimized_estimate(self) -> float:
        total = 0.0
        for fc in self.file_costs:
            if not fc.depth_costs:
                continue
            worst = fc.depth_costs[-1].cost_max
            if fc.caching_eligible:
                worst *= CACHE_DISCOUNT + 0.3
            total += worst
        return total

    @property
    def savings_alpha(self) -> float:
        return max(0.0, self.upper_bound_naive - self.optimized_estimate)

    @property
    def risk_files(self) -> List[FileCost]:
        return [fc for fc in self.file_costs if fc.risk_flags]


# ─── Core simulation math ─────────────────────────────────────────────────────

def _quadratic_context_tokens(
    N: int,
    S: int = DEFAULT_SYSTEM_PROMPT_TOKENS,
    U: int = DEFAULT_INPUT_TOKENS,
    R: int = DEFAULT_OUTPUT_MIN,
) -> int:
    return int(N * S + U * (N * (N + 1) / 2) + R * (N * (N - 1) / 2))


def _reasoning_multiplier(analysis: FileAnalysis) -> float:
    if analysis.high_complexity:
        return REASONING_HIGH
    return REASONING_LOW


def _compute_depth_cost(
    analysis: FileAnalysis,
    depth: int,
    input_price_per_m: float,
    output_price_per_m: float,
    input_tokens_base: int,
    output_tokens_min: int,
    output_tokens_max: int,
) -> DepthCost:
    calls = max(analysis.api_calls, 1)
    reasoning = _reasoning_multiplier(analysis)

    if analysis.calls_in_loops > 0:
        loop_calls = analysis.calls_in_loops * depth
        non_loop_calls = calls - analysis.calls_in_loops
        total_calls = loop_calls + non_loop_calls
    else:
        total_calls = calls

    if analysis.calls_in_loops > 0 and analysis.context_growth and depth > 1:
        total_tokens_min = _quadratic_context_tokens(
            depth, DEFAULT_SYSTEM_PROMPT_TOKENS, input_tokens_base, output_tokens_min,
        )
        total_tokens_max = _quadratic_context_tokens(
            depth, DEFAULT_SYSTEM_PROMPT_TOKENS, input_tokens_base, output_tokens_max,
        )
        input_tokens_min = int(total_tokens_min * 0.6)
        input_tokens_max = int(total_tokens_max * 0.6)
        output_tokens_total_min = int(total_tokens_min * 0.4)
        output_tokens_total_max = int(total_tokens_max * 0.4)
    else:
        input_tokens_min = input_tokens_base * total_calls
        input_tokens_max = input_tokens_base * total_calls
        output_tokens_total_min = output_tokens_min * total_calls
        output_tokens_total_max = output_tokens_max * total_calls

    input_tokens_min = int(input_tokens_min * reasoning)
    input_tokens_max = int(input_tokens_max * reasoning)
    output_tokens_total_min = int(output_tokens_total_min * reasoning)
    output_tokens_total_max = int(output_tokens_total_max * reasoning)

    input_tokens_min = int(input_tokens_min * TOKENIZER_INFLATION)
    input_tokens_max = int(input_tokens_max * TOKENIZER_INFLATION)

    def cost(inp, out):
        return (inp / 1_000_000) * input_price_per_m + (out / 1_000_000) * output_price_per_m

    cost_min = cost(input_tokens_min, output_tokens_total_min)
    cost_max = cost(input_tokens_max, output_tokens_total_max)
    cost_avg = (cost_min + cost_max) / 2

    return DepthCost(
        depth=depth,
        cost_min=cost_min,
        cost_avg=cost_avg,
        cost_max=cost_max,
        total_calls=total_calls,
        total_tokens_min=input_tokens_min + output_tokens_total_min,
        total_tokens_max=input_tokens_max + output_tokens_total_max,
        bankruptcy_risk=cost_max > 10.0,
    )


# ─── Risk & optimization analysis ────────────────────────────────────────────

def _assess_risks(analysis: FileAnalysis) -> List[str]:
    flags = []
    if analysis.calls_in_loops > 0:
        flags.append("API calls inside loops — cost grows with loop depth")
    if analysis.nested_loops:
        flags.append("Nested loops detected — potential exponential cost growth")
    if analysis.recursion_risk:
        flags.append("No loop depth limiter found — unbounded execution risk")
    if analysis.context_growth:
        flags.append("Context growth detected — quadratic token explosion risk")
    if analysis.repeated_prompt_risk:
        flags.append("Repeated prompt patterns — caching opportunity missed")
    if analysis.large_static_prompt:
        flags.append("Large static prompt detected — high baseline token cost")
    if analysis.high_complexity:
        flags.append("High-complexity task (agent/code/math) — reasoning tax ×20 applied")
    return flags


def _optimization_tips(analysis: FileAnalysis, depth_costs: List[DepthCost]) -> List[str]:
    tips = []
    if analysis.repeated_prompt_risk or analysis.large_static_prompt:
        tips.append("Enable prompt caching (90% input cost discount for prompts >1024 tokens)")
    if analysis.calls_in_loops > 0:
        tips.append("Add max_iterations/max_steps guard to bound loop depth")
    if analysis.context_growth:
        tips.append("Truncate or summarize message history to prevent quadratic context growth")
    if any(dc.bankruptcy_risk for dc in depth_costs):
        tips.append("Consider model downgrade: frontier → flash/haiku (10-20× cheaper)")
    if analysis.nested_loops:
        tips.append("Refactor nested loops into batch/parallel calls")
    if not tips:
        tips.append("No critical optimizations required for this file")
    return tips


# ─── Main simulation entry point ──────────────────────────────────────────────

def simulate(
    analyses: List[FileAnalysis],
    model: str = DEFAULT_MODEL,
    input_tokens: int = DEFAULT_INPUT_TOKENS,
    output_tokens_min: int = DEFAULT_OUTPUT_MIN,
    output_tokens_max: int = DEFAULT_OUTPUT_MAX,
) -> ProjectCost:
    pricing = MODEL_PRICES.get(model, MODEL_PRICES[DEFAULT_MODEL])
    input_price = pricing["input"]
    output_price = pricing["output"]

    file_costs = []
    for analysis in analyses:
        if analysis.api_calls == 0 and analysis.calls_in_loops == 0:
            fc = FileCost(
                path=str(analysis.path),
                language=analysis.language,
                api_calls=0,
                loop_count=analysis.loop_count,
                errors=analysis.errors,
            )
            file_costs.append(fc)
            continue

        depth_costs = [
            _compute_depth_cost(
                analysis=analysis,
                depth=d,
                input_price_per_m=input_price,
                output_price_per_m=output_price,
                input_tokens_base=input_tokens,
                output_tokens_min=output_tokens_min,
                output_tokens_max=output_tokens_max,
            )
            for d in DEPTH_LEVELS
        ]

        risk_flags = _assess_risks(analysis)
        tips = _optimization_tips(analysis, depth_costs)
        caching_eligible = analysis.repeated_prompt_risk or analysis.large_static_prompt or input_tokens > 1024

        fc = FileCost(
            path=str(analysis.path),
            language=analysis.language,
            api_calls=analysis.api_calls,
            loop_count=analysis.loop_count,
            depth_costs=depth_costs,
            risk_flags=risk_flags,
            optimization_tips=tips,
            caching_eligible=caching_eligible,
            high_complexity=analysis.high_complexity,
            errors=analysis.errors,
        )
        file_costs.append(fc)

    return ProjectCost(
        total_files=len(analyses),
        analyzed_files=len([a for a in analyses if a.api_calls > 0]),
        file_costs=file_costs,
        model=model,
    )