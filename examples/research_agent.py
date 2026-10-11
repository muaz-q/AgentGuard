"""A small research agent with the cost problems AgentGuard looks for.

Run `agentguard examples/` to see them reported. Each one is fixed in research_agent_fixed.py.
"""

import anthropic
from openai import OpenAI

claude = anthropic.Anthropic()
gpt = OpenAI()

SYSTEM_PROMPT = (
    """You are a meticulous research assistant.
"""
    + "Follow the house style guide. " * 300
)  # a long static prompt (~2,200 tokens)


def summarise(text):
    # AG006: no output cap - one runaway response can cost as much as the rest of the run.
    reply = gpt.chat.completions.create(model="gpt-4.1-mini", messages=[{"role": "user", "content": text}])
    return reply.choices[0].message.content


def research(question):
    messages = [{"role": "user", "content": question}]
    # AG001: the model decides when to stop; nothing else does.
    while True:
        # AG002: `messages` grows every turn and is re-sent in full.
        # AG007: the 2,200-token system prompt is re-sent uncached on every turn.
        reply = claude.messages.create(
            model="claude-sonnet-5-5",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": reply.content})
        if reply.stop_reason == "end_turn":
            return reply
        messages.append({"role": "user", "content": "Continue."})


def research_all(questions, sources):
    # AG003: one summary per question per source.
    for q in questions:
        for s in sources:
            summarise(f"{q}\n\n{s}")
