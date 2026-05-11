# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Include Mystical Archives (SOA set, cn 1-65)

### Implementation
- `cards/scryfall.py` — Added `fetch_scryfall_query()` for arbitrary Scryfall search queries with pagination
- `benchmarks/sos/fetch_data.py` — Added SOA fetch (cn 1–65), merge into sos.json, stale cache invalidation when SOA cards missing, set breakdown logging
- `silverquillm/card_classifier.py` — Added `set_code` field to classified JSON output records
- `silverquillm/card_spec.py` — Composite key lookup for tier_info (no plain-cn overwrite), set_code-prefixed output dirs for multi-set collision avoidance


## Item 2: Include Special Guests (SPG set, cn 149-158)

### Implementation
- `benchmarks/sos/fetch_data.py` — Added SPG cn 149-158 fetch with query-specific cache, collector-number filtering, merge into sos.json, and stale output cache validation requiring SPG 149-158 presence

## Item 3: Enforce SOS base set draft cutoff at collector number 271

### Tests
- `tests/test_sos_base_cutoff.py` — 13 tests for SOS base cutoff at cn 271, cache freshness, total count 346

### Implementation
- `benchmarks/sos/fetch_data.py` — Added SOS_BASE_MAX_COLLECTOR_NUMBER=271 constant, filter SOS cards to collector_number<=271 after fetch, and full SOS completeness check (exact cn 1-271 set) in output-cache freshness validation

## Item 4: Re-run classification and spec generation on updated card pool

### Tests
tests/test_sos_regenerated_artifacts.py — 26 tests for 346-card pool integrity, classification, specs, docs

### Implementation
- `benchmarks/sos/data/sos.json` — Regenerated with 346 cards from real Scryfall data (271 SOS base + 65 SOA + 10 SPG)
- `benchmarks/sos/data/sos_classified.json` — Regenerated classification for all 346 cards with set_code and complexity_tier
- `benchmarks/sos/cards/soa_1/` through `soa_65/` — 65 SOA spec dirs (force-added, gitignored by benchmarks/*)
- `benchmarks/sos/cards/spg_149/` through `spg_158/` — 10 SPG spec dirs (force-added, gitignored by benchmarks/*)
- `benchmarks/sos/cards/272/` through `368/` — Deleted stale SOS dirs above cn 271
- `data/sets/soa_cn1-65.json` — Real SOA subset cache from Scryfall (65 cards)
- `data/sets/spg_cn149-158.json` — Real SPG subset cache from Scryfall (10 cards, filtered out 158a variant)
- `benchmarks/DIRECTORY_SUMMARY.md` — Updated card count from 368 to 346
- `README.md` — Card count references already at 346
- `PROJECT_MAP.md` — Card count references already at 346
- `benchmarks/sos/DIRECTORY_SUMMARY.md` — Already at 346
