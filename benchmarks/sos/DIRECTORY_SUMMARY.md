# Directory Summary — `benchmarks/sos/`

## Purpose

Benchmark data and artifacts for the **Shadows over Sonnenthal (SOS)** Draft Set — 346 cards (271 SOS base + 65 SOA Mystical Archives + 10 SPG Special Guests) fetched from Scryfall. Contains raw card data, classified tiers (with both `tier` and `complexity_tier` keys), per-card specs, comprehensive rules, prototype card selections, and result output directories.

## Key Files

| Path | Responsibility |
|------|---------------|
| `__init__.py` | Package init for SOS benchmark set. |
| `fetch_data.py` | SOS data fetcher — downloads SOS base (cn 1-271), SOA (cn 1-65), and SPG (cn 149-158) from Scryfall. `SOS_BASE_MAX_COLLECTOR_NUMBER=271` cutoff. Stale cache invalidation, merge into sos.json, set breakdown logging. |
| `prototype_cards.json` | 5 prototype cards (one per complexity tier) with both `tier` and `complexity_tier` fields. |
| `prototype_gaps.md` | Engine gap analysis — documents missing engine features for prototype cards. |

## Subdirectories

| Directory | Contents |
|-----------|----------|
| `workspace/` | **Canonical agent workspace** — copied as-is into Docker containers. Contains engine/, cards/, tests/, RULEBOOK.txt, pytest.ini, AGENTS.md. See `benchmarks/sos/workspace/` summaries. |
| `data/` | Raw and processed data files, plus `tests/audited/` (FDN/SOS audited test suites). |
| `cards/` | Per-card directories (`1/`–`271/` for SOS, `soa_1/`–`soa_65/` for SOA, `spg_149/`–`spg_158/` for SPG), each containing `card_spec.json`. |
| `results/` | **Deprecated.** Benchmark results are now stored under `docker/<image_dir>/results/`. |

## Data Files (`data/`)

| File | Responsibility |
|------|---------------|
| `sos.json` | Normalized SOS Draft Set card data — 346 cards (271 SOS + 65 SOA + 10 SPG). |
| `sos_classified.json` | Classification output with both `tier` and `complexity_tier` fields. |
| `comprehensive_rules.txt` | Cached MTG comprehensive rules text. |
| `rules_overview.md` | Compact MTG rules overview (~573 tokens) for agent context. |
