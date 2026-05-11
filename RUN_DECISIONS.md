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

## Disagreement: SOS stub basic attribute completeness
- **Reviewer comment (strict)**: Generated SOS stubs lose hybrid mana costs, omit planeswalker loyalty, and omit P/T for vehicles/noncreature cards with printed power/toughness.
- **Implementer justification**: Initial stubs focused on common base classes and treated unsupported mana symbols conservatively.
- **Coordinator decision**: accept reviewer; require final implementation revision.
- **Reasoning**: The TODO explicitly requires basic attributes from Scryfall data. Hybrid mana, loyalty, and vehicle P/T are basic printed attributes and audited tests should fail on behavior gaps rather than incorrect basics.
- **Impact**: `scripts/generate_audited_stubs.py`, `cards/stubs/sos_stubs.py`, `tests/test_sos_stubs.py`.

## Test failure: Item 6 — Unsupported hybrid mana should not zero CMC
- **Failing tests**: `test_unsupported_hybrid_does_not_zero_cmc`
- **Tester's intent**: A card with two-brid mana such as `{2/R}` must not collapse the entire generated mana cost to empty/CMC 0.
- **Implementer's approach**: The final revision preserved simple hybrid symbols but still missed unsupported hybrid-like symbols.
- **Coordinator decision**: fix implementation
- **Reasoning**: The TODO requires basic mana attributes from Scryfall data; preserving a nonzero mana value for unsupported special symbols is better than silently making the card free.

## Disagreement: FDN Batch 1 audited behavior coverage
- **Reviewer comment (strict)**: Basic lands lack untap tests, vanilla creatures lack casting/combat tests, and French-vanilla cards only assert keyword flags rather than exercising keyword behavior.
- **Implementer justification**: Initial batch prioritized broad per-card file coverage and static correctness across the card list.
- **Coordinator decision**: accept reviewer; require test revision.
- **Reasoning**: The TODO explicitly requires behavior coverage for land untapping, vanilla casting/combat, and each French-vanilla keyword.
- **Impact**: `tests/audited/fdn/*/tests.py` for Batch 1 card directories. Tester revisions added land untap tests, vanilla casting/combat behavior, and French-vanilla keyword behavior including trample and indestructible coverage.

## Disagreement: FDN Batch 2 audited spell coverage gaps
- **Reviewer comment (strict)**: Several in-scope spells are missing entirely or lack important mode, targeting, counterspell, token, sacrifice/life, and X>=10 behavior coverage.
- **Implementer justification**: Initial batch created broad per-card spell coverage but skipped collector collisions and some branches.
- **Coordinator decision**: accept reviewer; require test revision.
- **Reasoning**: The TODO requires per-card audited tests for all in-scope simple instants/sorceries and independent coverage for modal/kicker/X-cost behavior.
- **Impact**: `tests/audited/fdn/*/tests.py` for Batch 2 spell directories and potentially FDN audited conftest collector mapping for collision handling.

## Test failure: Item 8 — Felling Blow and counterspell fizzle behavior
- **Failing tests**: `TestFellingBlowResolution::test_adds_plus_one_counter_to_own_creature`, `TestFellingBlowResolution::test_own_creature_takes_fight_damage`, `TestEssenceScatterResolution::test_fizzle_when_target_gone`, `TestCancelResolution::test_fizzle_when_target_gone`
- **Tester's intent**: Felling Blow should add the +1/+1 counter before fight damage, and counterspells resolving against missing stack targets should fizzle without moving the missing target card to graveyard.
- **Implementer's approach**: Existing spell implementations do not satisfy the stricter audited behavior assertions.
- **Coordinator decision**: partial: fix implementation for the counter and counterspell fizzle behavior, but fix the Felling Blow test that incorrectly expected reciprocal fight damage.
- **Reasoning**: Felling Blow's text is one-way damage after adding the counter, not a fight. The counter and target-damage assertions are valid; reciprocal source damage is not. Counterspell fizzle assertions align with the TODO's resolution/fizzle coverage.

## Disagreement: Felling Blow one-way damage semantics
- **Reviewer comment (strict)**: Felling Blow should not deal reciprocal damage to the source creature, and the audited test should not enforce mutual fight damage.
- **Implementer justification**: The first implementation fix followed the strengthened test expectation for mutual fight damage.
- **Coordinator decision**: accept reviewer; fix implementation and test.
- **Reasoning**: The card's rules text says the source creature deals damage to the opponent's creature; it does not say those creatures fight.
- **Impact**: `cards/foundations/simple_spells_batch3.py`, `tests/audited/fdn/105b/tests.py`.

## Disagreement: FDN Batch 3 audited trigger and activated coverage gaps
- **Reviewer comment (strict)**: Several activated-ability tests only assert ability presence, and several death-trigger tests are tautological/no-assertion or test the wrong trigger condition.
- **Implementer justification**: Initial batch prioritized broad per-card file coverage and basic behavior smoke tests.
- **Coordinator decision**: accept reviewer; require test revision.
- **Reasoning**: The TODO explicitly requires observable activated ability costs/effects and death trigger behavior/conditions where practical.
- **Impact**: `tests/audited/fdn/*/tests.py` for Batch 3 card directories.

## Disagreement: FDN Batch 4 audited permanent coverage gaps
- **Reviewer comment (strict)**: Crystal Barricade was missing; aura SBA detach, equipment activation/death persistence, artifact activated abilities, planeswalker loyalty/legend-rule behavior, and global enchantment leave-battlefield behavior needed stronger tests.
- **Implementer justification**: Initial batch prioritized broad per-card coverage and static assertions for some cards.
- **Coordinator decision**: accept reviewer; require test revision.
- **Reasoning**: The TODO explicitly calls for behavioral coverage across these permanent classes where engine-supported, not only per-card file presence.
- **Impact**: `tests/audited/fdn/*/tests.py` for Batch 4 card directories and `tests/audited/fdn/conftest.py`.

## Disagreement: FDN Batch 5 audited SPG/remaining coverage gaps
- **Reviewer comment (strict)**: Condemn, Sphinx's Tutelage, Paradise Druid, Akroma's Memorial, Fiend Artisan, remaining modal spells, and remaining complex creatures needed observable behavior assertions instead of metadata or registration-only checks.
- **Implementer justification**: Initial batch prioritized completing full registry coverage and used lighter tests for some complex remaining cards.
- **Coordinator decision**: accept reviewer; require test revision.
- **Reasoning**: The TODO specifically calls out SPG cards as complex Phase 5 coverage and requires remaining cards to have meaningful per-card audited behavior checks where engine-supported.
- **Impact**: `tests/audited/fdn/74`, `75b`, `80`, `81b`, `83`, `822`-`829`, `99`, `133`, `224`, `568`, `713`.

## Spec deviation: Item 11 — FDN audited test file count
- **TODO spec expected**: 301 FDN audited test files for FDN 001-291 plus SPG 074-083.
- **Actual codebase state**: The current CardRegistry exposes 264 unique registered FDN/SPG card implementations after loading the foundations registry modules.
- **What was implemented instead**: Created/verified one audited test directory for every registered FDN/SPG implementation, reaching 264/264 registry-backed coverage.
- **Impact**: `tests/audited/fdn/`, `tests/audited/fdn/conftest.py`; future additions to the FDN registry must add corresponding audited tests.

## Test failure: Item 12 — SOS audited tests Batch 1 expected stub failures
- **Failing tests**: 20 ability behavior tests fail against SOS stubs after revision; no import, syntax, collection, or basic-attribute errors.
- **Tester's intent**: Keep behavior assertions for simple SOS cards that define the audited contract for real implementations, including `on_resolve`, triggers, activated abilities, token creation, draw, mill, discard, sacrifice, and search behavior.
- **Implementer's approach**: Created the full trivial/simple file set and initially reported one expected stub failure; Tester rewrote weak tests into stronger behavior checks and then fixed reviewer-identified setup/spec issues.
- **Coordinator decision**: accept tests and proceed with expected stub failures documented.
- **Reasoning**: The TODO explicitly states SOS tests run against stubs and most ability tests may fail because stubs only provide basic attributes. Removing those assertions would undermine audited evaluation quality.

## Disagreement: SOS Batch 1 audited test setup/spec correctness
- **Reviewer comment (strict)**: Twelve simple-card tests had wrong expectations or incomplete setup, including missing X values, wrong searched card types, wrong tutor destination, missing sacrifice preconditions, and test-count violations.
- **Implementer justification**: Initial and first Tester rewrite prioritized broad meaningful behavior checks but some assertions did not exactly match the card specs.
- **Coordinator decision**: accept reviewer; require test revision.
- **Reasoning**: Expected stub failures are acceptable only when the audited test describes correct oracle behavior with valid setup. Tests that would fail a correct implementation must be fixed.
- **Impact**: `tests/audited/sos/50`, `158`, `184`, `202`, `249`, `soa_25`, `soa_33`, `soa_34`, `soa_35`, `soa_48`, `soa_49`, `soa_62`.

## Test failure: Item 13 — SOS audited tests Batch 2 expected stub failures
- **Failing tests**: 369 ability tests and 45 basic keyword tests fail against SOS stubs after revision; no import, syntax, or collection errors.
- **Tester's intent**: Keep behavior and keyword assertions for medium SOS cards as the audited contract for real implementations.
- **Implementer's approach**: Created 156 medium-card test files and the Tester strengthened weak generated patterns into observable behavior checks.
- **Coordinator decision**: accept tests and proceed with expected stub failures documented.
- **Reasoning**: SOS stubs intentionally omit oracle behavior and some keyword data. The audited tests should expose those gaps rather than weaken assertions.

## Disagreement: SOS Batch 2 generated test quality
- **Reviewer comment (strict)**: Generated tests included no-assertion `on_resolve()` calls, inherited-method `hasattr` checks, tautological setup/object-identity interactions, incomplete flashback assertions, and Harsh Annotation target/controller mistakes.
- **Implementer justification**: Initial batch generated broad coverage at scale and relied on template patterns for interactions and edge tests.
- **Coordinator decision**: accept reviewer; require batch-wide test revision.
- **Reasoning**: Expected stub failures are acceptable, but tests must still assert correct observable behavior and must not count no-op or tautological checks toward the 8-15 requirement.
- **Impact**: `tests/audited/sos/*/tests.py` for Item 13 medium-card directories.

## Test failure: Item 14 — SOS audited tests Batch 3 expected stub failures
- **Failing tests**: Ability, edge, and interaction tests fail against SOS stubs for card-specific behavior such as ETB effects, attack triggers, converge scaling, infusion conditions, opus triggers, and spell resolution.
- **Tester's intent**: Keep complex/expert behavior assertions as the audited contract for real implementations while ensuring no collection/import errors.
- **Implementer's approach**: Created 140 complex/expert test files and the Tester rewrote generated placeholders into oracle-derived assertions.
- **Coordinator decision**: accept tests and proceed with expected stub failures documented.
- **Reasoning**: SOS stubs intentionally omit oracle behavior. The audited complex/expert tests should expose those gaps and preserve benchmark signal.

## Disagreement: SOS Batch 3 generated placeholder quality
- **Reviewer comment (strict)**: Generated complex/expert tests still contained unconditional `pytest.fail` placeholders, inherited-method `hasattr` checks, no-assertion try/except paths, and generic fixture interaction tests.
- **Implementer justification**: Initial generation prioritized complete 346/346 coverage and broad category scaffolding across 140 complex cards.
- **Coordinator decision**: accept reviewer; require batch-wide test revision.
- **Reasoning**: Placeholder failures would fail even correct implementations, and inherited/generic assertions do not test the card oracle. Expected stub failures must come from meaningful state assertions, not placeholders.
- **Impact**: `tests/audited/sos/*/tests.py` for Item 14 complex/expert directories.

## Disagreement: Per-card audited eval result persistence
- **Reviewer comment (strict)**: `--audited-dir` wrote only flat run-level results and skipped the evaluator helper's missing-implementation path due to CLI pre-checks.
- **Implementer justification**: Initial implementation reused the existing flat eval result append flow and avoided calling per-card eval when implementation files were absent.
- **Coordinator decision**: accept reviewer; require implementation revision.
- **Reasoning**: The TODO target explicitly requires per-card `result.json` updates, and missing implementations should be recorded as audited errors rather than silently omitted.
- **Impact**: `silverquillm/cli.py`, `tests/test_audited_per_card.py`.
