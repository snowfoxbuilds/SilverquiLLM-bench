# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.

## Test failure: Item 2 — Wire SBA trigger queueing
- **Failing tests**: test_creature_dies_event_fires_on_lethal_damage, test_creature_dies_event_fires_on_zero_toughness, test_multiple_creatures_dying_all_triggers_queued, test_sba_loop_repeats_when_triggers_queued, test_death_trigger_source_matches_dying_creature
- **Tester's intent**: Death triggers registered on the dying creature itself must fire — events should fire BEFORE unregistration so self-referencing "when this creature dies" triggers work. This matches MTG rules where death triggers use last-known-information.
- **Implementer's approach**: Fires events AFTER `unregister()`, matching `game.py`'s `destroy()`/`sacrifice()` pattern. Self-referencing triggers can't fire because they're already unregistered.
- **Coordinator decision**: fix implementation — fire events before unregistration
- **Reasoning**: MTG rules 603.10 specify "when this creature dies" triggers use last-known-information and must fire. The Tester's tests correctly model this behavior. The Implementer must reorder: fire events first, then unregister.


## Disagreement: Item 4 — Vanilla creatures batch
- **Reviewer comment (strict)**: Cards are not real FDN printings. Collector numbers are fabricated.
- **Implementer justification**: Tests hardcode these exact card names/numbers, so implementation must match tests. Implementer cannot modify test files.
- **Coordinator decision**: accept reviewer — both implementation AND tests need rewriting with correct FDN data
- **Reasoning**: The Implementer originally used non-FDN cards (Glory Seeker, Colossal Dreadmaw, etc.) which don't exist in FDN. The Tester mirrored incorrect data. Both need correction. Will direct Tester to rewrite tests with real Scryfall FDN data, then Implementer to match.
- **Impact**: `cards/foundations/vanilla_creatures_batch2.py`, `tests/cards/test_vanilla_creatures_batch2.py`

## Spec deviation: Item 4 — Vanilla creatures batch
- **TODO spec expected**: ~25–30 vanilla/French vanilla creatures
- **Actual codebase state**: Only 7 real FDN vanilla/French vanilla creatures remained unimplemented (Fire Elemental, Gigantosaurus, Quakestrider Ceratops, Elementalist Adept, Skyraker Giant, Swiftblade Vindicator, Zetalpa Primal Dawn)
- **What was implemented instead**: 7 creatures verified against Scryfall FDN data
- **Impact**: `cards/foundations/vanilla_creatures_batch2.py`, batch is smaller than estimated but complete
