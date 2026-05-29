# Run Decisions

Decisions made during this run only. Before the run ends, migrate anything worth preserving into `KEY_DECISIONS.md`.

## Untestable acceptance: sos_13
- Accepted partial coverage for the prepared spell-copy behavior because the spec omits the spell-side oracle text and there is no established public prepared-copy casting API to target safely.
- Accepted partial coverage for the split-card spell-half metadata because the engine has no canonical public schema for a second face on a creature implementation.
- Directive to Implementer: cover the testable creature/ETB/prepared-state behavior and add `# UNVERIFIED:` markers in `cards/sos/sos_13/card_impl.py` for the omitted prepared spell-copy and spell-half metadata requirements.

## Spec/engine note: sos_13
- Kept Emeritus of Truce's observable token/prepared effect mirrored in `on_resolve` because the current engine cast path does not surface the permanent's self-ETB trigger in a way that satisfies the local card contract directly.

## Spec/engine note: sos_201
- Left the advisory miracle-window timing divergence in place after the strict review fix; the card implementation remains green, but the local engine window still follows its existing simplified miracle timing surface.
