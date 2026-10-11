import json

import pytest

from agentguard.pricing import DEFAULT_MODEL, PriceTable, normalize_model_name

T = PriceTable.bundled()


@pytest.mark.parametrize(
    "written, key",
    [
        ("gpt-4o", "gpt-4o"),
        ("gpt-4o-mini-2024-07-18", "gpt-4o-mini"),
        ("openai/gpt-4.1-mini", "gpt-4.1-mini"),
        ("claude-sonnet-4-5-20250929", "claude-sonnet-4-5"),
        ("anthropic.claude-opus-5-5", "claude-opus-5-5"),
        ("claude-sonnet-4.5", "claude-sonnet-4-5"),
        ("models/gemini-2.5-pro", "gemini-2.5-pro"),
        ("GPT-5", "gpt-5"),
        ("totally-unknown", None),
        (None, None),
    ],
)
def test_resolve(written, key):
    assert T.resolve(written) == key


def test_normalize_keeps_non_date_suffix():
    assert normalize_model_name("gpt-5.4-mini") == "gpt-5.4-mini"


def test_default_model_is_priced():
    assert T.resolve(DEFAULT_MODEL) == DEFAULT_MODEL


def test_every_bundled_price_is_sane():
    for name, p in T.models.items():
        assert 0 < p.input <= p.output, name
        assert p.cache_read is None or p.cache_read <= p.input, name


def test_litellm_override(tmp_path):
    f = tmp_path / "prices.json"
    f.write_text(
        json.dumps(
            {
                "my-model": {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6, "litellm_provider": "openai"},
                "sample_spec": {"note": "ignored"},
            }
        )
    )
    t = PriceTable.load(str(f))
    assert t.get("my-model").input == pytest.approx(1.0)
    assert t.get("my-model").output == pytest.approx(2.0)
    assert "gpt-4o" in t.models  # bundled entries remain


def test_native_override(tmp_path):
    f = tmp_path / "p.json"
    f.write_text(json.dumps({"as_of": "x", "models": {"gpt-4o": {"input": 1, "output": 2}}}))
    assert PriceTable.load(str(f)).get("gpt-4o").input == 1
