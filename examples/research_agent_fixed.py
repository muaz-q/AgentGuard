"""research_agent.py with each finding fixed. `agentguard examples/research_agent_fixed.py` is clean."""

import anthropic
from openai import OpenAI

claude = anthropic.Anthropic()
gpt = OpenAI()

SYSTEM_PROMPT = (
    """You are a meticulous research assistant.
"""
    + "Follow the house style guide. " * 300
)

MAX_STEPS = 12
KEEP_TURNS = 8


def summarise(texts):
    # One call for the whole batch, with an output cap.
    reply = gpt.chat.completions.create(
        model="gpt-4.1-mini",
        max_completion_tokens=800,
        messages=[{"role": "user", "content": "\n\n---\n\n".join(texts)}],
    )
    return reply.choices[0].message.content


def research(question):
    messages = [{"role": "user", "content": question}]
    for _ in range(MAX_STEPS):  # a hard cap on turns
        reply = claude.messages.create(
            model="claude-sonnet-5-5",
            max_tokens=2048,
            # The static prefix is cached: later turns read it at ~10% of the input price.
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
        )
        if reply.stop_reason == "end_turn":
            return reply
        messages.append({"role": "assistant", "content": reply.content})
        messages.append({"role": "user", "content": "Continue."})
        messages = messages[:1] + messages[-KEEP_TURNS:]  # a sliding window, not the whole history
    return None


def research_all(questions, sources):
    return summarise([f"{q}\n\n{s}" for q in questions for s in sources])
