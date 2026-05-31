# Directory Summary — `benchmarks/`

## Purpose

Namespace package for benchmark data sets. Each subdirectory (`sos/`, etc.) contains card data, generated specs, and result artifacts for a specific MTG set used in benchmarking. The runner code in `silverquillm/` is set-agnostic; this directory holds set-specific data.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `sos/` | Secrets of Strixhaven (SOS) benchmark set — 346 cards (271 SOS base + 65 SOA + 10 SPG). See `benchmarks/sos/DIRECTORY_SUMMARY.md`. |

## Convention

- Each set directory follows the pattern: `data/` (raw card data + rules), `cards/` (per-card specs).
- Benchmark results are now stored under `docker/<image_dir>/results/` rather than inside each set directory.
- The `__init__.py` files make this a proper Python namespace package.
