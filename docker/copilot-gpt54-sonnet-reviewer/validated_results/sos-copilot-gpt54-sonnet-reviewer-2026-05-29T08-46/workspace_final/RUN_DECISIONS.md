# Run Decisions

Decisions made during this run only. Before the run ends, migrate anything worth preserving into `KEY_DECISIONS.md`.

## Untestable partial coverage: sos_13
- Accepted partial coverage for the requirement "While it's prepared, you may cast a copy of its spell. Doing so unprepares it."
- Reason: the workspace has no public prepared-action API, and the card spec omits the spell-side rules text needed to define the copied spell's exact behavior safely.
- Coordinator action: require an `# UNVERIFIED:` marker in `cards/sos/sos_13/card_impl.py` for this gap.

## Test dispute: sos_245
- **Disputed tests**: `cards/sos/sos_245/tests.py:150` — `TestWitherbloomTheBalancerGrantedAffinity.test_granted_affinity_lets_you_cast_an_instant_for_only_its_colored_mana`
- **Tester's intent**: Affinity should reduce only the generic portion of the cost and should not reduce colored mana requirements.
- **Implementer's objection**: The current setup only provides four creatures and `{B}`, so a `{6}{B}` spell still costs `{2}{B}` and cannot be cast legally.
- **Decision**: accept implementer
- **Reasoning**: The disputed test setup contradicts its own stated affinity rule; the expected successful cast is impossible under the card text and the rationale.
