# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.

## Test failure: Item 2 — Wire SBA trigger queueing
- **Failing tests**: test_creature_dies_event_fires_on_lethal_damage, test_creature_dies_event_fires_on_zero_toughness, test_multiple_creatures_dying_all_triggers_queued, test_sba_loop_repeats_when_triggers_queued, test_death_trigger_source_matches_dying_creature
- **Tester's intent**: Death triggers registered on the dying creature itself must fire — events should fire BEFORE unregistration so self-referencing "when this creature dies" triggers work. This matches MTG rules where death triggers use last-known-information.
- **Implementer's approach**: Fires events AFTER `unregister()`, matching `game.py`'s `destroy()`/`sacrifice()` pattern. Self-referencing triggers can't fire because they're already unregistered.
- **Coordinator decision**: fix implementation — fire events before unregistration
- **Reasoning**: MTG rules 603.10 specify "when this creature dies" triggers use last-known-information and must fire. The Tester's tests correctly model this behavior. The Implementer must reorder: fire events first, then unregister.

