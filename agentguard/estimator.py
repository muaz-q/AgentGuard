"""Cost model: turn call sites and their loop context into a dollar range.

Static analysis cannot know how many times a data-dependent or open-ended loop runs, so
those loops are evaluated at several assumed iteration counts (``depths``). Loops with a
constant bound use that bound. Everything else is an explicit, user-overridable assumption.

Per call, a model receives ``system + input`` tokens and returns ``output`` tokens.
When a loop re-sends a history that grows every iteration, turn ``k`` (1-based) also
re-sends the ``k - 1`` previous inputs and outputs, so over ``n`` turns:

    input  = n*S + U*n(n+1)/2 + O*n(n-1)/2
    output = n*O
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from agentguard.analyzer import CallSite, ProjectAnalysis
from agentguard.pricing import DEFAULT_MODEL, Price, PriceTable

FREE_PROVIDERS = {"ollama"}  # local inference


@dataclass(frozen=True)
class Assumptions:
    system_tokens: int = 500
    input_tokens: int = 500
    output_min: int = 200
    output_max: int = 1000
    depths: Tuple[int, ...] = (1, 10, 100)
    model: str = DEFAULT_MODEL


@dataclass
class Usage:
    """Tokens and dollars for some number of calls."""

    input: float = 0.0
    output: float = 0.0
    cached: float = 0.0  # input tokens billed at the cache-read rate
    calls: float = 0.0
    cost: float = 0.0

    def __add__(self, o: Usage) -> Usage:
        return Usage(
            self.input + o.input,
            self.output + o.output,
            self.cached + o.cached,
            self.calls + o.calls,
            self.cost + o.cost,
        )

    def scaled(self, k: float) -> Usage:
        return Usage(self.input * k, self.output * k, self.cached * k, self.calls * k, self.cost * k)


@dataclass
class SiteEstimate:
    site: CallSite
    model: str
    model_assumed: bool  # the code names no model we could price, so the default was used
    low: Dict[int, Usage] = field(default_factory=dict)  # depth -> usage at output_min
    high: Dict[int, Usage] = field(default_factory=dict)  # depth -> usage at output_max


@dataclass
class Estimate:
    assumptions: Assumptions
    prices_as_of: str
    sites: List[SiteEstimate]
    unknown_models: Set[str]

    def total(self, depth: int, bound: str) -> Usage:
        out = Usage()
        for s in self.sites:
            out = out + (s.low if bound == "low" else s.high)[depth]
        return out

    @property
    def depths(self) -> Tuple[int, ...]:
        return self.assumptions.depths


def _iterations(site: CallSite, depth: int) -> List[int]:
    return [lp.count if lp.kind == "fixed" and lp.count is not None else depth for lp in site.loops]


class _Model:
    def __init__(self, analysis: ProjectAnalysis, prices: PriceTable, a: Assumptions):
        self.a = a
        self.prices = prices
        self.unknown: Set[str] = set()
        default = prices.resolve(a.model)
        if default is None:
            raise ValueError(f"model {a.model!r} is not in the price table (see --list-models)")
        self.default: str = default
        self.by_function: Dict[str, List[CallSite]] = {}
        for s in analysis.sites:
            self.by_function.setdefault(s.function, []).append(s)
        self._memo: Dict[Tuple[str, int, int], Usage] = {}
        self._active: Set[str] = set()

    def model_for(self, site: CallSite) -> Tuple[str, bool]:
        key = self.prices.resolve(site.model)
        if key:
            return key, False
        if site.model:
            self.unknown.add(site.model)
        return self.default, True

    def _cost(self, price: Optional[Price], inp: float, out: float, cached: float) -> float:
        if price is None:
            return 0.0
        cache_rate = price.cache_read if price.cache_read is not None else price.input
        return ((inp - cached) * price.input + cached * cache_rate + out * price.output) / 1e6

    def site_usage(self, site: CallSite, depth: int, out_tokens: int) -> Usage:
        iters = _iterations(site, depth)
        inner = iters[-1] if iters else 1
        outer = 1
        for k in iters[:-1]:
            outer *= k
        calls = inner * outer
        S = site.system_tokens or self.a.system_tokens
        U, O = self.a.input_tokens, out_tokens

        if site.target:  # a call into a function that makes LLM calls
            per = self.invocation(site.target, depth, out_tokens)
            usage = per.scaled(calls)
            if site.context_growth and inner > 1:
                extra = (U + O) * inner * (inner - 1) / 2 * outer
                usage = usage + Usage(input=extra, cost=self._cost(self.prices.get(self.default), extra, 0, 0))
            return usage

        model, _ = self.model_for(site)
        price = None if site.provider in FREE_PROVIDERS else self.prices.get(model)
        if site.context_growth and site.loops:
            n = inner
            inp = (n * S + U * n * (n + 1) / 2 + O * n * (n - 1) / 2) * outer
        else:
            inp = calls * (S + U)
        out = calls * O
        cached = S * (calls - 1) if site.cached and site.provider == "anthropic" and calls > 1 else 0.0
        return Usage(inp, out, cached, calls, self._cost(price, inp, out, cached))

    def invocation(self, fn: str, depth: int, out_tokens: int) -> Usage:
        key = (fn, depth, out_tokens)
        if key in self._memo:
            return self._memo[key]
        if fn in self._active:  # recursion: count one level, AG005 reports the rest
            return Usage()
        self._active.add(fn)
        total = Usage()
        for s in self.by_function.get(fn, []):
            total = total + self.site_usage(s, depth, out_tokens)
        self._active.discard(fn)
        self._memo[key] = total
        return total


def estimate(analysis: ProjectAnalysis, prices: PriceTable, a: Optional[Assumptions] = None) -> Estimate:
    a = a or Assumptions()
    m = _Model(analysis, prices, a)
    called = {s.target for s in analysis.sites if s.target}
    # A function that something else calls is costed through its callers, not on its own.
    roots = [s for s in analysis.sites if s.function not in called]
    out = []
    for s in roots:
        model, assumed = m.model_for(s) if not s.target else (m.default, False)
        est = SiteEstimate(s, model, assumed)  # type: ignore[arg-type]
        for d in a.depths:
            est.low[d] = m.site_usage(s, d, a.output_min)
            est.high[d] = m.site_usage(s, d, a.output_max)
        out.append(est)
    return Estimate(a, prices.as_of, out, m.unknown)
