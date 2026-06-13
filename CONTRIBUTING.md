# Contributing

Thanks for your interest! `bricksafe` is small and safety-focused, so the bar is correctness +
clarity.

## Setup

```bash
uv venv && uv pip install -e ".[dev]"
uv run ruff check src tests examples
uv run mypy src
uv run pytest -q
```

All three must be green (CI runs exactly these). The library has **zero runtime dependencies** —
please keep it that way.

## Guidelines

- **Every safety change pairs with a test that proves the gate bites** (a negative control), not just
  the happy path. See `tests/test_bricksafe.py` for the pattern.
- Keep the public surface in `__init__.py` curated and typed (`mypy --strict`).
- Conventional-commit style summaries (`feat:`, `fix:`, `docs:`) are appreciated.
- A guard that can't prove safety should **refuse**, never assume success — preserve that posture.
