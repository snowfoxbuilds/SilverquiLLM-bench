# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.

## Disagreement: Include Mystical Archives (SOA set, cn 1-65)
- **Reviewer comment (strict)**: Add a test that patches the fetch/cache paths and verifies `fetch_sos_data()` produces exactly 65 `set_code="soa"` cards with collector numbers 1-65.
- **Implementer justification**: The strict comment targets a test file, and the Implementer was instructed not to modify tests.
- **Coordinator decision**: accept reviewer; send the test gap to the Tester.
- **Reasoning**: The TODO's testability requirement is about the public fetch workflow, not only normalization helpers, so the test suite should exercise `fetch_sos_data()` with mocked network/cache paths.
- **Impact**: `tests/test_soa_mystical_archives.py`.

## Test failure: Item 2 — Include Special Guests (SPG set, cn 149-158)
- **Failing tests**: `TestStaleCacheRebuild::test_cache_with_soa_but_no_spg_triggers_rebuild`
- **Tester's intent**: A pre-existing `sos.json` output cache that has SOA but no SPG cards must be treated as stale and rebuilt so normal fetches satisfy the SPG requirement.
- **Implementer's approach**: The stale cache check intentionally remained SOA-only to preserve compatibility with item 1-era caches, with users expected to pass `--force` for SPG.
- **Coordinator decision**: fix implementation
- **Reasoning**: The TODO requires `fetch_data.py` to include SPG 149-158 in the SOS Draft Set output; relying on manual `--force` for an existing cache repeats the stale-cache issue caught for SOA and violates normal-fetch testability.

## Disagreement: Include Special Guests (SPG set, cn 149-158)
- **Reviewer comment (strict)**: Freshness checks must validate the exact SPG collector-number multiset/count, rejecting output or subset caches with duplicates or extra SPG rows.
- **Implementer justification**: The first revision validated the presence of all collector numbers 149-158 but did not enforce exact multiplicity or reject extras.
- **Coordinator decision**: accept reviewer; require final implementation revision.
- **Reasoning**: The TODO testability requirement says exactly 10 SPG cards with collector numbers 149-158. Presence-only validation can return corrupted caches with additional SPG rows or duplicates, so normal fetches could still violate the requirement.
- **Impact**: `benchmarks/sos/fetch_data.py`.

## Test failure: Item 2 — Prior SOA cache freshness test
- **Failing tests**: `TestFetchSosDataWorkflow::test_fresh_cache_with_soa_returns_cached`
- **Tester's intent**: Item 1 verified that a cache containing the required SOA subset was considered fresh.
- **Implementer's approach**: Item 2 correctly expanded cache freshness requirements to require the exact SPG 149-158 subset as well.
- **Coordinator decision**: fix tests
- **Reasoning**: After item 2, a cache with SOA but no SPG is intentionally stale. The prior test fixture must include the SPG subset to keep testing the fresh-cache short-circuit behavior.

## Disagreement: Enforce SOS base set draft cutoff at collector number 271
- **Reviewer comment (strict)**: Cached `sos.json` freshness should verify the complete SOS base collector-number set, not only absence of SOS collector numbers above 271.
- **Implementer justification**: Initial implementation filtered fresh fetches and rejected caches with above-cutoff SOS cards, but did not reject truncated SOS caches.
- **Coordinator decision**: accept reviewer; require implementation revision.
- **Reasoning**: The TODO requires final pool count 346, which implies 271 SOS base cards. A truncated cache with no above-cutoff cards would violate the count while passing absence-only validation.
- **Impact**: `benchmarks/sos/fetch_data.py`.

## Disagreement: SOS Draft Set exact output-cache freshness
- **Reviewer comment (strict)**: Cached `sos.json` freshness must validate the SOA subset exactly, not only `>=65` SOA rows, otherwise duplicate or extra SOA rows can make the final pool exceed 346.
- **Implementer justification**: The previous item 3 revision preserved the older SOA `>=65` check while tightening SOS and SPG.
- **Coordinator decision**: accept reviewer; require final implementation revision.
- **Reasoning**: Once the pool is fixed at 346 cards, all fixed subsets need exact collector-number validation for stale caches.
- **Impact**: `benchmarks/sos/fetch_data.py`; this reinforces the exact fixed-subset cache convention already in `KEY_DECISIONS.md`.

## Disagreement: Per-card audited conftest isolation
- **Reviewer comment (strict)**: FDN/SOS conftests still expose global registry fallbacks and do not reliably select the card under test from the per-card collector directory, including zero-padded FDN directories and set-prefixed SOS directories.
- **Implementer justification**: Initial fixes added collector lookup but retained broad class-name fallbacks for compatibility.
- **Coordinator decision**: accept reviewer; require final implementation revision.
- **Reasoning**: The audited-test contract requires one `card_impl` per collector directory. Global fallbacks can make wrong-card tests pass and hide broken directory mappings.
- **Impact**: `tests/audited/fdn/conftest.py`, `tests/audited/sos/conftest.py`, `tests/test_audited_infrastructure.py`.
