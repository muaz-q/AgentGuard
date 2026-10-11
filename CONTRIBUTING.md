# Contributing

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest && ruff check . && ruff format --check . && mypy
```

**Reporting a false positive or a miss:** open an issue with the smallest snippet that
reproduces it. Every rule change comes with a test in `tests/` built from such a snippet.

**Changing a rule:** re-run the benchmark and say in the PR how the numbers moved.

```bash
python bench/real_world.py --set tuning     # projects used while developing the rules
python bench/real_world.py --set holdout    # projects used only for measurement
```

New hold-out projects should be added before looking at their findings, not after.

**Prices:** `agentguard/data/prices.json` is USD per 1M tokens with an `as_of` date. Update the
date with the numbers and cite the source in the PR.
