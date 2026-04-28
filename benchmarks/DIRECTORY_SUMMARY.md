# Directory Summary — `benchmarks/`

## Purpose

Namespace package for benchmark data sets. Each subdirectory (`sos/`, etc.) contains card data, generated specs, and result artifacts for a specific MTG set used in benchmarking. The runner code in `benchmark/` is set-agnostic; this directory holds set-specific data.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `sos/` | Shadows over Sonnenthal (SOS) benchmark set — 368 cards. See `benchmarks/sos/DIRECTORY_SUMMARY.md`. |

## Convention

- Each set directory follows the pattern: `data/` (raw card data + rules), `cards/` (per-card specs), `results/` (benchmark outputs).
- The `__init__.py` files make this a proper Python namespace package.
