"""A minimal chat agent that keeps its whole history - the pattern AG002 flags.

Runs against a local Ollama server so it can be measured for free. validate_cost_model.py
runs AgentGuard on this file and compares its prediction with the token counts Ollama reports.
"""

import ollama

SYSTEM = "You are a storyteller. Continue the story you are given; never summarise or stop early."


def run(model, turns, max_tokens, topic, questions=None):
    """One chat turn per iteration. With ``questions``, user turns cycle through them and
    replies end naturally, so message sizes vary from turn to turn."""
    messages = [{"role": "system", "content": SYSTEM}]
    usage = []
    for turn in range(turns):
        if questions:
            text = f"About {topic}: {questions[turn % len(questions)]}"
        else:
            text = f"Turn {turn + 1}. Continue the story about {topic}."
        messages.append({"role": "user", "content": text})
        reply = ollama.chat(
            model=model,
            messages=messages,
            options={"num_predict": max_tokens, "num_ctx": 32768, "temperature": 0, "seed": 7},
        )
        messages.append({"role": "assistant", "content": reply.message.content})
        usage.append({"input": reply.prompt_eval_count, "output": reply.eval_count})
    return usage
