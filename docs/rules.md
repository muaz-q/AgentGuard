# Rules

Each finding has a rule id, a severity, a location and a fix. Turn rules off with
`--ignore AG004,AG006`, `ignore = [...]` under `[tool.agentguard]` in pyproject.toml, or a
comment on the reported line: `# agentguard: ignore[AG006]` (or `# agentguard: ignore` for all).

Precision is the share of findings that were correct when every finding on 8 open-source
agent projects was checked by hand, with the rules frozen first. See [benchmarks.md](benchmarks.md).

| Rule | Severity | Hold-out precision |
|---|---|---|
| [AG001](#ag001) llm-call-in-unbounded-loop | high | 0/1 |
| [AG002](#ag002) unbounded-context-growth | high (medium for short fixed loops) | 5/5 |
| [AG003](#ag003) llm-call-in-nested-loop | medium | 4/4 |
| [AG004](#ag004) llm-call-per-item | low | 10/11 |
| [AG005](#ag005) unbounded-llm-recursion | high | 0/1 |
| [AG006](#ag006) missing-max-tokens | low | 14/14 |
| [AG007](#ag007) uncached-large-prompt-in-loop | medium | no findings in the sample |

## AG001

**An LLM call inside a loop with no detectable iteration cap.** The classic agent loop that
stops only when the model says so. If the model never says so - a tool that keeps failing,
a confused plan - it runs until something else stops it.

```python
while True:  # AG001
    reply = client.messages.create(...)
    if reply.stop_reason == "end_turn":
        break
```

Fix: cap it.

```python
for step in range(MAX_STEPS):
    reply = client.messages.create(...)
    if reply.stop_reason == "end_turn":
        break
```

Recognised as caps: `range(...)`, `while i < N` / `while step < max_steps`, `if step >= MAX_STEPS: break`
(also `return`, `raise`, `continue`), countdowns (`left -= 1` ... `if left <= 0`), and a cap
check that clears a flag tested later. Loops that wait for a person each iteration
(`input()`, `Prompt.ask`) are human-paced and not reported. Known false positive: a server
loop paced by incoming messages (`await websocket.receive_json()`).

## AG002

**History that grows every iteration and is re-sent on every call.** Turn `k` re-sends all
`k - 1` earlier turns, so input tokens grow with the square of the number of turns. At 40
turns the measured total input was 30-100x what a "40 calls x turn-1 size" estimate gives
([measured](benchmarks.md#cost-model)).

```python
for step in range(MAX_STEPS):
    reply = client.chat.completions.create(model=M, messages=messages)  # AG002
    messages.append(reply.choices[0].message)
```

Found whether the append comes before or after the call, through `+=`, `x = x + [...]`,
f-strings, helper functions that take the history as an argument, and methods that append
to `self.messages`. Not reported when the loop also trims the history: `messages = messages[-k:]`,
`messages[:1] + messages[-k:]`, `del messages[...]`, `.pop()`, or `x = summarize(x)`.

Fix: keep a sliding window or summarise; use provider-side compaction where available.

## AG003

**An LLM call inside two or more loops whose size is not a small constant.** The call count
is the product of the loop sizes. Loops over literals and module-level constant sequences
(`LANGS = ("ja", "ko")`) count as fixed and do not trigger this.

Fix: send the items as one batch, or cap the inner loop.

## AG004

**One LLM call per item of a collection.** Cost scales with input size, which is often fine -
but worth knowing. Not reported for tenacity `Retrying` loops. Known false positive: a
fallback loop over models that returns on the first success.

Fix: if the results are not needed right away, the OpenAI and Anthropic Batch APIs bill at
50%; otherwise put several items in one call.

## AG005

**A function that makes LLM calls and calls itself with no depth parameter.** Recursive
planners ("break the task into subtasks, then research each") can fan out without limit.
Not reported when the function has a parameter named like `depth`, `level`, `remaining`,
`budget`, `max_*` or `limit`. Known false positive: a self-call that is really a one-time
retry or is bounded by external events.

Fix: pass `depth` down and stop at a fixed maximum.

## AG006

**An OpenAI or LiteLLM call that sets no output cap** (`max_tokens`, `max_completion_tokens`,
`max_output_tokens`). One runaway response can cost as much as the rest of the run.
Calls that forward `**kwargs` are not reported. Anthropic calls are not checked: the API
requires `max_tokens`.

## AG007

**A large static prompt (about 1,000+ tokens) sent to Anthropic on every loop iteration
without `cache_control`.** Anthropic caching is opt-in; cached reads bill at about 10% of the
input price. Prompts built with `+`, `*`, f-strings and `textwrap.dedent` are measured, as are
prompts imported from another module. OpenAI and Gemini cache long prefixes automatically,
so this rule is Anthropic-only.
