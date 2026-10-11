"""The cost model, checked against hand-computed values."""

import pytest

from agentguard.estimator import Assumptions, estimate
from agentguard.pricing import PriceTable

PRICES = PriceTable.bundled()
GPT4O = PRICES.get("gpt-4o")
A = Assumptions(
    system_tokens=800, input_tokens=1200, output_min=300, output_max=3000, depths=(1, 10, 100), model="gpt-4o"
)

LOOP = """
from openai import OpenAI
client = OpenAI()
messages = []
while True:
    messages.append("q")
    r = client.chat.completions.create(model="gpt-4o", messages=messages, max_tokens=9)
    messages.append(r)
"""


def dollars(inp, out, price=GPT4O):
    return (inp * price.input + out * price.output) / 1e6


def test_quadratic_history_matches_hand_computation(single):
    est = estimate(single(LOOP), PRICES, A)
    n, S, U, O = 100, 800, 1200, 3000
    inp = sum(S + U * k + O * (k - 1) for k in range(1, n + 1))  # turn k re-sends k-1 earlier turns
    assert est.total(100, "high").input == pytest.approx(inp)
    assert est.total(100, "high").output == pytest.approx(n * O)
    assert est.total(100, "high").cost == pytest.approx(dollars(inp, n * O))
    # The review's hand-computed figure for this loop was ~$55.
    assert est.total(100, "high").cost == pytest.approx(55.47, abs=0.01)


def test_filename_does_not_change_cost(project):
    # Regression: 0.2.x multiplied cost by 20 when the file name contained "agent".
    a = project({"x_agent.py": LOOP, "plain.py": LOOP})
    est = estimate(a, PRICES, A)
    costs = [s.high[100].cost for s in est.sites]
    assert costs[0] == pytest.approx(costs[1])


def test_linear_loop(single):
    est = estimate(
        single(
            "from openai import OpenAI\nc = OpenAI()\ndef f(xs):\n    for x in xs:\n        c.chat.completions.create(model='gpt-4o', messages=[x], max_tokens=5)\n"
        ),
        PRICES,
        A,
    )
    for n in (1, 10, 100):
        assert est.total(n, "low").cost == pytest.approx(dollars(n * 2000, n * 300))


def test_fixed_loop_ignores_depth(single):
    est = estimate(
        single(
            "from openai import OpenAI\nc = OpenAI()\nfor i in range(3):\n    c.chat.completions.create(model='gpt-4o', messages=[], max_tokens=5)\n"
        ),
        PRICES,
        A,
    )
    assert est.total(1, "high").calls == est.total(100, "high").calls == 3


def test_nested_loops_multiply(single):
    est = estimate(
        single(
            "from openai import OpenAI\nc = OpenAI()\ndef f(a):\n    for x in a:\n        for y in range(4):\n            c.chat.completions.create(model='gpt-4o', messages=[], max_tokens=5)\n"
        ),
        PRICES,
        A,
    )
    assert est.total(10, "high").calls == 40


def test_model_named_in_code_is_used(single):
    est = estimate(
        single(
            "import anthropic\nanthropic.Anthropic().messages.create(model='claude-haiku-5-5-20261001', max_tokens=5, messages=[])"
        ),
        PRICES,
        A,
    )
    s = est.sites[0]
    assert (s.model, s.model_assumed) == ("claude-haiku-5-5", False)
    haiku = PRICES.get("claude-haiku-5-5")
    assert s.low[1].cost == pytest.approx(dollars(2000, 300, haiku))


def test_unknown_model_falls_back_and_is_reported(single):
    est = estimate(
        single(
            "import anthropic\nanthropic.Anthropic().messages.create(model='my-finetune', max_tokens=5, messages=[])"
        ),
        PRICES,
        A,
    )
    assert est.sites[0].model_assumed
    assert est.unknown_models == {"my-finetune"}


def test_cache_read_pricing(single):
    big = "x" * 8000  # 2000 tokens
    src = f'''
import anthropic
c = anthropic.Anthropic()
SYSTEM = """{big}"""
def f(xs):
    for x in xs:
        c.messages.create(model="claude-opus-5-5", max_tokens=5, messages=[x],
                          system=[{{"type": "text", "text": SYSTEM, "cache_control": {{"type": "ephemeral"}}}}])
'''
    est = estimate(single(src), PRICES, A)
    p = PRICES.get("claude-opus-5-5")
    n, S, U, O = 10, 2000, 1200, 300
    expected = ((n * U + S) * p.input + (n - 1) * S * p.cache_read + n * O * p.output) / 1e6
    assert est.total(10, "low").cost == pytest.approx(expected)


def test_helper_costed_through_caller_not_twice(single):
    src = """
from openai import OpenAI
c = OpenAI()
def ask(q):
    return c.chat.completions.create(model="gpt-4o", messages=[q], max_tokens=5)
def run(qs):
    for q in qs:
        ask(q)
"""
    est = estimate(single(src), PRICES, A)
    assert len(est.sites) == 1 and est.sites[0].site.target
    assert est.total(10, "low").calls == 10
    assert est.total(10, "low").cost == pytest.approx(dollars(10 * 2000, 10 * 300))


def test_local_models_are_free(single):
    est = estimate(
        single("import ollama\nfor i in range(9):\n    ollama.chat(model='llama3.2', messages=[])"), PRICES, A
    )
    assert est.total(1, "high").cost == 0
    assert est.total(1, "high").calls == 9


def test_unknown_default_model_is_an_error(single):
    with pytest.raises(ValueError):
        estimate(single(LOOP), PRICES, Assumptions(model="not-a-model"))
