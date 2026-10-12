# Changelog

## 0.3.0 - 2026-10-12

The package is now published as `agentguard` (`pip install agentguard`). Versions up to
0.2.3 were published as `agentguard-cli`; that name is no longer updated.

A rewrite. 0.2.x produced cost figures that could not be trusted and had several broken
basics; 0.3.0 reports located, rule-based findings and a cost model checked against
measured runs.

### Breaking

- Output is now `file:line:col: RULE [severity] message`. Use `--format json` for the
  machine-readable report; its schema is versioned (`schema_version: 1`).
- Exits 1 when a finding is at or above `--fail-on` (default `high`). Use `--fail-on never`
  for the old always-0 behaviour.
- The default pricing model is `claude-sonnet-5-5`; each call is priced at the model named in
  the code when there is one.
- `--dag` is removed. JavaScript/TypeScript files are no longer listed as "scanned" (they
  were never analysed).
- The old flags (`--root_dir`, `--json`, `--json_out`, `--input_tokens`, `--output_min`,
  `--output_max`, `-q`) still work.

### Fixed

- `--json` printed debug lines before the JSON, so the output never parsed.
- A debug print crashed piped output on Windows (cp1252 console).
- The standard agent loop - call, then append the reply - was never reported as history
  growth, because only appends before the call were seen.
- LangChain `llm.invoke(q)`, `async for` loops and history inside f-strings were missed.
- `subprocess.run(..., input=x)` was counted as an LLM call.
- Long docstrings were reported as large prompts.
- Cost model: a file name containing "agent" multiplied the cost by about 17; re-sent
  history was billed at the output rate; `range(3)` was simulated as 100 iterations; caching
  "savings" was always 60%; prices were from 2024.

### Added

- Rules AG001-AG007 with fixes, severities, inline suppression and `[tool.agentguard]` config.
- Calls are followed through helper functions, methods and imports across files.
- Loop bounds from the code: literals, constants, step caps, countdowns, retry iterators.
- SARIF 2.1.0 output for GitHub code scanning, Markdown output for PR summaries.
- A GitHub Action, a pre-commit hook, and `--prices` for LiteLLM's price file.
- Benchmarks: precision on 22 open-source agent projects, token model checked against
  measured Ollama runs.
