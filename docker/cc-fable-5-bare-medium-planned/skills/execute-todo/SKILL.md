---
name: execute-todo
description: Execute the prepared SOS card-implementation plan in this workspace. Reads /workspace/TODO.md and /workspace/CONTEXT.md, implements the card checklist one item at a time through the real engine, runs engine_tests after each, and never stops to ask questions. Built for an unattended single-shot run — no worktree, branch, or PR.
---

**Execute this incrementally. Do not describe your plan — read the files and start working through the checklist.**

**This is an unattended, single-shot run. Never stop to ask the user a question.
When something is ambiguous, make your best spec-grounded decision, log one line
in `/workspace/KEY_DECISIONS.md`, and keep moving.**

## 1. Orient (once, briefly)

- Read `/workspace/TODO.md` — your task, the build order, the shared engine seams
  to reuse, the engine gaps to keep card-local, and the pitfalls. Read the whole
  `## Pitfalls` section before writing any engine code.
- Read `/workspace/CONTEXT.md` — the vocabulary (keyword mechanics + terms).
- Skim `AGENTS.md` and `PROJECT_MAP.md` for layout. Do **not** read `RULEBOOK.txt`
  whole — use `skills/grep-rulebook/SKILL.md` recipes for any rules question.
- Parse the `- [ ]` checklist in `TODO.md`. Work the items **in order**.

TODO.md is a **guide, not a spec**. `card_spec.json` + `RULEBOOK.txt` are the
source of truth. When the real engine contradicts a claim in the plan, trust the
engine and the spec, fix the code, and add a one-line note next to that item.

## 2. Per-item loop (one card at a time, in order)

For each incomplete `- [ ]` item:

1. **Read the spec.** Open `cards/sos/sos_<N>/card_spec.json` and enumerate every
   clause of `oracle_text` and its edge cases (empty zones, no legal target,
   optional "may", trigger-vs-replacement ordering, state-based actions).
2. **Find the nearest FDN analogue and mirror it.** Use the one named in TODO.md;
   confirm by reading it. `grep -rl "<phrase>" cards/fdn/*/card_impl.py` finds
   more. Mirror its structure — many cards collapse to a few lines.
3. **Reuse the named seam.** Read the actual hook/registry/helper in `engine/`
   (the docstrings, not the `docs/` spec) before using it. Pick the *simplest*
   seam that the FDN example uses. For a gap, implement the **smallest card-local
   change** per TODO's `## Engine gaps` — never a general subsystem for a
   single-card mechanic (this is the #1 pitfall).
4. **Make the minimal change** at `cards/sos/sos_<N>/card_impl.py`, plus the
   smallest additive `engine/` edit if truly required.
5. **Test through the real engine.** Write 2–5 focused tests at
   `cards/sos/sos_<N>/tests.py` using `test_utils` (`create_game`,
   `set_board_state`, `cast_spell`, `advance_to_phase`, `declare_attackers`,
   `declare_blockers`; for abilities, `ActivateAbility(card, index)` driven through
   `priority_loop`). Never hand-build internal events, call a card's
   `get_*_abilities()` or `on_resolve` directly, pop the stack, or script a
   player's queue.
6. **Verify against the spec, independently of your tests.** Green tests are not
   proof — re-derive each clause from `card_spec.json` + `RULEBOOK.txt`, then run a
   short **throwaway** smoke check you did *not* write a test for and assert the
   spec-observable outcome (zones, life, P/T, counters, exile vs graveyard). If it
   disagrees with your tests or the plan, trust the spec and fix the code.
7. **Guard the engine.** Run `python3 -m pytest engine_tests/ -q`. Never ship a
   change that regresses it. If a gap edit broke it, fix or shrink the edit.
8. **Mark `- [x]`** in `TODO.md` and commit:
   `git add -A && git commit -m "sos_<N>: <card name>"`. One commit per card.
9. Move to the next item.

Rules: one item at a time, in order; do not skip or reorder; do not reword TODO
items (only flip `[ ]`→`[x]` and add deviation notes); never stop to ask.

## 3. Restraint (the whole point of this run)

- **Reuse before you add.** The smallest correct change extending an existing
  seam is the target. A new module/manager/framework for one card is over-built.
- **Calibrate against the codebase.** If your solution is much larger or more
  novel than how comparable FDN cards solve similar problems, you are
  over-building — reconsider.
- **Single-card gaps stay card-local.** Prefer a flag/field read at the one right
  point, commented as a deliberate limitation, over a speculative subsystem.
- **Additive-only engine.** Add or edit bodies; never rename/move/delete existing
  `engine/` symbols. Keep each card class in its own `card_impl.py`. Never touch
  `engine_tests/` or `cards/fdn/*/tests.py`.

## 4. KEY_DECISIONS.md

Keep `/workspace/KEY_DECISIONS.md` as a lightweight log. One short entry whenever
a clause is ambiguous, you deviate from TODO.md, or you make an engine gap a
deliberate card-local limitation: what was unclear, what you decided, why.

## 5. Finish

When every item is `- [x]`, do a final `python3 -m pytest engine_tests/ -q`,
ensure all ten card files import cleanly, commit anything uncommitted, and stop.
Maximize forward progress: keep going until all cards are done.
