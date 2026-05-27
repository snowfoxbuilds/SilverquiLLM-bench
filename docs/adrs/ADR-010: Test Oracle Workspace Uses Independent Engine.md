Status: ACCEPTED

Date: 2026-05-26

# ADR-010: Test Oracle Workspace Uses Independent Engine

## Context

The Phase 18 SOS test audit identified 10 cards whose Test Oracle Impls require engine primitives not present in the canonical `engine/` — cast-from-zone-without-paying (sos_1, sos_120), miracle alternative-cost-on-first-draw (sos_201), casualty additional-cost-and-spell-copy (sos_226), paradigm self-exile-and-recurring-trigger (sos_120). Adding those primitives to canonical `engine/` would (a) invalidate the 2026-05-26 benchmark scores by making previously hard cards retroactively easier, and (b) gut the Engine Extension Quality scoring category, which exists precisely to grade whether the agent can invent missing primitives.

## Decision

The Test Oracle Workspace at `benchmarks/sos/data/test_oracle_workspace/` keeps an independent copy of `engine/` that may diverge from canonical. Canonical `benchmarks/sos/workspace/engine/` is frozen with respect to Phase 18 work — engine extensions needed by Test Oracle Impls land in the oracle's engine only.

The rewritten audited test suite is constrained to call only public APIs present in the canonical engine. Tests target observable game-state outcomes; they never reach into oracle-engine-only helpers. This guarantees that a rewritten audited test passes against any correct agent impl regardless of which primitives that agent invents to satisfy the spec.

## Consequences

- **Positive**: Existing benchmark scores remain comparable. Engine Extension Quality scoring stays meaningful for the cards that motivate the category. Canonical engine grows organically with Replay Validation and natural mechanic coverage, not retroactively for oracle convenience.
- **Negative**: Two `engine/` copies in the repo. Manual sync discipline when canonical changes (bug fixes, refactors) — oracle engine may lag canonical fixes.
- **Neutral**: A future phase may merge oracle-proved primitives into canonical once an explicit engine-baseline-versioning scheme is in place. Until then, the canonical engine grows by other means.
## Workflow

The Test Oracle Workspace mirrors `benchmarks/sos/workspace/` 1:1 — `engine/`, `cards/fdn/`, `cards/sos/` (with stubs for non-audited cards), `tests/`, `test_utils.py`, `AGENTS.md`, `pytest.ini`. The oracle workspace's `test_utils.py` is where the host-side ergonomic test helpers live (`set_mana_pool`, `set_hand`, `set_battlefield`, `set_library_top`, `set_graveyard`, `assert_on_stack`, `assert_in_zone`, `assert_casting_error`). **There is no separate ****`silverquillm/test_utils.py`****.**

Per-card workflow:

1. Author the Test Oracle Impl at `test_oracle_workspace/cards/sos/sos_{cn}/card_impl.py` from the xmage analog.
2. Develop the rewritten audited tests at `test_oracle_workspace/tests/audited/sos/sos_{cn}/tests.py`, importing helpers from `test_oracle_workspace/test_utils.py`, running against the oracle impl.
3. Once the test file is green against the oracle impl, **copy it** to the canonical audited path at `benchmarks/sos/data/tests/audited/sos/sos_{cn}/tests.py`. The canonical path is where the validation harness `tests/test_audited_against_reference.py` reads from, and where the harness runs the tests against agent impls.
Engine extensions land in `test_oracle_workspace/engine/` only. The validation harness ensures rewritten tests (canonical-engine-API-only) pass against the oracle's independent engine — guaranteeing they pass against any correct agent impl regardless of which primitives the agent invents.

## Alternatives Considered

- **Symlink oracle engine to canonical**: a single engine, but pre-ships miracle/casualty/`cast_for_free` to agents that previously had to invent them. Rejected — defeats Engine Extension Quality scoring and invalidates comparability of prior scores.
- **Feature-gate canonical engine with ****`_REFERENCE_MODE`**** flag**: oracle sees the extensions, agent doesn't. Adds a config surface threaded through every engine call. Rejected — over-engineered for v1.
- **Auto-regenerated copy with checked-in diff**: `make test-oracle-workspace` re-copies canonical and re-applies an `oracle.patch`. More discipline, less drift, but extra build machinery. Rejected for v1; can revisit if drift bites.
