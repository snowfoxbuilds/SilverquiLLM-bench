Implement the following. Do not pause to ask questions. Do not stop until everything is complete. Log key decisions in KEY_DECISIONS.md. Create a [SUMMARY.md](http://summary.md/) to summarize your work.

> 🎯 **Mission.** Operationalize [AUDITED-TEST-API.md](https://app.notion.com/p/8f73aba9c12e49449feef275f8470e96) in code: (1) implement the test API, (2) add a conformance test that enforces *only* the test API may touch the engine in audited tests, and (3) migrate every old-paradigm SOS audited test to the new simulation-only model.
> **Non-negotiable guardrail.** This work requires **zero changes to any workspace/canonical engine** (`benchmarks/sos/workspace/engine/`). Oracle-side changes are allowed where noted. If you think you need a canonical-engine change, stop — you've misread the spec.

## Role & repo

You are an engineer working in the **`snowfoxbuilds/SilverquiLLM-bench`** repository. SilverquiLLM-bench is an MTG-based benchmark that scores LLM coding agents; the **audited tests** are the maintainer-curated grading suite. The SOS benchmark is in the **Benchmarking** tier (per [ADR-011: Three-Tier Benchmark Locking](https://app.notion.com/p/1502318a9e494f06b4e68a9245cb6ab7)): `workspace/` is **locked**, while oracle impls/engine and audited tests are still editable.

## Read first (source of truth)

- [AUDITED-TEST-API.md](https://app.notion.com/p/8f73aba9c12e49449feef275f8470e96) — the API you are implementing. Parts 1–4 + the **allow-list** are normative.
- [AUDITED-TEST-SUITE.md](https://app.notion.com/p/a50ff4a1782e4badbc4419b6cbaface9) — Decisions log + Audited Test Categories (the simulation-only shape).
- [TESTING-CONVENTIONS.md](https://app.notion.com/p/c6553b4b515e4a7abdda59586e01d779) — Rule 5 is revised: entering the priority loop via `priority_loop` / `advance_to_phase` is now *required*; `game.run()` / `run_game()` / `run_turn()` stay banned.
- [ADR-010: Test Oracle Workspace Uses Independent Engine](https://app.notion.com/p/3517df19bf3c4b709ad6cbe40471c8b1) — `test_utils` 1:1 mirror rule + additive-extension-only constraint on the oracle engine.
> ✅ **Verified against the repo (2026-06-04, default branch).** The harness `tests/test_audited_against_reference.py` reads audited tests from `benchmarks/sos/data/tests/audited/sos/{cn}/tests.py`, copies the oracle `test_utils.py` + the audited `conftest.py` into a temp dir, and runs the 10 cards **sos_1, sos_4, sos_13, sos_57, sos_97, sos_120, sos_201, sos_226, sos_245, sos_257** against their oracle impls. The oracle authoring dir `…/test_oracle_workspace/tests/audited/sos/sos_{cn}/` exists for all 10. **The new API is not implemented yet** — the oracle `test_utils.py` still ships the old paradigm (`cast_spell(game, idx, name, …)` + `resolve_top` + private `_script` pokes) and `DeterministicPlayer` is single-channel, so all three deliverables are greenfield against the current code.

## Hard constraints

- **No canonical/workspace engine edits.** `benchmarks/sos/workspace/engine/` and the frozen canonical `benchmarks/sos/workspace/test_utils.py` are untouchable.
- **The test API references only canonical-public primitives**, so it keeps working against any candidate engine. Tests themselves run against the **oracle** (and, at eval time, each candidate).
- **Oracle engine changes are allowed only when additive / behavior-preserving** per ADR-010 — e.g. the one owed change below.
- **Two channels stay separate**: a player's directive queue (`script`) and choice script (`choices`) are distinct, ordered, and a dry queue on *either* fails the test (`ScriptExhaustedError`).
- **Assert observable state only.** No internal flags, private fields, call counts, or prompt-log inspection.
## Where code lives

- **Host-side API helpers** → the oracle workspace mirror `benchmarks/sos/data/test_oracle_workspace/test_utils.py` (ADR-010's home for ergonomic helpers). Not in `silverquillm/`; not in the frozen canonical mirror.
- **Audited tests** are authored at `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_{cn}/tests.py`, validated green against the matching oracle impl, then copied to the canonical audited path `benchmarks/sos/data/tests/audited/sos/sos_{cn}/tests.py`.
- **Validation harness** → `tests/test_audited_against_reference.py` (repo root) runs each audited test against its Test Oracle Impl.
- **Oracle impls** → `benchmarks/sos/data/test_oracle_workspace/cards/sos/sos_{cn}/card_impl.py`.
---

## Deliverable 1 — Implement the test API

Implement everything in the [AUDITED-TEST-API.md](http://audited-test-api.md/) allow-list as composition over canonical-public entrypoints (never engine edits).

**Setup**

- `create_game` — today's signature is deck-based (`create_game(deck1, deck2, *, player1_life, player2_life, scripts)`) with **no seed parameter**; add `seed=None` and seed `game.rng` from it (per the RNG decision). `set_player(game, idx, player)` is **new** (does not exist yet).
- Expand `set_board_state(game, idx, *, battlefield, hand, graveyard, life, mana)` (today's actual signature) to also accept `library` (ordered), `exile`, and `PermanentSpec` per-permanent state.
- `PermanentSpec(name, tapped, summoning_sick, counters, damage_marked, attachments, controller)`. `counters` keys limited to canonical `+1/+1`, `-1/-1`, `loyalty`.
- No `set_stack` primitive — stacked states are reached only by casting.
**Advance** (exactly two sanctioned advancers)

- `priority_loop(game)` — host-side driver: each iteration check SBAs → place triggers → poll players APNAP for one directive (retain-on-action, push without auto-drain) → if nobody acts and stack non-empty, resolve **exactly one** object via `resolve_top` → re-poll. Terminate when stack empty AND all directive queues exhausted. A poll/choice against a dry queue raises `ScriptExhaustedError`.
- `advance_to_phase(game, phase, step=None)` — fast-forwards turn structure (runs turn-based actions, triggers, end-of-turn cleanup so state is correct on arrival) but opens **no** priority windows; a trigger that forces a choice is still answered FIFO from the choice script.
- Keep the `pytest-timeout` 30s backstop.
**DeterministicPlayer** (two channels)

- `DeterministicPlayer` lives in the **oracle engine** (`benchmarks/sos/data/test_oracle_workspace/engine/player.py`) and today is **single-channel** (one flat `script` / `_script` deque consumed via `_pop()`). Adding the second `choices` channel — `DeterministicPlayer(name, script=[], choices=[], life=20)` — is an **additive oracle-engine change** (allowed per ADR-010), as is any directive-polling change to `priority_loop` (which lives in `engine/stack.py`). The directive action types (`CastSpell` / `CastSpellFree` / `ActivateAbility` / `PlayLand`), `no_op` / `perform_action` / `perform_illegal_action`, `PermanentSpec`, and the `assert_*` family are **new** and belong in the oracle `test_utils.py`.
- Channel 1 directives: `no_op()`, `perform_action(action)`, `perform_illegal_action(action)`.
- Channel 2 (`choices`) reuses the canonical answer deque consumed by `choose` / `choose_target` / `choose_yes_no` / `choose_card` / `assign_damage_order`.
- Actions: `CastSpell(name, targets=[], x=None, mode=None, mana=None, from_zone=Zone.HAND)`, `CastSpellFree(name, from_zone=Zone.HAND)`, `ActivateAbility(source, ability, targets=[], x=None)` (`ability` = printed-order index into `get_activated_abilities()` / `get_loyalty_abilities()`), `PlayLand(name)`.
- `from_zone != HAND` routes to a `cast_spell_from_exile`-style helper: a thin copy of the canonical cast path for the alternate zone/cost. Composition in the test layer — never an engine change.
- Failure semantics table from Part 3 must hold: `perform_action` on an illegal action fails; `perform_illegal_action` on an accepted action fails; both `CastingError` and `AbilityError` are treated as the rejection signal.
**Assertions** — the full `assert_*` family in Part 4 (zones, library order, tapped, counters, damage, P/T, stack, mana pool, colors-spent, life). No `assert_mana_spent` (canonical `StackObject` has no `mana_spent`) — measure via pool deltas. No `assert_counters` for non-canonical counter types.

*Acceptance:* every allow-list symbol exists, is importable from the oracle `test_utils`, and is exercised by at least one migrated test. No new symbol outside the allow-list is introduced.

## Deliverable 2 — Conformance test: only the test API may touch the engine

Add a meta-test (suggested `benchmarks/sos/data/test_oracle_workspace/tests/audited/test_api_conformance.py`) that statically scans **every** `tests/audited/**/sos_*/tests.py` and **fails** if any file reaches around the API. Use **AST parsing** (consistent with the harness's existing `_is_stub_impl` AST approach), not regex.

Flag as violations:

- Calls to banned advancers/shortcuts: `game.run`, `run_game`, `run_turn`, and the old free-function step helpers used directly in audited tests (`cast_spell(...)`, `resolve_top(...)`, `_resolve_top_of_stack(...)`).
- Direct card-internal probes: `on_resolve`, `register_triggers`, `register_replacement_effects`, `get_targets`, `get_cost_reduction`, etc. called from a test.
- **Private-attribute poking**: attribute access or names with a leading underscore on engine/card/game objects (`_script`, `_resolve_targets`, `_pop`, `_omniscience_active`, …).
- Any engine-touching call whose name is **not** in the [AUDITED-TEST-API.md](http://audited-test-api.md/) allow-list.
Do **not** flag importing the running engine package for value types/enums (`Phase`, `Step`, `Zone`, `ManaType`, `Color`, `CardType`, `Keyword`) — the import boundary decision permits importing the engine under test; the rule constrains the *API surface used to drive/observe*, not imports.

Emit a clear failure listing offending `file:line` + the banned symbol. Include a small fixture proving the checker actually catches a planted violation (so the guard can't silently rot).

*Acceptance:* conformance test is green on the migrated suite and red when any banned pattern is reintroduced.

## Deliverable 3 — Migrate old-paradigm audited tests

Rewrite each SOS card's audited `tests.py` from the old shape (`create_game` → `set_board_state` → `cast_spell` → `resolve_top` → assert, with direct `on_resolve` probes and a flat `DeterministicPlayer` script) to the new shape: `create_game` → `set_board_state` → `set_player(DeterministicPlayer(script=..., choices=...))` → advance via `priority_loop` (or `advance_to_phase`) → `assert_*`.

All 10 audited cards: **sos_1, sos_4, sos_13, sos_57, sos_97, sos_120, sos_201, sos_226, sos_245, sos_257.** Card-specific notes:

| Card | Migration note |
| --- | --- |
| sos_57 Mana Sculpt | No `assert_mana_spent`. Measure mana via pool delta (activate mana abilities → `assert_mana_pool` before/after); for the `{C}` refund, set the opponent's spell cost and assert the resulting pool. |
| sos_4 Together as One | Converge: pin `len(colors_spent)` by pre-setting the pool to exactly the needed colored mana (mana-minimality) or scripting mana-ability activations, then `assert_colors_spent`. |
| sos_97 Ral Zarek | Loyalty abilities by printed-order index in `ActivateAbility`. RNG via seed-replacement (`game.rng = random.Random(seed)`, re-derive expected from an identically-seeded RNG). Once-per-turn 2nd activation is exception-signaled → `perform_illegal_action` (raises `AbilityError`). |
| sos_257 Great Hall | Prowess is until-end-of-turn: use `advance_to_phase` so the reset actually runs; assert P/T before and after. Restricted mana is oracle-only — exercise indirectly. |
| sos_201 (Miracle granter) | Answer the miracle "cast for its miracle cost?" yes/no from the choice script; assert the granted behavior fires. |
| sos_226 Silverquill (Casualty) | Answer "sacrifice which creature?" from the choice script via public `choose`; assert sacrificed creature in graveyard + spell effect applied **twice** (`assert_on_stack` count 2 or doubled result). Same targets on the copy — do not assert retargeting. **Owed oracle change below.** |
| sos_245 Witherbloom (Affinity) | Affinity cost reduction is oracle-only; cast the subject under the grant and assert the reduced-cost outcome. |
| sos_13 Emeritus // Swords (Prepared) | Cast the back face from **exile** for `{W}` via `CastSpell(..., from_zone=Zone.EXILE)` → `cast_spell_from_exile` helper. |
| sos_1 Dawning Archaic & sos_120 Improvisation Capstone | Spell goes to **exile** instead of graveyard — use `test_spell_to_exile_after_resolution`; assert recast object lands in EXILE. sos_120 self-drains in `on_resolve`: assert only end-state, never a mid-cascade stack. |

**Combat (any card that attacks/blocks):** attackers/blockers are **choice-script** answers, not directives — attackers = a list, blockers = a `{blocker: attacker}` dict, ordering via `assign_damage_order`, reached by `advance_to_phase(COMBAT, …)`. Illegal attacks/blocks are **silently filtered** by the engine, so assert combat illegality **by outcome** (e.g. the flyer's damage reached the player); reserve `perform_illegal_action` for exception-signaled illegality.

**Owed oracle-engine change (allowed):** in `benchmarks/sos/data/test_oracle_workspace/engine/casting.py`, `_handle_casualty(game, card, player, stack_obj)` currently does `if isinstance(player, DeterministicPlayer): choice = player._pop()`. Drop that private poke and prompt via public `choose()`. It is invoked from `cast_spell`, `cast_spell_free`, **and** `cast_spell_for_cost`, so all three cast paths benefit. The same private `_script.appendleft(...)` poke also lives in the old `cast_spell` / `declare_attackers` / `declare_blockers` test-util helpers — the migration removes those in favor of the two-channel `choices` script. Canonical stays untouched; this also makes the test portable across candidate engines.

*Acceptance (per-card gate):* (1) all rewritten tests pass against the matching Test Oracle Impl via `tests/test_audited_against_reference.py`; (2) the oracle impl matches `card_spec.json` with **no engine-clamping shortcuts**; (3) per-card peer-review checkpoint before the commit lands.

---

## Definition of done

- [ ] All allow-list API symbols implemented in the oracle `test_utils` mirror; none outside the allow-list.
- [ ] Conformance test green on the migrated suite, and demonstrably red on a planted violation.
- [ ] All 10 SOS audited test files migrated to the simulation-only two-channel shape and green against their oracle impls via the harness.
- [ ] Migrated tests copied to the canonical audited path; harness green in CI.
- [ ] `_handle_casualty` oracle change landed (public `choose`), with **no** canonical/workspace engine diff anywhere in the PR.
- [ ] `git diff` touches **nothing** under `benchmarks/sos/workspace/`.
## Suggested PR shape (mirror the Phase 18 pattern)

1. **Setup commit** — new/expanded API helpers in the oracle `test_utils`, the conformance test, and the `_handle_casualty` oracle change. Harness + conformance green.
2. **One commit per card** (flagship **sos_57** first) — oracle impl (if needed) paired with its rewritten audited tests; each commit independently bisect-friendly (harness green at that commit). CI gate green from commit 2 onward.
> 📌 The four deferred-capability scoping decisions (arbitrary counter types, `SpecialAction` directive, multi-player turn control, simultaneous-trigger ordering) are **out of scope** here — see [Backlog](https://app.notion.com/p/3506a7adc8ed8089886ddb9193f307d0). Do not build them.
