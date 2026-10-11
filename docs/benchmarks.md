# Benchmarks

Everything here is reproducible with the scripts in [`bench/`](../bench/). Raw results are in
[`bench/results/`](../bench/results/) and every hand verdict is in [`bench/labels.csv`](../bench/labels.csv).

## Precision on real projects

### Method

AgentGuard was run on open-source agent projects at pinned commits, excluding test suites
(they call mocks). Every finding - not a sample - was checked against the source and marked
correct if what it claims is true of the code: the loop really has no cap, the history really
grows and is re-sent, the call really sets no output cap. A finding whose literal claim holds
but whose implied risk does not (a loop with no counter that is paced by a person typing)
was marked a false positive.

The projects were split before any review:

- **Tuning set (14 projects).** Reviewed while developing the rules. Four of its six false
  positives came from patterns general enough to fix (caps via `continue`, countdowns,
  `input()` loops, tenacity retries); those fixes are in the rules now, each with a test.
  Its precision is therefore optimistic.
- **Hold-out set (8 projects).** Run only after those fixes, with the rules frozen, and
  reviewed once. This is the number to quote.

### Results

| Rule | Tuning (first review) | Hold-out |
|---|---|---|
| AG001 unbounded loop | 1/4 | 0/1 |
| AG002 history growth | 3/3 | 5/5 |
| AG003 nested loops | 2/2 | 4/4 |
| AG004 per-item calls | 13/14 | 10/11 |
| AG005 recursion | 0/2 | 0/1 |
| AG006 no output cap | 25/25 | 14/14 |
| **All** | **44/50 (88%)** | **33/36 (92%)** |

AG007 produced no findings in either set; its tests are in `tests/test_rules_misc.py`.

The remaining false positives, all hold-out:

| Rule | Where | Why it is wrong |
|---|---|---|
| AG001 | khoj `routers/api_chat.py:1576` | A websocket server loop; each iteration waits for a client message. |
| AG004 | khoj `routers/helpers.py:1703` | A fallback chain over models that returns on the first success. |
| AG005 | AutoGPT `copilot/sdk/service.py:4650` | The self-call only happens when a user queues a message mid-turn. |

AG001 and AG005 are where the tool is weakest: they make the strongest claims (this will
not stop), and the evidence they need - what bounds a loop or a recursion - is often outside
the function. AG002, AG003 and AG006 were right every time they fired.

### Projects

| Set | Project | Commit | Files | Lines | LLM call sites | Findings |
|---|---|---|---|---|---|---|
| tuning | [Aider-AI/aider](https://github.com/Aider-AI/aider/tree/5dc9490bb35f9729ef2c95d00a19ccd30c26339c) | `5dc9490` | 105 | 25,853 | 3 | 0 |
| tuning | [AntonOsika/gpt-engineer](https://github.com/AntonOsika/gpt-engineer/tree/a90fcd543eedcc0ff2c34561bc0785d2ba83c47e) | `a90fcd5` | 58 | 6,894 | 2 | 0 |
| tuning | [OpenInterpreter/open-interpreter](https://github.com/OpenInterpreter/open-interpreter/tree/ac1fcc8fe57aba51fcc3c79afd57a0883237fe87) | `ac1fcc8` | 125 | 40,963 | 0 | 0 |
| tuning | [SWE-agent/SWE-agent](https://github.com/SWE-agent/SWE-agent/tree/3ea751c087f32b16e039a2233dd6eefecef325d5) | `3ea751c` | 68 | 12,477 | 4 | 0 |
| tuning | [TransformerOptimus/SuperAGI](https://github.com/TransformerOptimus/SuperAGI/tree/c3c1982e7bd6a11cfed53c5a193ea502f924b1b6) | `c3c1982` | 306 | 23,950 | 2 | 0 |
| tuning | [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher/tree/3582a6841fe7dc801e2a34e34ee408641aea9bce) | `3582a68` | 217 | 26,038 | 8 | 1 |
| tuning | [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI/tree/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d) | `6b93fa0` | 951 | 324,006 | 84 | 14 |
| tuning | [geekan/MetaGPT](https://github.com/geekan/MetaGPT/tree/11cdf466d042aece04fc6cfd13b28e1a70341b1f) | `11cdf46` | 580 | 66,151 | 18 | 0 |
| tuning | [huggingface/smolagents](https://github.com/huggingface/smolagents/tree/96f33faaf028479119ec8d34507b47694cf14e34) | `96f33fa` | 48 | 17,673 | 2 | 1 |
| tuning | [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research/tree/1b7d2e80db9faa586165c60e09096dbbfd483a64) | `1b7d2e8` | 13 | 5,837 | 7 | 0 |
| tuning | [openai/openai-agents-python](https://github.com/openai/openai-agents-python/tree/125efa029b4bfd84238bd2c4fd69c3406f802663) | `125efa0` | 551 | 170,426 | 23 | 4 |
| tuning | [openai/swarm](https://github.com/openai/swarm/tree/6af0b4caf37dca4526dfd98e9fbd8ce36e7eeb22) | `6af0b4c` | 58 | 3,434 | 35 | 8 |
| tuning | [stanfordnlp/dspy](https://github.com/stanfordnlp/dspy/tree/f1260ff14610286cb295c7d3a5ee2cbfd0ba5cb9) | `f1260ff` | 260 | 73,309 | 4 | 0 |
| tuning | [yoheinakajima/babyagi](https://github.com/yoheinakajima/babyagi/tree/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2) | `fa8930e` | 41 | 6,153 | 18 | 17 |
| holdout | [browser-use/browser-use](https://github.com/browser-use/browser-use/tree/c75e8476e26d18b7617643bc2ae082fae8eae431) | `c75e847` | 280 | 75,615 | 47 | 6 |
| holdout | [qodo-ai/pr-agent](https://github.com/qodo-ai/pr-agent/tree/cf76f708a1ac58cc8d0e26dde26fa53cc4b8819e) | `cf76f70` | 120 | 50,467 | 1 | 1 |
| holdout | [mem0ai/mem0](https://github.com/mem0ai/mem0/tree/b7ad69afda6b6ed030347c66d48a13e4de9dec08) | `b7ad69a` | 277 | 77,704 | 25 | 3 |
| holdout | [camel-ai/camel](https://github.com/camel-ai/camel/tree/24fde60ad739b4be8f8f533fea9ba54256fbc4a2) | `24fde60` | 853 | 205,221 | 30 | 1 |
| holdout | [Significant-Gravitas/AutoGPT](https://github.com/Significant-Gravitas/AutoGPT/tree/4473fbbcb1951471df0a05374d47c93c4e39bea6) | `4473fbb` | 1,334 | 386,154 | 157 | 12 |
| holdout | [khoj-ai/khoj](https://github.com/khoj-ai/khoj/tree/ae229ca894c0b80ad84664afcfdde523b5e87057) | `ae229ca` | 224 | 34,760 | 118 | 10 |
| holdout | [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai/tree/69ea1e57201ed59e7d30fbe4a7590d193acecce0) | `69ea1e5` | 895 | 264,034 | 29 | 2 |
| holdout | [microsoft/TaskWeaver](https://github.com/microsoft/TaskWeaver/tree/d44ddef23f90059fb17999d3095db4240e98f955) | `d44ddef` | 139 | 15,859 | 10 | 1 |

Recall is not measured: it would need every LLM call site in 1.9M lines labelled by hand.
As a sanity check, [`bench/pattern_recall.py`](../bench/pattern_recall.py) finds every call
whose shape is unmistakably a direct SDK call (`*.chat.completions.create`, `*.messages.create`,
`*.responses.create`, `litellm.completion`, `*.generate_content`, ...) and checks AgentGuard
reported it: **176 of 176** across all 22 projects. This shares the detector's idea of what a
call looks like, so it cannot find whole classes of misses; what it does catch is aliasing - an
earlier grep version of the same check found that Aider's `from aider.llm import litellm`
re-export hid both of Aider's calls, which was then fixed. Calls made through a framework's own abstraction (MetaGPT's `self.llm.aask`)
are seen where the framework makes the SDK call, not at the user's call.

## Cost model against measured tokens

### Method

[`bench/ollama_agent.py`](../bench/ollama_agent.py) is a minimal chat agent that keeps its whole
history - the pattern AG002 reports. [`bench/validate_cost_model.py`](../bench/validate_cost_model.py):

1. runs AgentGuard on it and checks the finding (one `ollama` call site, history growth);
2. runs it for 40 turns on `llama3.2` (3B) through Ollama, recording the prompt and
   completion token counts Ollama reports for every call;
3. calibrates the per-turn sizes from the **first two turns only** - static prompt `S`,
   new input per turn `U`, output `O` - and predicts the cumulative input tokens for every
   turn count from 3 to 40 with AgentGuard's estimator.

The naive estimate is the first call's prompt size times the number of calls, which is what
you get if you price an agent as "N calls".

### Results

| Run | Turns | Measured input tokens | AgentGuard | Naive (N x first call) |
|---|---|---|---|---|
| Constant sizes (every reply hits a 64-token cap) | 10 | 4,495 | 4,495 (+0.0%) | 580 (-87.1%) |
| Constant sizes (every reply hits a 64-token cap) | 40 | 70,180 | 70,180 (+0.0%) | 2,320 (-96.7%) |
| Constant sizes (every reply hits a 128-token cap) | 10 | 7,430 | 7,430 (+0.0%) | 590 (-92.1%) |
| Constant sizes (every reply hits a 128-token cap) | 40 | 120,920 | 120,920 (+0.0%) | 2,360 (-98.0%) |
| Varied sizes (questions of different lengths, replies end naturally) | 10 | 13,833 | 12,360 (-10.7%) | 570 (-95.9%) |
| Varied sizes (questions of different lengths, replies end naturally) | 40 | 232,760 | 206,640 (-11.2%) | 2,280 (-99.0%) |

**Constant sizes (every reply hits a 64-token cap).** Calibrated from turns 1-2: S = 35, U = 23, O = 64 tokens. Reply lengths over the run: 64-64 tokens. Error over turns 3-40: mean 0.0%, max 0.0%. At 40 turns: measured 70,180, predicted 70,180, naive 2,320.

**Constant sizes (every reply hits a 128-token cap).** Calibrated from turns 1-2: S = 35, U = 24, O = 128 tokens. Reply lengths over the run: 128-128 tokens. Error over turns 3-40: mean 0.0%, max 0.0%. At 40 turns: measured 120,920, predicted 120,920, naive 2,360.

**Varied sizes (questions of different lengths, replies end naturally).** Calibrated from turns 1-2: S = 23, U = 34, O = 228 tokens. Reply lengths over the run: 43-400 tokens. Error over turns 3-40: mean 10.9%, max 24.3%. At 40 turns: measured 232,760, predicted 206,640, naive 2,280.

With constant sizes the prediction is exact, which confirms the shape of the model (turn *k* re-sends the *k - 1* earlier turns) rather than its accuracy in general. The varied run is the realistic case: its error comes from calibrating on two turns that are not typical of the rest, which is the same uncertainty the `--input-tokens` and `--output-tokens` assumptions carry. The naive estimate only gets worse the longer the run: it is linear in
the number of turns, the real cost is quadratic.

## Speed

7,503 files, 1,912,978 lines in 154 s (12,413 lines/s) on a Windows laptop, single process, including parsing.
