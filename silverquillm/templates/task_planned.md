# {{ISSUE_TITLE}}

{{PROBLEM_STATEMENT}}

## Plan first

Before you write any implementation code, produce an explicit implementation
plan and then follow it. Work in two phases:

1. **Plan.** Read the specs, the reference cards, and the engine, and write
   down — in order — the cards you will implement, the engine changes each one
   needs, and the risks or unknowns you see. Decide the sequence before you
   start.
2. **Execute.** Implement against that plan, one card at a time, keeping the
   engine tests green as you go. When reality diverges from the plan, update the
   plan and record the change in your Output Proposal's `decisions`.

The plan is a means, not a deliverable: it exists to make your execution
deliberate. Do not spend the whole budget planning.

## Workspace layout

Your working tree is mounted at `/workspace`. It is the entire world you act in.

- `cards/{{TARGET_SET}}/<card_id>/card_impl.py` — the target card implementations. The
  cards named above are stubs for you to fill in; every other card in this
  directory is a completed reference implementation you can read as an example.
- `cards/{{TARGET_SET}}/<card_id>/card_spec.json` — each card's structured spec
  (name, mana cost, type line, oracle text).
- `engine/` — the rules engine. You may change it to implement new keywords or
  mechanics the cards need.
- `engine_tests/` — engine tests you can run locally to check your changes.
- `RULEBOOK.txt` — the full deep-reference rules text.
- `AGENTS.md`, `PROJECT_MAP.md` — orientation for this workspace; read them first.

For engine API discovery, read the source modules directly — they carry rich
docstrings (`engine/card.py`, `engine/events.py`, `engine/triggers.py`,
`engine/replacement_effects.py`, `engine/zones.py`).

## Envelope

There is no additive-only rule and no diff policing. You may edit, rename, or
refactor any file under `/workspace`, including the engine, as long as you do
not break behavior the reference cards and engine tests depend on. The
authoritative grading suites run host-side from their own copies; the tests
staged in `engine_tests/` are for your local verification only, and editing
them cannot change your score — it can only mislead you.

## Output contract

All of your work product is the state of the `/workspace` tree when your session
ends — that filesystem state is the source of truth, and it is graded exactly as
you leave it. When you are done, also record an Output Proposal describing what
you did: write `output/proposal.json` in the job directory using the
`format-output` tool (never edit the file by hand). The `commit-message` field
is required; `decisions`, `open-questions`, `remaining-work`, and `dead-ends`
are optional narrative. The driver validates and applies the proposal — and
commits the workspace — after your session exits. Do not run `git` yourself.
