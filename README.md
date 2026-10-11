# 🛡 AgentGuard

**Pre-execution cost estimator for agentic AI systems**

AgentGuard analyzes your multi-file agentic codebase and estimates the **minimum and maximum possible LLM API cost** — _without running any code or calling any APIs_.

## Install

```bash
pip install -e .
```

## Usage

```bash
agentguard --root_dir ./my_agent
agentguard --root_dir ./my_agent --model claude-3-5-sonnet
agentguard --root_dir ./my_agent --input_tokens 400 --output_max 1000
agentguard --root_dir ./my_agent --json_out report.json
agentguard --root_dir ./my_agent --quiet --dag
```

## What It Detects

- API calls inside loops (cost multiplies with iteration count)
- Nested loops (exponential scaling)
- Missing loop depth limiters (unbounded execution)
- Repeated prompts (caching opportunity)
- Large static prompts (high baseline cost)
- High-complexity tasks (reasoning tax ×20)

## Supported Models

gpt-4o, gpt-4o-mini, gpt-4-turbo, claude-3-5-sonnet, claude-3-haiku,
claude-3-opus, gemini-1.5-pro, gemini-1.5-flash

## Architecture

CLI → Crawler → Analyzer (AST/regex) → Simulator (math model) → Reporter
