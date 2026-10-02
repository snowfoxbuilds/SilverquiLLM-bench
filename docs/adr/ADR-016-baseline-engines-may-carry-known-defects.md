Status: ACCEPTED
Date: 2026-10-02

# ADR-016: Baseline Engines May Carry Known Defects, Scored Against a Separate Known-Best Engine

## Context

Every benchmark's baseline engine is a port of the XMage rules engine, and none has ever been flawless.
The regression suites were written against those engines, so some graded tests encode a defect (counters surviving a zone change, status read off a graveyard card), and failing cases the baseline could not pass were cut from the graded suites.
An agent that fixed a real defect then failed a graded test it could not change, and lost regression points for correct rules work (#123).
Oracle validation could not catch this, because each Test Oracle Workspace engine carried the same defects as the baseline it was copied from.

## Decision

A benchmark's baseline engine and FDN implementations may carry Known Defects, either inherited (found in an engine or implementation) or seeded on purpose; Seeded Defects are fixed per benchmark version, and agents may fix either kind.
The Audited Tests of the two regression dimensions assert rules-correct behavior even where the baseline fails them.
Each regression dimension reports its raw pass/total against two reference points: the Baseline Score (the unmodified Workspace's grade) and the Known-Best Score (a perfect score).

A Known-Best Workspace, separate from every benchmark, holds the Known-Best Engine and the FDN implementations with every Known Defect fixed, and the full regression Audited Tests.
A benchmark is built by porting a copy of it; its Test Oracle Workspace engine starts from that copy, and its baseline engine is that copy plus its Known Defects.
Each benchmark lists its Known Defects in a host-only manifest, and CI checks that the baseline fails exactly the listed Audited Tests and the oracle passes every one.

A new defect is fixed in the Known-Best Workspace first, then ported to the Test Oracle Workspace of every non-Released benchmark that carries it.
Released benchmarks never take the fix.

## Consequences

- **Positive**: Fixing a real engine defect raises an agent's regression score instead of lowering it, so the benchmark measures rules knowledge rather than tolerance of a contradictory spec.
- **Positive**: Every graded test is shown passable on a defect-free engine, and Seeded Defects become a deliberate difficulty knob.
- **Positive**: Failing cases no longer have to be cut from graded suites to keep the baseline green.
- **Negative**: Regression scores need two reference points to read, and a raw pass rate below 100% no longer means the agent broke something.
- **Negative**: The Known-Best Engine and each benchmark's oracle engine must be kept in step by porting; a missed port shows up only as a failing oracle check.
- **Neutral**: The Baseline Score moves whenever a regression Audited Test changes, so it is recomputed per grading-inputs digest.

## Alternatives Considered

- **Fix every defect in each benchmark's baseline engine**: Rejected, because a locked Workspace cannot change and new defects keep being found; it also removes engine repair from what the benchmark can measure.
- **Make regression tests convention-agnostic, so any engine convention passes**: Rejected as the general rule, because a dedicated rules test is then impossible and correct fixes earn nothing; individual tests still avoid pinning conventions unrelated to the behavior they check.
- **Hold ledger-disputed failures as pending until adjudicated**: Rejected, because it needs per-run grading state; a wrong graded test is instead fixed while the benchmark is in Benchmarking and every run is regraded.
- **Use each benchmark's Test Oracle Workspace engine as its known-best engine**: Rejected, because the oracle engines are benchmark-specific copies carrying the same inherited defects, and a fix would have to be found and made separately in each one.
