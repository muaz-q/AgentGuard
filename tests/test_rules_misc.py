"""AG006, AG007, suppression comments."""

from conftest import rules

BIG = "x" * 6000


def test_missing_max_tokens(single):
    a = single("from openai import OpenAI\nOpenAI().chat.completions.create(model='gpt-4o', messages=[])")
    assert rules(a) == ["AG006"]


def test_max_tokens_present_or_forwarded(single):
    a = single("""
from openai import OpenAI
c = OpenAI()
c.chat.completions.create(model="gpt-5", messages=[], max_completion_tokens=100)
def f(**kw):
    return c.chat.completions.create(model="gpt-5", messages=[], **kw)
""")
    assert rules(a) == []


def test_docstring_is_not_a_prompt(single):
    # Regression: 0.2.x flagged any long docstring as a large static prompt.
    a = single(f'''
import anthropic
c = anthropic.Anthropic()
def helper():
    """{BIG}"""
    for i in range(5):
        c.messages.create(model="claude-opus-5-5", max_tokens=9, messages=[])
''')
    assert a.sites[0].system_tokens is None


def test_large_uncached_prompt_in_loop(single):
    a = single(f'''
import anthropic
c = anthropic.Anthropic()
SYSTEM = """{BIG}"""
for i in range(5):
    c.messages.create(model="claude-opus-5-5", max_tokens=9, system=SYSTEM, messages=[])
''')
    assert a.sites[0].system_tokens == 1500
    assert rules(a) == ["AG007"]


def test_cached_prompt_is_fine(single):
    a = single(f'''
import anthropic
c = anthropic.Anthropic()
SYSTEM = """{BIG}"""
for i in range(5):
    c.messages.create(model="claude-opus-5-5", max_tokens=9, messages=[],
                      system=[{{"type": "text", "text": SYSTEM, "cache_control": {{"type": "ephemeral"}}}}])
''')
    assert rules(a) == []


def test_large_prompt_imported_from_another_module(project):
    a = project(
        {
            "prompts.py": f'SYSTEM = """{BIG}"""\n',
            "agent.py": (
                "import anthropic\nfrom prompts import SYSTEM\nc = anthropic.Anthropic()\n"
                "for i in range(5):\n    c.messages.create(model='claude-opus-5-5', max_tokens=9, system=SYSTEM, messages=[])\n"
            ),
        }
    )
    assert rules(a) == ["AG007"]


def test_openai_large_prompt_not_flagged(single):
    # OpenAI caches long prefixes automatically; AG007 is Anthropic-only.
    a = single(f'''
from openai import OpenAI
c = OpenAI()
SYSTEM = """{BIG}"""
for i in range(5):
    c.chat.completions.create(model="gpt-4o", max_tokens=9, messages=[{{"role": "system", "content": SYSTEM}}])
''')
    assert rules(a) == []


def test_suppress_one_rule(single):
    a = single(
        "from openai import OpenAI\nwhile True:\n    OpenAI().chat.completions.create(model='x', messages=[])  # agentguard: ignore[AG006]\n"
    )
    assert rules(a) == ["AG001"]


def test_suppress_all_on_line(single):
    a = single(
        "from openai import OpenAI\nwhile True:\n    OpenAI().chat.completions.create(model='x', messages=[])  # agentguard: ignore\n"
    )
    assert rules(a) == []


def test_suppress_file(single):
    a = single(
        "# agentguard: ignore-file\nfrom openai import OpenAI\nwhile True:\n    OpenAI().chat.completions.create(model='x', messages=[])\n"
    )
    assert rules(a) == []
