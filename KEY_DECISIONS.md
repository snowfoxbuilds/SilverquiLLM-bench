# Key Decisions

Persistent architectural and convention decisions across runs. Periodically drained into specs/ADRs

## Docker stdout/stderr direct-write carve-out

`_drain_pipe` in `silverquillm/runner.py` streams Docker stdout/stderr directly to
`run_dir/docker_stdout.log` and `run_dir/docker_stderr.log` in real time (append mode,
line-buffered, UTF-8 with error replacement). This intentionally breaks the general
`.tmp` → `.log` → harvest-copy convention used by other output files. The `.tmp` files
in `output/` are still written for backward compatibility and local diagnostics, but
the authoritative real-time logs live in `run_dir`. `_harvest_results` in `cli.py`
skips these two files since they are already present in `run_dir`.


## Oracle workspace stub detection uses AST parsing

- **Context**: The harness needs to detect which `card_impl.py` files are real oracle implementations vs empty stubs.
- **Decision**: `_is_stub_impl()` uses Python's AST module to check if any class defines a non-dunder method (e.g., `on_resolve`, `can_cast`, `get_targets`). Classes that only have `__init__` with attribute assignments are still stubs.
- **Reasoning**: Simple text-matching or regex could be fooled. AST parsing is robust and aligns with the semantics: a card impl is "real" when it defines game logic methods.
- **Impact**: `tests/test_audited_against_reference.py`

## resolve_top() vs _resolve_top_of_stack() semantics

- **Context**: The oracle workspace `test_utils.py` needed both a "resolve one stack object" helper and the existing "drain full stack" behavior.
- **Decision**: `resolve_top()` resolves exactly one stack object (pop + resolve + SBA). `_resolve_top_of_stack()` drains the entire stack with a while loop. `cast_spell()` uses `_resolve_top_of_stack()` to drain all triggers.
- **Reasoning**: Tests need fine-grained control (resolve one thing at a time) while `cast_spell()` needs the convenience of auto-draining.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/test_utils.py`


## Spell-to-graveyard replacement effect mechanism (oracle workspace engine)

- **Context**: Cards that route spells to exile on resolution (instead of graveyard) need the engine to consult replacement effects during spell resolution.
- **Decision**: Modified `_resolve_spell` in oracle workspace's `engine/casting.py` to fire a `_SpellToGraveyardReplacementEvent` and consult the `ReplacementManager` before moving instant/sorcery spells to graveyard. The replacement's `destination` field determines actual zone.
- **Reasoning**: Without this, registered replacement effects had no actual effect on the engine's resolution path.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/engine/casting.py` — oracle workspace only (ADR-010).

## Attack trigger targeting uses condition-callback lock-in

- **Context**: "Whenever ~ attacks, you may target..." triggers need targets locked when put on stack, not on resolution.
- **Decision**: Targets are locked in during the trigger's condition callback (closest available hook to "ability goes on stack"). Single-target auto-selection avoids consuming a script entry.
- **Reasoning**: The trigger system lacks a pre-resolution targeting hook. Condition check is the pragmatic alternative.
- **Impact**: Oracle card implementations using attack triggers with targeting.


## Planeswalker damage removes loyalty counters (oracle workspace engine)

- **Context**: `deal_damage()` in the oracle workspace engine needed to handle planeswalkers.
- **Decision**: Extended `deal_damage()` in `engine/game.py` to detect planeswalkers via `hasattr(target, "loyalty")` and remove loyalty counters. Check order: player → planeswalker → creature.
- **Reasoning**: MTG rules: damage to a planeswalker removes that many loyalty counters.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/engine/game.py`

## All-targets-illegal = spell countered on resolution (no effects)

- **Context**: Multi-target spells with untargeted bonus effects (like life gain) need correct handling when all targets become illegal.
- **Decision**: Per MTG rule 608.2b, if ALL targets are illegal at resolution, the spell is countered — no effects happen, including untargeted ones. Untargeted effects only resolve if at least one target remains legal.
- **Reasoning**: Matches official MTG comprehensive rules.
- **Impact**: Oracle card implementations with mixed targeted/untargeted effects.


## Planeswalker zero-loyalty SBA (oracle workspace engine)

- **Context**: MTG rule 704.5i requires planeswalkers with 0 loyalty to be put into owner's graveyard as a state-based action.
- **Decision**: Added planeswalker-0-loyalty check to `check_state_based_actions()` in oracle workspace engine.
- **Reasoning**: Required for test_dies_at_zero_loyalty to pass; fundamental MTG rule.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/engine/` — oracle workspace only.

## Surveil uses scripted choices (oracle workspace engine)

- **Context**: Surveil N requires looking at top N cards and choosing which to put in graveyard vs keep on top.
- **Decision**: Surveil implementation consults player's scripted choices to determine card disposition rather than always milling all cards.
- **Reasoning**: Matches MTG rules for surveil; enables testing both "all to gy" and "keep some on top" paths.
- **Impact**: Oracle workspace planeswalker impls and tests using surveil.


## Paradigm mechanic: replacement effect + recurring trigger (oracle workspace)

- **Context**: Paradigm is an ability word that routes a spell to exile on resolution and registers a recurring "may cast from exile" trigger at each main phase.
- **Decision**: Paradigm self-exile uses the existing `ReplacementManager` / `_SpellToGraveyardReplacementEvent` mechanism built for sos_1. Recurring trigger fires via `BeginningOfMainPhaseEvent` wired into `advance_phase()`. Recurring cast uses `cast_spell_free` for proper stack flow.
- **Reasoning**: Reuses existing engine infrastructure rather than inventing parallel mechanisms.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/engine/` and sos_120 card_impl.

