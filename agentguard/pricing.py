"""Model price table: bundled defaults, user overrides, and model-name resolution."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Dict, Optional

DEFAULT_MODEL = "claude-sonnet-5-5"


@dataclass(frozen=True)
class Price:
    """USD per 1M tokens."""

    input: float
    output: float
    cache_read: Optional[float] = None
    provider: str = "unknown"


class PriceTable:
    def __init__(self, models: Dict[str, Price], as_of: str = "unknown"):
        self.models = models
        self.as_of = as_of

    @classmethod
    def bundled(cls) -> PriceTable:
        text = resources.files("agentguard").joinpath("data/prices.json").read_text("utf-8")
        return cls._from_json(json.loads(text))

    @classmethod
    def load(cls, path: Optional[str] = None) -> PriceTable:
        """The bundled table, with entries from ``path`` layered on top."""
        table = cls.bundled()
        if path:
            extra = cls._from_json(json.loads(Path(path).read_text("utf-8")))
            table.models.update(extra.models)
            table.as_of = f"{table.as_of} + {Path(path).name}"
        return table

    @classmethod
    def _from_json(cls, data: dict) -> PriceTable:
        # Native format: {"as_of": ..., "models": {name: {"input": per-1M, ...}}}
        if isinstance(data.get("models"), dict):
            models = {
                name: Price(
                    input=float(p["input"]),
                    output=float(p["output"]),
                    cache_read=p.get("cache_read"),
                    provider=p.get("provider", "unknown"),
                )
                for name, p in data["models"].items()
            }
            return cls(models, as_of=str(data.get("as_of", "unknown")))

        # LiteLLM format: {name: {"input_cost_per_token": per-token, ...}}
        models = {}
        for name, p in data.items():
            if not isinstance(p, dict) or "input_cost_per_token" not in p:
                continue
            if "output_cost_per_token" not in p:
                continue
            cache = p.get("cache_read_input_token_cost")
            models[name] = Price(
                input=float(p["input_cost_per_token"]) * 1e6,
                output=float(p["output_cost_per_token"]) * 1e6,
                cache_read=float(cache) * 1e6 if cache is not None else None,
                provider=str(p.get("litellm_provider", "unknown")),
            )
        return cls(models, as_of="litellm")

    def resolve(self, model: Optional[str]) -> Optional[str]:
        """Map a model string as written in code to a key in the table, or None."""
        if not model:
            return None
        if model in self.models:
            return model
        name = normalize_model_name(model)
        if name in self.models:
            return name
        # Longest known name that the written name starts with, so
        # "gpt-4o-mini-2024-07-18" resolves to "gpt-4o-mini", not "gpt-4o".
        candidates = [k for k in self.models if name.startswith(k)]
        return max(candidates, key=len) if candidates else None

    def get(self, model: str) -> Price:
        return self.models[model]


_DATE_SUFFIX = re.compile(r"([-@])(\d{8}|\d{4}-\d{2}-\d{2})(-v\d+(:\d+)?)?$")


def normalize_model_name(model: str) -> str:
    name = model.strip().lower()
    # Provider prefixes: "openai/gpt-4o", "models/gemini-2.5-pro", "anthropic.claude-..."
    name = name.rsplit("/", 1)[-1]
    if name.startswith("anthropic."):
        name = name[len("anthropic.") :]
    name = _DATE_SUFFIX.sub("", name)
    # Older Claude ids use dots for the version ("claude-sonnet-4.5").
    if name.startswith("claude-"):
        name = name.replace(".", "-")
    return name
