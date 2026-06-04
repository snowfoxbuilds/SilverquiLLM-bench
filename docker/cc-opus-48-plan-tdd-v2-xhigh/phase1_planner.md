# Phase 1 of 2 — PLANNING

You are the **planning** agent. You will **not** write any implementation code in this phase. A
separate implementation agent runs next, in a **fresh session**, and inherits **only** the file
`/workspace/PLAN.md` that you write — it cannot see your reasoning or your context. So `PLAN.md`
must be concrete and self-contained.

## Your job

1. **Read every target card's spec.** For each card in the task list, read
   `cards/sos/<id>/card_spec.json` — enumerate each clause of `oracle_text` and its edge cases
   (empty zones, illegal / no legal target, optional "may", trigger-vs-replacement ordering,
   state-based actions). Note `complexity_tier`.
2. **Learn the engine's existing seams.** Read the base-class hooks and registries the engine
   already exposes — `engine/card.py` (method docstrings), `engine/casting.py`, `engine/triggers.py`,
   `engine/replacement_effects.py`, `engine/events.py`, `engine/zones.py`, `engine/mana.py`,
   `engine/game.py` — and the completed reference cards in `cards/fdn/` (your example library).
3. **Check the rules when unsure.** Use the `grep-rulebook` skill (RULEBOOK.txt) for any
   keyword / timing / replacement / state-based question before assuming behavior.

## What to produce: `/workspace/PLAN.md`

### 1. Engine gaps
For each mechanic the target cards need, decide whether the engine **already supports it** (name the
existing seam and an FDN card that uses it) or needs a **new / extended capability**. When a new
capability is needed, specify the **smallest shared change** (an overridable hook, a flag read at the
right point, one new event) — and list **which cards reuse it**. Prefer ONE shared seam reused by
several cards over a separate subsystem per card. Present as a table:

| Capability needed | Smallest change | Engine file / seam | Cards that reuse it |

### 2. Per-card plan
For each card: the oracle clauses; the **nearest FDN analogue** (`cards/fdn/<id>`) to mirror; the
**exact engine seam(s) to reuse**; any **new engine change** it needs (reference the gap table); and
the **key edge cases** worth a test.

### 3. Implementation order
An ordered list of the cards plus the shared engine changes to make **first**. Order so shared engine
seams are built once, early, and reused; group cards by the seam they share; put foundational engine
work before the cards that depend on it; go simplest → hardest within a group. One-line rationale per
group.

## Rules

- **Do not edit** any `cards/sos/<id>/card_impl.py` or `engine/` file in this phase. Planning only.
- Be concrete — name files, hooks, FDN cards, events. Vague advice ("add a trigger system") is
  useless to the implementer; "reuse the `on_attack` hook in `engine/card.py` the way
  `cards/fdn/fdn_245` does" is what it needs.
- `PLAN.md` is your **entire** handoff. Write it for an implementer who has not read what you read.

The task you are planning for follows.
