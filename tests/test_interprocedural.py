"""LLM calls reached through other functions and modules; recursion (AG005)."""

from conftest import rules

TOOLS = """
from openai import OpenAI
client = OpenAI()

def ask(q):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": q}], max_tokens=50)

def ask_twice(q):
    return ask(q), ask(q)
"""


def test_helper_in_same_file(single):
    a = single(TOOLS + "\nwhile True:\n    ask('x')\n")
    loop_site = next(s for s in a.sites if s.loops)
    assert loop_site.target.endswith(":ask")
    assert rules(a) == ["AG001"]


def test_transitive_helper(single):
    a = single(TOOLS + "\ndef run(items):\n    for i in items:\n        ask_twice(i)\n")
    loop_site = next(s for s in a.sites if s.loops)
    assert loop_site.target.endswith(":ask_twice")


def test_cross_module_import(project):
    a = project(
        {
            "tools.py": TOOLS,
            "main.py": "from tools import ask\nwhile True:\n    ask('x')\n",
        }
    )
    assert [(f.path.name, f.rule) for f in a.findings] == [("main.py", "AG001")]


def test_module_attribute_import(project):
    a = project(
        {
            "pkg/__init__.py": "",
            "pkg/tools.py": TOOLS,
            "pkg/main.py": "from pkg import tools\nwhile True:\n    tools.ask('x')\n",
        }
    )
    assert [f.rule for f in a.findings] == ["AG001"]


def test_relative_import(project):
    a = project(
        {
            "pkg/__init__.py": "",
            "pkg/tools.py": TOOLS,
            "pkg/main.py": "from .tools import ask\nwhile True:\n    ask('x')\n",
        }
    )
    assert [f.rule for f in a.findings] == ["AG001"]


def test_unrelated_function_with_same_name_elsewhere(project):
    a = project(
        {
            "tools.py": TOOLS,
            "other.py": "def ask(q):\n    return q\nwhile True:\n    ask('x')\n",
        }
    )
    assert a.findings == []


def test_recursion_without_depth(single):
    a = single(TOOLS + "\ndef research(q):\n    r = ask(q)\n    for sub in r.choices:\n        research(sub)\n")
    assert "AG005" in rules(a)


def test_recursion_with_depth_param(single):
    a = single(
        TOOLS + "\ndef research(q, depth):\n    if depth > 3:\n        return\n    research(ask(q), depth + 1)\n"
    )
    assert "AG005" not in rules(a)
