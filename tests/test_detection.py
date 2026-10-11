"""Which calls count as LLM calls."""

import pytest


def apis(analysis):
    return [s.api for s in analysis.sites]


@pytest.mark.parametrize(
    "src, api, provider",
    [
        (
            "from openai import OpenAI\nc = OpenAI()\nc.chat.completions.create(model='gpt-4o', messages=[])",
            "openai.chat",
            "openai",
        ),
        (
            "import openai\nc = openai.OpenAI()\nc.responses.create(model='gpt-5', input='hi')",
            "openai.responses",
            "openai",
        ),
        (
            "import anthropic\nc = anthropic.Anthropic()\nc.messages.create(model='claude-opus-5-5', max_tokens=9, messages=[])",
            "anthropic.messages",
            "anthropic",
        ),
        (
            "from google import genai\nc = genai.Client()\nc.models.generate_content(model='gemini-2.5-pro', contents='x')",
            "google.generate_content",
            "google",
        ),
        ("import litellm\nlitellm.completion(model='gpt-4o', messages=[])", "litellm", "unknown"),
        ("from litellm import completion\ncompletion(model='gpt-4o', messages=[])", "litellm", "unknown"),
        ("import ollama\nollama.chat(model='llama3.2', messages=[])", "ollama", "ollama"),
    ],
)
def test_sdk_calls(single, src, api, provider):
    a = single(src)
    assert [(s.api, s.provider) for s in a.sites] == [(api, provider)]


def test_client_stored_on_self(single):
    a = single("""
        from anthropic import AsyncAnthropic
        class Agent:
            def __init__(self):
                self.client = AsyncAnthropic()
            async def step(self, msgs):
                return await self.client.messages.create(model="claude-haiku-5-5", max_tokens=100, messages=msgs)
    """)
    assert apis(a) == ["anthropic.messages"]


def test_langchain_positional_invoke(single):
    # Regression: 0.2.x needed a model=/messages= keyword, so this was invisible.
    a = single("""
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o-mini")
        for q in ["a", "b"]:
            llm.invoke(q)
    """)
    assert [(s.api, s.provider, s.model) for s in a.sites] == [("framework", "openai", "gpt-4o-mini")]


def test_langchain_chain_and_bound_tools(single):
    a = single("""
        from langchain_anthropic import ChatAnthropic
        from langchain_core.prompts import ChatPromptTemplate
        llm = ChatAnthropic(model="claude-sonnet-5-5")
        prompt = ChatPromptTemplate.from_template("{q}")
        chain = prompt | llm
        tooled = llm.bind_tools([])
        chain.invoke({"q": 1})
        tooled.invoke("x")
        prompt.invoke({"q": 1})
    """)
    # The prompt template alone is not an LLM call.
    assert [s.line for s in a.sites] == [7, 8]
    assert all(s.model == "claude-sonnet-5-5" for s in a.sites)


def test_gemini_model_object(single):
    a = single("""
        import google.generativeai as genai
        model = genai.GenerativeModel("gemini-2.5-flash")
        model.generate_content("hi")
    """)
    assert [(s.api, s.model) for s in a.sites] == [("google.generate_content", "gemini-2.5-flash")]


def test_with_statement_client(single):
    a = single("""
        from openai import OpenAI
        with OpenAI() as client:
            client.chat.completions.create(model="gpt-4o", messages=[], max_tokens=5)
    """)
    assert apis(a) == ["openai.chat"]


def test_model_from_module_constant(single):
    a = single("""
        from openai import OpenAI
        MODEL = "gpt-4.1-mini"
        OpenAI().chat.completions.create(model=MODEL, messages=[])
    """)
    assert a.sites[0].model == "gpt-4.1-mini"


@pytest.mark.parametrize(
    "src",
    [
        # Regression: 0.2.x counted this as an LLM call because of `input=`.
        "import subprocess\nfor f in ['a']:\n    subprocess.run(['cat'], input=f)",
        "Order.objects.create(model='x', prompt='y')",
        "import requests\nrequests.post('https://x', json={'messages': []})",
        "from langchain_core.prompts import ChatPromptTemplate\nChatPromptTemplate.from_template('x').invoke({})",
        "d = {}\nd.get('model')",
    ],
)
def test_not_llm_calls(single, src):
    assert single(src).sites == []


def test_generic_messages_heuristic(single):
    a = single("client = make()\nclient.chat(model='m', messages=[])")
    assert apis(a) == ["generic"]


def test_syntax_error_is_reported_not_fatal(project):
    a = project(
        {
            "bad.py": "def (:\n",
            "good.py": "import openai\nopenai.OpenAI().chat.completions.create(model='x', messages=[])",
        }
    )
    by_name = {f.path.name: f for f in a.files}
    assert "syntax error" in by_name["bad.py"].error
    assert len(by_name["good.py"].sites) == 1
