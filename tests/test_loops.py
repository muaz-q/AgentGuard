"""Loop bounds and the rules that depend on them (AG001, AG003, AG004)."""

from conftest import rules

HEAD = "from openai import OpenAI\nclient = OpenAI()\n"
CALL = "client.chat.completions.create(model='gpt-4o', messages=[], max_tokens=10)"


def loop_kinds(analysis):
    return [[(lp.kind, lp.count) for lp in s.loops] for s in analysis.sites]


def test_while_true_without_cap_is_unbounded(single):
    a = single(HEAD + f"while True:\n    r = {CALL}\n    if r.stop_reason == 'end_turn':\n        break\n")
    assert loop_kinds(a) == [[("unbounded", None)]]
    assert rules(a) == ["AG001"]


def test_while_true_with_step_cap(single):
    a = single(
        HEAD
        + f"MAX_STEPS = 8\nstep = 0\nwhile True:\n    {CALL}\n    step += 1\n    if step >= MAX_STEPS:\n        break\n"
    )
    assert loop_kinds(a) == [[("fixed", 8)]]
    assert rules(a) == []


def test_while_counter_condition(single):
    a = single(HEAD + f"def run(max_steps):\n    i = 0\n    while i < max_steps:\n        {CALL}\n        i += 1\n")
    assert loop_kinds(a) == [[("capped", None)]]
    assert rules(a) == []


def test_while_open_condition(single):
    a = single(
        HEAD + f"done = False\nwhile not done:\n    r = {CALL}\n    done = r.choices[0].finish_reason == 'stop'\n"
    )
    assert rules(a) == ["AG001"]


def test_range_literal_is_fixed(single):
    # Regression: 0.2.x simulated range(3) up to N=100.
    a = single(HEAD + f"for i in range(3):\n    {CALL}\n")
    assert loop_kinds(a) == [[("fixed", 3)]]
    assert rules(a) == []


def test_range_of_constant(single):
    a = single(HEAD + f"N = 4\nfor i in range(1, N):\n    {CALL}\n")
    assert loop_kinds(a) == [[("fixed", 3)]]


def test_literal_list_is_fixed(single):
    a = single(HEAD + f"for p in ['a', 'b']:\n    {CALL}\n")
    assert loop_kinds(a) == [[("fixed", 2)]]


def test_loop_over_data(single):
    a = single(HEAD + f"def run(docs):\n    for d in docs:\n        {CALL}\n")
    assert loop_kinds(a) == [[("data", None)]]
    assert rules(a) == ["AG004"]


def test_itertools_count_is_unbounded(single):
    a = single(HEAD + f"import itertools\nfor i in itertools.count():\n    {CALL}\n")
    assert rules(a) == ["AG001"]


def test_async_for_is_a_loop(single):
    # Regression: 0.2.x had no visit_AsyncFor.
    a = single(HEAD + f"async def run(stream):\n    async for item in stream:\n        await {CALL}\n")
    assert loop_kinds(a) == [[("data", None)]]


def test_comprehension_is_a_loop(single):
    a = single(HEAD + f"def run(docs):\n    return [{CALL} for d in docs]\n")
    assert loop_kinds(a) == [[("data", None)]]


def test_nested_open_loops(single):
    a = single(HEAD + f"def run(a, b):\n    for x in a:\n        for y in b:\n            {CALL}\n")
    assert rules(a) == ["AG003"]


def test_nested_fixed_inner_is_not_nested_risk(single):
    a = single(HEAD + f"def run(a):\n    for x in a:\n        for y in range(2):\n            {CALL}\n")
    assert rules(a) == ["AG004"]


def test_function_body_does_not_inherit_enclosing_loop(single):
    a = single(HEAD + f"for i in range(1000):\n    def helper():\n        {CALL}\n")
    assert loop_kinds(a) == [[]]


# Patterns found while hand-reviewing findings on real projects (bench/labels.csv).


def test_cap_via_continue_countdown(single):
    # Aider's cache-warming thread: the loop runs on, but calls stop when the countdown ends.
    a = single(
        HEAD
        + "class W:\n    def run(self):\n        while self.ok:\n"
        + "            if self.pings_left <= 0:\n                continue\n"
        + f"            self.pings_left -= 1\n            {CALL}\n"
    )
    assert loop_kinds(a) == [[("capped", None)]]
    assert rules(a) == []


def test_cap_via_flag(single):
    # Aider's retry loop: a timeout check clears a flag, a later check returns.
    a = single(
        HEAD
        + "RETRY_TIMEOUT = 60\ndef send():\n    delay = 0.1\n    while True:\n        try:\n"
        + f"            return {CALL}\n"
        + "        except Exception:\n            retry = True\n            delay *= 2\n"
        + "            if delay > RETRY_TIMEOUT:\n                retry = False\n"
        + "            if not retry:\n                return None\n"
    )
    assert rules(a) == []


def test_interactive_loop_is_not_unbounded(single):
    a = single(HEAD + f"while True:\n    q = input('> ')\n    if q == 'exit':\n        break\n    {CALL}\n")
    assert loop_kinds(a) == [[("interactive", None)]]
    assert rules(a) == []


def test_tenacity_retry_is_not_per_item(single):
    a = single(
        HEAD
        + "from tenacity import Retrying, stop_after_attempt\n"
        + f"def ask():\n    for attempt in Retrying(stop=stop_after_attempt(3)):\n        with attempt:\n            return {CALL}\n"
    )
    assert loop_kinds(a) == [[("capped", None)]]
    assert rules(a) == []


def test_module_constant_sequence_is_fixed(single):
    a = single(HEAD + f"LANGS = ('ja', 'ko', 'zh')\ndef run():\n    for lang in LANGS:\n        {CALL}\n")
    assert loop_kinds(a) == [[("fixed", 3)]]


def test_reassigned_sequence_is_not_fixed(single):
    a = single(HEAD + f"ITEMS = ['a']\nITEMS = load()\ndef run():\n    for x in ITEMS:\n        {CALL}\n")
    assert loop_kinds(a) == [[("data", None)]]


def test_empty_literal_is_not_fixed_zero(single):
    a = single(HEAD + f"QUEUE = []\ndef run():\n    for x in QUEUE:\n        {CALL}\n")
    assert loop_kinds(a) == [[("data", None)]]
