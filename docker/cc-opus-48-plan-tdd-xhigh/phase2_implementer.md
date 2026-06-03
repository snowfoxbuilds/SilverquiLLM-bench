# Phase 2 of 2 — IMPLEMENTATION (TDD)

You are the **implementation** agent. A planning agent already analyzed this task and wrote
`/workspace/PLAN.md`.

## Start here

1. **Read `/workspace/PLAN.md` in full.** It contains the engine-gap analysis (which shared seams to
   build), the per-card plans (nearest FDN analogue + exact seams to reuse + edge cases), and the
   implementation order. **Follow it.**
2. If a point in the plan turns out wrong or incomplete, correct course — and note the deviation in
   `PLAN.md` so the record stays accurate. Default to following the plan. If `PLAN.md` is missing or
   thin, proceed from the task directly.

## How to implement: strict TDD (use the `tdd` skill)

Work in the plan's order. **Build the shared engine seams first**, then the cards that reuse them.
For each behavior, go **vertical** — one tracer bullet at a time:

1. Write **one** test that drives the behavior through the engine's **public interface**
   (`test_utils`: `create_game`, `set_board_state`, `cast_spell`, `advance_to_phase`,
   `declare_attackers`, `declare_blockers`) and asserts a spec-derived **observable** outcome.
2. Run it, watch it **fail** (red) for the right reason.
3. Write the **minimal** code to make it pass (green) — at `cards/sos/<id>/card_impl.py`, reusing the
   seam the plan named.
4. Repeat for the next behavior. **Do not** write all tests up front — that tests hypothetical
   structure, not real behavior.

## Discipline

- **Test the real engine, not a stand-in.** Never hand-construct internal events, pop the stack and
  call `on_resolve()` directly, or script a player's internal queue — those pass while the real path
  is broken. Drive the card the way a player would, through `test_utils`.
- **Reuse before you add.** Extend the existing seam the plan identified; mirror the nearest FDN card.
  A new subsystem for a single card is almost always over-built — keep engine edits minimal and shared
  (the plan flags which changes are shared).
- **Requirements are the source of truth — not your tests.** Green tests can encode the same misreading
  as the code; re-check each oracle clause against `card_spec.json` + `RULEBOOK.txt` (use
  `grep-rulebook`).
- **Guard the engine.** After each card and after any `engine/` change, run
  `python3 -m pytest engine_tests/ -q` — never ship a change that regresses it.
- Do **not** modify anything under `engine_tests/` (the grader uses its own authoritative copies).

The task follows.
