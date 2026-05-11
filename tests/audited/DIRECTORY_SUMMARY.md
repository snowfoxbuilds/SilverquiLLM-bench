# Directory Summary — `tests/audited/`

## Purpose

Per-card audited test directories for MTG card implementations. Each card has a numbered directory containing a `tests.py` file with card-specific behavioral tests. Tests import card implementations via a synthetic `card_impl` module injected by per-set `conftest.py` files.

## Subdirectories

| Directory | Contents |
|-----------|----------|
| `fdn/` | **FDN (Foundations) audited tests** — 260+ card test directories (by collector number). Each directory has `tests.py` testing the card against its FDN implementation from `cards/foundations/`. Conftest uses `CardRegistry` to auto-inject `card_impl`. |
| `sos/` | **SOS Draft Set audited tests** — 346 card test directories (by collector key: `1/`–`271/` for SOS base, `soa_1/`–`soa_65/` for SOA, `spg_149/`–`spg_158/` for SPG). Conftest uses `cards.stubs.sos_stubs` for auto-injection. |

## Key Files

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package init for audited tests root. |
| `fdn/conftest.py` | Per-card `card_impl` injection via collector-directory detection and `CardRegistry` class-name mapping. Does not override evaluator-provided `card_impl.py`. |
| `sos/conftest.py` | Per-card `card_impl` injection from `cards.stubs.sos_stubs` via `register_sos_stubs(registry)`. Restricts plain numeric collector keys to SOS base cards; SOA/SPG use set-prefixed keys. |

## Testing Approach

- **Per-card isolation**: Each card's tests live in their own directory (`{collector_number}/tests.py`).
- **Synthetic module injection**: `conftest.py` creates a `card_impl` module in `sys.modules` at collection time, exposing the card class under its class name.
- **Evaluator compatibility**: When an evaluator provides an explicit `card_impl.py` on `PYTHONPATH`, conftest defers to it.
- **pytest config**: `pyproject.toml` sets `python_files = ["tests.py"]` and `addopts = "--import-mode=importlib"` for subdir support.
