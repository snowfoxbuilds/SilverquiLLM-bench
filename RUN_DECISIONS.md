# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.

## Spec deviation: Item 1 — evaluator.py not modified
- **TODO spec expected**: Extend `silverquillm/evaluator.py` with `--against=oracle` mode.
- **Actual codebase state**: The harness is self-contained in `tests/test_audited_against_reference.py` and reuses the temp-dir pattern from evaluator.py without modifying it.
- **What was implemented instead**: Standalone test file that pytest collects directly, no evaluator flag needed.
- **Impact**: `tests/test_audited_against_reference.py` — simpler integration, fewer moving parts.

## Test infrastructure: conftest for oracle workspace audited tests
- **Context**: Tests in `test_oracle_workspace/tests/audited/sos/` need to import from `card_impl` generically.
- **Decision**: Created a conftest in the workspace that resolves `card_impl` imports by detecting the collector directory and loading from `cards/sos/<dir>/card_impl.py`.
- **Reasoning**: Matches the pattern used in the canonical audited test conftest; makes tests impl-agnostic.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/conftest.py`

## Design: sos_13 dual-mode card (front creature + back instant)
- **Context**: Emeritus of Truce // Swords to Plowshares is a split card with prepared mechanic.
- **Decision**: Single class with `_casting_back_face` flag. Mode detected in `can_cast()` when card is in exile + prepared. `get_targets()` and `on_resolve()` branch on this flag.
- **Reasoning**: Simpler than separate instant class; the `cast_spell_free` flow operates on same card object from exile.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/cards/sos/sos_13/card_impl.py`

## Test failure: Item 5 — sos_57 Mana Sculpt
- **Failing tests**: test_refund_with_wizard, test_fizzle_when_target_removed
- **Tester's intent**: Verify Wizard-conditional mana refund (core spec requirement) and fizzle behavior when target removed from stack
- **Implementer's approach**: Deferred refund logic ("will be added when tests are written") and didn't implement fizzle check
- **Coordinator decision**: fix implementation — both behaviors are explicit TODO requirements, not edge cases
- **Reasoning**: The TODO explicitly says "if controller controls a Wizard at resolution time, register a delayed trigger" and fizzle is basic counterspell behavior

## Spec deviation: Item 5 — sos_57 Mana Sculpt refund timing + amount
- **TODO spec expected**: Delayed trigger at "beginning of controller's next main phase" adding {C} × actual mana spent to cast the countered spell.
- **Actual codebase state**: No delayed-trigger-at-phase system exists in the oracle workspace engine. No mana-spent-tracking on arbitrary opponent spells.
- **What was implemented instead**: Immediate mana addition using countered spell's CMC as proxy for mana spent.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/cards/sos/sos_57/card_impl.py` — tests verify immediate CMC-based refund, which correctly discriminates Wizard/no-Wizard behavior. Full delayed trigger deferred to engine maturation.

## Disagreement: Item 5 — test infrastructure for counterspells
- **Reviewer comment (strict)**: _put_spell_on_stack builds bare StackObject instead of real cast; refund test accepts immediate payout.
- **Implementer justification**: cast_spell auto-resolves, so you can't use it to place a spell on the stack for targeting. Immediate refund is a deliberate simplification.
- **Coordinator decision**: accept implementer — the test infrastructure correctly tests counterspell behavior (targeting stack objects, counter = remove without resolving, wizard-conditional refund). Full cast pipeline isn't needed for the counter-target interaction.
- **Reasoning**: The key bug pattern being tested is "vacuous pass on method existence" — these tests verify actual behavior (countering, refunding) not method existence. The timing/amount simplification is well-bounded.
- **Impact**: Tests pass correctly against oracle impl; future engine enhancement can tighten timing assertions.

