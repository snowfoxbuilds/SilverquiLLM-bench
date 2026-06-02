---
name: implement-mtg-card
description: >-
  Discipline for implementing a Magic card in this Python engine
  (cards/sos/<id>/card_impl.py). Use whenever implementing, fixing, or verifying any
  SOS or FDN card — turning a card_spec.json / oracle_text into engine behavior:
  finding the closest reference card, discovering which CardImpl hook or engine
  registry a mechanic maps to, reusing existing seams instead of adding new ones, and
  testing through the real engine rather than a stand-in. Covers the loop spec ->
  nearest example -> minimal change -> real-engine tests -> independent verify, and how
  to avoid over-engineering.
---

This is a general implementation discipline, shown with this engine's tools as examples.
It transfers to any codebase: read the requirement, copy the nearest working example,
extend through existing seams, verify against the real system.

## Principles that matter most

1. **The requirements are the source of truth — not your own tests.** Here that means
   `card_spec.json` + the rules text in `RULEBOOK.txt`. Tests you write can encode the
   *same* misreading as your implementation, so green tests are not proof of
   correctness. Implement what the card actually does.
2. **Verify by exercising the real engine,** through its public interface — not by a
   harness that simulates the engine's internals.
3. **Reuse before you add.** The smallest correct change that extends an existing seam
   is the target. A new subsystem to satisfy a single card is almost always over-built.

## Per-card loop (a method, not a rigid script)

1. **Read the spec.** Enumerate every clause of `oracle_text` and its edge cases
   (empty zones, illegal / no legal target, optional "may", ordering of triggers vs
   replacements, state-based actions). Note `complexity_tier`.
2. **Find the nearest working example and mirror it.** The completed FDN cards in
   `cards/fdn/` are your reference library. Search by mechanic and shape, e.g.:
   ```bash
   grep -rl "<keyword or phrase>" cards/fdn/*/card_impl.py
   grep -l '"complexity_tier": "<tier>"' cards/fdn/*/card_spec.json
   ```
   Read the closest one and mirror its structure. Many simple cards collapse to a
   one-liner — e.g. a vanilla / keyword-only creature is usually just
   `make_vanilla(...)` (see `cards/fdn/fdn_142`, ~16 lines). Don't hand-roll what an
   existing card already does.
3. **Let the code show you the seams.** Read the card base class's overridable hooks
   (`engine/card.py`) and the registries the engine exposes; pick the *simplest* seam
   that the nearest example uses. Don't reach for a heavyweight mechanism when a small
   local override or a flag matches a working example — the shortest correct path wins.
4. **Make the minimal change.** Implement the card class at `cards/sos/<id>/card_impl.py`,
   reusing existing capability and keeping logic where comparable cards keep it.
5. **Test through the real engine.** Write 2–5 focused tests at `cards/sos/<id>/tests.py`
   that drive the card the way the game does (see "Test the real system" below). Then
   run the provided platform suite so you don't regress the engine:
   ```bash
   python3 -m pytest engine_tests/ -q
   ```
6. **Self-review against spec + rulebook.** Re-check each oracle clause is implemented.
   When unsure how a keyword/timing/replacement actually works, consult the rulebook
   (use the `grep-rulebook` skill) before guessing.
7. **Verify independently.** Spawn the `card-verifier` subagent (Task tool,
   `subagent_type: card-verifier`) with the card id and the paths to its
   `card_spec.json` and `card_impl.py`. Address every `LIKELY_FAIL` it reports; rerun
   the engine suite after fixes.

## Restraint — judgment, not bans

- Reuse before you add. Prefer extending an existing seam over inventing a new module,
  manager, or framework. A new abstraction has to earn its place.
- Calibrate against comparable code: if your solution is much larger or more novel than
  how the codebase solves similar problems, you're probably over-building — reconsider.
- If the engine genuinely lacks a capability, prefer a small, local workaround (e.g. a
  flag on the card read at the right point, commented as a deliberate limitation) over a
  speculative general subsystem — and **note the tradeoff** in your rationale rather than
  silently building infrastructure.
- Follow the repo's own conventions (`AGENTS.md`).

## Test the real system, not a stand-in

Drive behavior through the engine's public interface — `test_utils` provides
`create_game`, `set_board_state`, `cast_spell`, `advance_to_phase`, `declare_attackers`,
`declare_blockers`. A spell is cast and resolved by going through that path, the same way
a player would.

**Avoid tests that bypass the real execution path:** hand-constructing internal event
objects and firing them yourself, popping the stack and calling `on_resolve()` directly,
or scripting a player's internal decision queue to force a path. Such tests pass while
the real path is broken — that is exactly how a self-authored test suite gives false
confidence. Some FDN `tests.py` take these shortcuts; **don't copy that** — go through
`test_utils`.

## Where to look (orientation, not a lookup table)

This engine exposes its extension points as **overridable hooks on the card base class**
(`engine/card.py` — read its method docstrings) plus a few **registries** (triggered
abilities, replacement effects, continuous effects) and **helper factories**
(e.g. `engine/creatures.py`, `engine/casting.py`, `engine/game.py`). Discover *which*
seam fits a given clause by reading the base class and the nearest FDN example — not from
a memorized "mechanic → exact API" mapping. The skill here is the method (read the
interface, mirror the closest example); it transfers to any codebase.
