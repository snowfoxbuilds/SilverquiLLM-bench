Status: ACCEPTED
Date: 2026-10-02

# ADR-016: Baseline Engines May Carry Known Defects, Scored Against a Separate Known-Best Engine

## Context

Every benchmark's baseline engine is a port of the XMage rules engine, and none has ever been flawless.
The FDN and engine suites were written against those engines, so some graded tests encode a defect (counters surviving a zone change, status read off a graveyard card), and failing cases the baseline could not pass were cut from the graded suites.
An agent that fixed a real defect then failed a graded test it could not change, and lost points for correct rules work (#123).
Oracle validation could not catch this, because each Test Oracle Workspace engine carried the same defects as the baseline it was copied from.

## Decision

A benchmark's baseline engine and FDN implementations may carry Known Defects, either inherited (found in an engine or implementation) or seeded on purpose; Seeded Defects are fixed per benchmark version, and agents may fix either kind.
The FDN and engine Audited Tests assert rules-correct behavior even where the baseline fails them.
Those the unmodified Workspace fails are Dependency Tests and those it passes are Collateral Tests, both counted in the Net Card Score of ADR-020 (amended 2026-10-14).

A Known-Best Workspace, separate from every benchmark, holds the Known-Best Engine and the FDN implementations with every Known Defect fixed, and the full FDN and engine Audited Tests.
A benchmark is built by porting a copy of it; its Test Oracle Workspace engine starts from that copy, and its baseline engine is that copy plus its Known Defects.
Each benchmark lists its Known Defects in a host-only manifest, and CI checks that the baseline fails exactly the listed Audited Tests and the oracle passes every one.

A new defect is fixed in the Known-Best Workspace first, then ported to the Test Oracle Workspace of every non-Released benchmark that carries it.
Released benchmarks never take the fix.

## Consequences

- **Positive**: Fixing an engine defect the target cards depend on raises an agent's score instead of lowering it, so the benchmark measures rules knowledge rather than tolerance of a contradictory spec (amended 2026-10-14).
- **Positive**: Every graded test is shown passable on a defect-free engine, and Seeded Defects become a deliberate difficulty knob.
- **Positive**: Failing cases no longer have to be cut from graded suites to keep the baseline green.
- **Negative**: An FDN or engine pass rate below 100% no longer means the agent broke something; only a failing Collateral Test does (amended 2026-10-14).
- **Negative**: The Known-Best Engine and each benchmark's oracle engine must be kept in step by porting; a missed port shows up only as a failing oracle check.
- **Neutral**: The baseline reference grade moves whenever an FDN or engine Audited Test changes, so it is recomputed per grading-inputs digest.

## Alternatives Considered

- **Fix every defect in each benchmark's baseline engine**: Rejected, because a locked Workspace cannot change and new defects keep being found; it also removes engine repair from what the benchmark can measure.
- **Make FDN and engine Audited Tests convention-agnostic, so any engine convention passes**: Rejected as the general rule, because a dedicated rules test is then impossible and correct fixes earn nothing; individual tests still avoid pinning conventions unrelated to the behavior they check.
- **Separate reference scores per suite**: Rejected, because an engine defect often fails FDN Audited Tests, so attributing defects to suites needs per-test bookkeeping for little difference in what a reader learns.
- **Hold ledger-disputed failures as pending until adjudicated**: Rejected, because it needs per-run grading state; a wrong graded test is instead fixed while the benchmark is in Benchmarking and every run is regraded.
- **Use each benchmark's Test Oracle Workspace engine as its known-best engine**: Rejected, because the oracle engines are benchmark-specific copies carrying the same inherited defects, and a fix would have to be found and made separately in each one.

## Amendments

- **2026-10-14**: The Combined Regression report and its Baseline Score and Known-Best Score reference points gave way to the Net Card Score of ADR-020, which classes the FDN and engine Audited Tests as Dependency or Collateral Tests and credits only fixes the target cards depend on; evaluation-sense "regression" names were swapped per the rename record ADR-021.

## Relevant PRs

- #126 — Specifies the Known-Best Engine model, Known Defect manifests and Combined Regression.
