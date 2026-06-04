# SUMMARY — AUDITED-TEST-API operationalization (Phase 18 simulation-only migration)

Mission: implement the AUDITED-TEST-API.md test API, add a conformance test
enforcing that only the API touches the engine in audited tests, and migrate
all 10 old-paradigm SOS audited test suites to the simulation-only model.
**Zero changes to any workspace/canonical engine** (`benchmarks/sos/workspace/`
untouched — verified via `git diff`).

## Deliverable 1 — Test API (oracle `test_utils` mirror)

`benchmarks/sos/data/test_oracle_workspace/test_utils.py` now implements the
full allow-list, composed exclusively over canonical-public engine
entrypoints:

- **Setup** — `create_game(..., seed=None)` (seeds `game.rng`), expanded
  `set_board_state(..., library=, exile=, ...)` (`library` ordered, index 0 =
  top), new `set_player(game, idx, player)` (adopts scripts onto the existing
  player object so owner/controller/trigger references stay valid), and
  `PermanentSpec(name, tapped, summoning_sick, counters, damage_marked,
  attachments, controller)` with counters limited to canonical `+1/+1`,
  `-1/-1`, `loyalty`. No `set_stack` — stacked states are reached by casting.
- **Advance** — exactly two sanctioned advancers:
  - `priority_loop(game)`: host-side driver — SBAs each iteration, APNAP
    directive polling with retain-on-action, host-side execution through
    canonical `cast_spell`/`cast_spell_free`/`play_land`/`activate_ability`,
    single-object resolution when nobody acts, termination on empty stack +
    exhausted queues, `ScriptExhaustedError` on a dry directive queue while
    the stack is live.
  - `advance_to_phase(game, phase, step=None)`: fast-forwards turn structure,
    runs turn-based actions/triggers/cleanup per step entered, opens no
    priority windows; combat declarations and trigger-forced choices come
    from the choice script. Turn crossing raises (deferred capability).
- **DeterministicPlayer** — two explicit channels: directive queue (`script`)
  + choice script (`choices` = the canonical answer deque). Implemented as a
  `test_utils` subclass over the canonical constructor so it works against
  any candidate engine at eval time (see KEY_DECISIONS for why this deviates
  from the put-it-in-the-engine suggestion). Dry on either channel fails the
  test.
- **Directives/actions** — `no_op`, `perform_action`, `perform_illegal_action`
  (both `CastingError` and `AbilityError` are the rejection signal),
  `CastSpell(name, targets, x, mode, mana, from_zone)` (`from_zone != HAND`
  routes through the test-layer cast-from-exile helper; `mana=` pins the
  generic split via canonical `pay(cost, choices=...)`), `CastSpellFree`,
  `ActivateAbility(source, ability_index, targets)` (printed order:
  loyalty list for planeswalkers; mana abilities then activated abilities
  otherwise — mana abilities resolve straight into the pool), `PlayLand`.
- **Assertions** — the full Part-4 family: `assert_in_zone` (with count),
  `assert_zone_count`, `assert_zone_exact`, `assert_library_order`,
  `assert_tapped`, `assert_counters` (canonical keys only), `assert_damage`,
  `assert_power_toughness`, `assert_stack`, `assert_on_stack` (with count),
  `assert_stack_empty`, `assert_mana_pool` (full-pool match — the pool-delta
  basis), `assert_colors_spent`, `assert_life_total`. No `assert_mana_spent`.
- Legacy helpers (`cast_spell`, `resolve_top`, `declare_attackers/_blockers`,
  `set_*`, `assert_casting_error`, `card_colors`) remain for the oracle's own
  engine_tests and pre-Phase-18 suites; they are outside the audited
  allow-list and banned by the conformance test.

**Acceptance verified**: every allow-list symbol exists, is importable from
the oracle `test_utils`, and is exercised by at least one migrated test; no
new symbol outside the allow-list was introduced.

## Deliverable 2 — Conformance meta-test

`benchmarks/sos/data/test_oracle_workspace/tests/audited/test_api_conformance.py`
AST-scans every `tests/audited/**/sos_*/tests.py` (oracle authoring tree +
the canonical copies of the same collector dirs) and fails with `file:line +
symbol + reason` listings on:

- banned advancers/shortcuts (`game.run`, `run_game`, `run_turn`,
  `cast_spell`, `resolve_top`, `_resolve_top_of_stack`, ...),
- card-internal probes (`on_resolve`, `register_triggers`, `get_targets`,
  `get_cost_reduction`, ...) called from a test,
- private-attribute poking (any leading-underscore attribute access; `self.*`
  and fixture-card `__init__` excepted),
- engine-touching calls outside the allow-list (curated list incl. engine
  machinery, zone/pool mutators, choice methods, machinery constructors, and
  the old non-allow-list helpers).

Imports are never flagged (the import-boundary decision), and hook bodies of
fixture card classes defined inside a test file are exempt (they are
card-impl code). A planted-violation fixture test proves the guard fires on
every category, and a clean canonical-shape fixture proves zero false
positives. `tests/test_audited_api_conformance.py` wraps the same module so
the repo CI run (`pytest tests/`) gates on it.

## Deliverable 3 — Migration of all 10 audited suites

All of sos_1, sos_4, sos_13, sos_57 (flagship), sos_97, sos_120, sos_201,
sos_226, sos_245, sos_257 rewritten to
`create_game → set_board_state → set_player(DeterministicPlayer(script=...,
choices=...)) → priority_loop / advance_to_phase → assert_*`, validated green
against their oracle impls via `tests/test_audited_against_reference.py`,
then copied byte-identical to `benchmarks/sos/data/tests/audited/sos/`.
Card-specific notes honored: sos_57 refund via pool deltas with the
opponent's spell cost pinned; sos_4 converge pinned by mana-minimality +
`assert_colors_spent`; sos_97 loyalty by printed index, seeded-RNG
re-derivation, `perform_illegal_action` for once-per-turn; sos_257 prowess
reset via `advance_to_phase(ENDING, CLEANUP)` with P/T asserted before/after;
sos_201 miracle yes/no from the choice script with mana-minimality proving
the alt cost; sos_226 casualty answered via public `choose` with the doubled
result asserted; sos_245 affinity via reduced-cost outcomes; sos_13 back face
cast from exile via `CastSpell(from_zone=Zone.EXILE)`; sos_1/sos_120
spell-to-exile end-state assertions, never a mid-cascade stack; combat
(sos_1, sos_245) scripted on the choice channel with illegal blocks asserted
by outcome.

## Oracle-side changes (canonical untouched)

- `engine/casting.py`: `_handle_casualty` prompts via public `choose()` (the
  owed change) + counters-aware power threshold; all three cast paths fire
  `SpellCastTriggeredEvent` (additive).
- `engine/state_based_actions.py`: creature SBAs skip permanents that declare
  non-creature `card_types` (fixes the unanimated Great Hall dying to a
  zero-toughness SBA pass).
- `cards/sos/sos_120/card_impl.py`: Paradigm hooks registered in `on_cast`;
  copies flagged and hook-free.
- `cards/sos/sos_226/card_impl.py`: `casualty_grant` as a property → the
  harness no longer stub-skips sos_226 (all 10 cards now actually run).
- Two oracle `engine_tests` files updated to the post-Phase-18
  `advance_to_phase` semantics.

## Verification

- `tests/test_audited_against_reference.py`: **10/10 cards green** (sos_226
  included for the first time).
- Conformance: green on the migrated suite, red on planted violations
  (fixture-proved), wired into CI via `tests/`.
- Full repo suite: **1938 passed, 5 skipped** — no regressions.
- Oracle workspace `engine_tests`: 1141 passed; only the 4 failures already
  present at baseline HEAD remain (pre-existing, unrelated).
- `git diff` touches **nothing** under `benchmarks/sos/workspace/`.
- Ruff clean on all new/rewritten files (remaining findings in touched engine
  files pre-date this work).

Key decisions and consciously dropped coverage are logged in
`KEY_DECISIONS.md`.
