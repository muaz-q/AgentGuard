"""History growth (AG002)."""

HEAD = "from openai import OpenAI\nclient = OpenAI()\n"


def growth(analysis):
    return [s.context_growth for s in analysis.sites]


def test_append_after_the_call(single):
    # Regression: the canonical agent loop. 0.2.x only saw appends that came before the call.
    a = single(
        HEAD
        + """
messages = [{"role": "user", "content": "hi"}]
for _ in range(50):
    r = client.chat.completions.create(model="gpt-4o", messages=messages, max_tokens=9)
    messages.append(r.choices[0].message)
"""
    )
    assert growth(a) == [True]
    assert [f.rule for f in a.findings] == ["AG002"]
    assert a.findings[0].severity == "high"  # 50 > 20 turns


def test_short_fixed_loop_is_medium(single):
    a = single(
        HEAD
        + """
messages = []
for _ in range(5):
    messages.append("q")
    client.chat.completions.create(model="gpt-4o", messages=messages, max_tokens=9)
"""
    )
    assert [(f.rule, f.severity) for f in a.findings] == [("AG002", "medium")]


def test_history_inside_fstring(single):
    # Regression: 0.2.x did not look inside f-strings.
    a = single(
        HEAD
        + """
history = []
for t in range(10):
    history.append(t)
    client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": f"{history}"}], max_tokens=9)
"""
    )
    assert growth(a) == [True]


def test_concatenation_counts_as_growth(single):
    a = single(
        HEAD
        + """
def run(qs):
    msgs = []
    for q in qs:
        msgs = msgs + [q]
        client.chat.completions.create(model="gpt-4o", messages=msgs, max_tokens=9)
"""
    )
    assert growth(a) == [True]


def test_sliding_window_is_not_growth(single):
    a = single(
        HEAD
        + """
messages = []
while True:
    messages.append("q")
    client.chat.completions.create(model="gpt-4o", messages=messages, max_tokens=9)
    messages = messages[-10:]
"""
    )
    assert growth(a) == [False]
    assert [f.rule for f in a.findings] == ["AG001"]


def test_summarise_is_not_growth(single):
    a = single(
        HEAD
        + """
def loop(messages, summarize_history):
    for _ in range(100):
        messages.append("q")
        client.chat.completions.create(model="gpt-4o", messages=messages, max_tokens=9)
        messages = summarize_history(messages)
"""
    )
    assert growth(a) == [False]


def test_reset_each_iteration_is_not_growth(single):
    a = single(
        HEAD
        + """
def run(tasks):
    for t in tasks:
        messages = [{"role": "system", "content": "x"}]
        messages.append(t)
        client.chat.completions.create(model="gpt-4o", messages=messages, max_tokens=9)
"""
    )
    assert growth(a) == [False]


def test_unrelated_append_is_not_growth(single):
    a = single(
        HEAD
        + """
def run(qs):
    results = []
    for q in qs:
        r = client.chat.completions.create(model="gpt-4o", messages=[q], max_tokens=9)
        results.append(r)
"""
    )
    assert growth(a) == [False]


def test_conversation_class_called_in_loop(single):
    # A method that appends to self.messages and sends it, called once per turn.
    a = single("""
import anthropic

class Conversation:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.messages = []

    def send(self, text):
        self.messages.append({"role": "user", "content": text})
        r = self.client.messages.create(model="claude-opus-5-5", max_tokens=100, messages=self.messages)
        self.messages.append({"role": "assistant", "content": r.content})
        return r

def main(questions):
    conv = Conversation()
    for q in questions:
        conv.send(q)
""")
    loop_site = next(s for s in a.sites if s.target)
    assert loop_site.target.endswith(":Conversation.send")
    assert loop_site.context_growth
    assert {f.rule for f in a.findings} == {"AG002", "AG004"}


def test_window_keeping_first_message_is_not_growth(single):
    a = single(
        HEAD
        + """
messages = []
while True:
    messages.append("q")
    client.chat.completions.create(model="gpt-4o", messages=messages, max_tokens=9)
    messages = messages[:1] + messages[-8:]
"""
    )
    assert growth(a) == [False]


def test_window_with_star_unpacking_is_not_growth(single):
    a = single(
        HEAD
        + """
def run(qs):
    messages = []
    for q in qs:
        messages.append(q)
        client.chat.completions.create(model="gpt-4o", messages=messages, max_tokens=9)
        messages = [*messages[:1], *messages[-8:]]
"""
    )
    assert growth(a) == [False]
