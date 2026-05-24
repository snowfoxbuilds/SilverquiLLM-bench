# AGENTS.md — Workspace Orientation

## Task

You are implementing SOS card implementations. Each card's implementation class
must be placed in its assigned file:

```
cards/sos/{card_id}/card_impl.py
```

## Hard Rules

1. **Card location invariant** — Each card's canonical implementation class must
   remain in `cards/sos/{card_id}/card_impl.py`. Do not move or rename card
   directories.

2. **Staged-test integrity** — Do not modify any files under `tests/engine/` or
   any FDN reference test files at `cards/fdn/*/tests.py`. These tests are for
   your local verification and learning only; the runner uses its own
   authoritative copies for grading. Modifying these tests will not change your
   score — it will only mislead you about whether your engine changes are
   correct.

3. **Additive-only engine modifications** — You may add new methods, classes,
   helpers, and files inside `engine/`. You may modify the bodies of existing
   functions to implement card behavior. You MUST NOT rename, move, or delete
   anything that already exists in `engine/` — no renaming, no refactoring.
   Restructuring the engine will break the grader's imports and zero your score.

These rules are derived from the project's Workspace Contract decisions
(maintained outside this workspace). They ensure deterministic grading.

## Test Commands

Run from the workspace root:

```bash
pytest
```

This discovers:
- FDN reference tests at `cards/fdn/{collector_number}/tests.py`
- Engine regression tests at `tests/engine/test_*.py`

The workspace `pytest.ini` configures `python_files = test_*.py tests.py` for
discovery of both patterns.

## Engine Extension Scope

- **May**: Add files, methods, classes, and helpers inside `engine/`.
- **May**: Modify the bodies of existing functions in `engine/`.
- **Must NOT**: Rename, move, or delete anything existing in `engine/`.

## Tools

Git is available. The workspace is initialized as a git repository at stage time.

## Navigation

See `PROJECT_MAP.md` for the directory layout.
