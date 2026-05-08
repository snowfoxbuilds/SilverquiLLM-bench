# Directory Summary — `benchmarks/sos/`

## Purpose

Benchmark data and artifacts for the **Shadows over Sonnenthal (SOS)** set — 368 cards fetched from Scryfall. Contains raw card data, classified tiers (with both `tier` and `complexity_tier` keys), per-card specs, comprehensive rules, prototype card selections, and result output directories.

## Key Files

| Path | Responsibility |
|------|---------------|
| `__init__.py` | Package init for SOS benchmark set. |
| `fetch_data.py` | SOS data fetcher — downloads from Scryfall, normalizes card fields. |
| `prototype_cards.json` | 5 prototype cards (one per complexity tier) with both `tier` and `complexity_tier` fields. |
| `prototype_gaps.md` | Engine gap analysis — documents missing engine features for prototype cards. |

## Subdirectories

| Directory | Contents |
|-----------|----------|
| `data/` | Raw and processed data files. |
| `cards/` | Per-card directories (`1/` through `368/`), each containing `card_spec.json`. |
| `results/` | Benchmark run outputs (per-run isolated directories). |

## Data Files (`data/`)

| File | Responsibility |
|------|---------------|
| `sos.json` | Normalized SOS card data — 368 cards. |
| `sos_classified.json` | Classification output with both `tier` and `complexity_tier` fields. |
| `comprehensive_rules.txt` | Cached MTG comprehensive rules text. |
| `rules_overview.md` | Compact MTG rules overview (~573 tokens) for agent context. |
