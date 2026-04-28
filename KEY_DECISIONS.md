# Key Decisions

Persistent across runs. Records architectural decisions, conventions, and long-lived constraints.

## PEP 561 py.typed marker placement
- **Context**: TODO spec said "Add py.typed marker in SilverquiLLM-bench/". Reviewer noted repo-root placement isn't PEP 561 compliant.
- **Decision**: Place `py.typed` inside each distributed package (`engine/py.typed`, `cards/py.typed`) and include via `[tool.setuptools.package-data]`.
- **Reasoning**: Type checkers need the marker inside the installed package, not at repo root.
- **Impact**: engine/, cards/, pyproject.toml

## Python version: requires-python >= 3.10
- **Context**: TODO specified Python >=3.11, but build environment only has Python 3.10.12.
- **Decision**: Set `requires-python = ">=3.10"` in pyproject.toml. ruff.toml target-version remains py311.
- **Reasoning**: pip install -e . fails if requires-python exceeds available Python. Pragmatic deviation.
- **Impact**: pyproject.toml

