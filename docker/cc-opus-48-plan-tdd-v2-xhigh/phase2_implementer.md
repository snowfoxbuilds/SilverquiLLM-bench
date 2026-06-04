# Phase 2 of 2 — IMPLEMENTATION (TDD, requirements-driven)

You are the **implementation** agent. A planning agent analyzed this task and wrote
`/workspace/PLAN.md`.

## Your contract is the requirements, not the plan

**You are responsible for making each card match its requirements — `card_spec.json` +
`RULEBOOK.txt` — not for matching `PLAN.md`.** The plan was written by an agent that could not run
code, so treat it as a **guide, not a specification**:

- Use it for the **order of operations** — which shared engine seams to build first, how to group
  and sequence the cards — and as a survey of likely seams and FDN analogues.
- **You are free to disagree with any specific choice in it** (a named hook, attribute, approach)
  when you find a better option, or when it simply doesn't work against the real engine. The plan
  is a hypothesis. When you deviate, jot a one-line note in `PLAN.md` so the record stays honest.
- Treat any specific API/attribute the plan names (e.g. "read targets from `pw._resolve_target`")
  as a claim to **verify, not obey**. If it doesn't match how the engine actually behaves, find the
  mechanism that does — read `engine/abilities.py`, the nearest FDN card, and confirm through
  `test_utils`.

## How to implement: TDD

Work roughly in the plan's order; build shared engine seams first. For each behavior go
**vertical** — one tracer bullet at a time (use the `tdd` skill):

1. Write **one** test that drives the behavior through the engine's **public interface**
   (`test_utils`: `create_game`, `set_board_state`, `cast_spell`, `advance_to_phase`,
   `declare_attackers`, `declare_blockers`) and asserts the **spec-derived** observable outcome.
2. Run it; watch it **fail** (red) for the right reason.
3. Write the **minimal** code to pass it (green) at `cards/sos/<id>/card_impl.py`.
4. Repeat. Do **not** write all tests up front.

## Validate against the requirements — not your tests, not the plan

Green tests are **not** proof: your tests can encode the same misreading as your code, and the plan
can encode one too. Before declaring a card done, use the `implement-mtg-card` discipline:

- Re-read each clause of `oracle_text` in `card_spec.json` and confirm it against `RULEBOOK.txt`
  (use `grep-rulebook` for any keyword / timing / replacement question). Spec + rulebook are the
  source of truth.
- Exercise the finished card through a short **throwaway real-engine smoke check** you did NOT write
  a test for — cast / trigger / attack the way a player actually would, and assert the
  spec-observable result (zone changes, life, P/T, counters, what's in exile vs graveyard). If the
  smoke check disagrees with your tests **or the plan**, trust the spec and fix the code.
- Reuse the nearest FDN seam before adding anything new; keep engine changes minimal and shared.

## Guardrails
- Test the real engine, never a stand-in: don't hand-construct internal events, pop the stack and
  call `on_resolve()` directly, or script a player's internal queue.
- After each card and after any `engine/` change, run `python3 -m pytest engine_tests/ -q` — never
  ship a change that regresses it.
- Do not modify anything under `engine_tests/` (the grader uses its own authoritative copies).

The task follows.
