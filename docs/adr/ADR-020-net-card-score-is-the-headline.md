Status: ACCEPTED
Date: 2026-10-14

# ADR-020: The Net Card Score Is the Headline Score

## Context

The headline result was the target-card Audited Test pass rate, reported beside two regression dimensions with no composite score.
It ranked first the run that passed the most Audited Tests, even when that run broke existing cards along the way.
It also charged the agent with failures it inherited: in hob-medium, most of the gap between the top candidates came from engine defects the agents trusted, not from their own implementations.

## Decision

A Benchmark Run's headline is its Net Card Score, in units of working cards:

    (Cards Implemented + Cards Fixed − Cards Broken) / (target cards + cards hosting related Known Defects)

- Every Audited Test is an Implementation Test (a target-card test that depends on no Known Defect), a Dependency Test (one that fails because of a Known Defect) or a Collateral Test (an FDN or engine Audited Test the unmodified Workspace passes).
  Which target-card tests depend on a Known Defect is found by putting the defect back into the Test Oracle Workspace; only Known Defects are dependencies, and an engine mechanic a target card needs but the baseline lacks is part of that card's implementation.
- Every counted test has one Attributed Card. Collateral Tests are one group across the FDN and engine suites, so every engine breakage shows up as a broken existing card.
  The tests of one mechanic, or of one related Known Defect, share one card, and no card hosts two mechanics; the grouping is best-effort.
- Only related Known Defects earn Cards Fixed: those some target-card test depends on.
  Dependency Tests of other Known Defects, and those that also depend on one, are left out.
- Each count is all-or-nothing per card.
- An unmodified Workspace scores 0 and the Known-Best Workspace with the Test Oracle Impls scores 1. There is no floor.
- The score is derived when read, from a Run Record's per-test outcomes, the baseline reference grade and the benchmark's attribution and relatedness data; Run Records do not store it.
- It applies from fra-hard-v2 on. hob-medium, fra-hard v1 and SOS keep the results they reported.

## Consequences

- **Positive**: Breaking an existing card cancels implementing a new one, so a run that makes a mess no longer ranks first.
- **Positive**: The agent's own mistakes are separated from failures inherited from Known Defects, and a workaround duplicated inside a card earns nothing over fixing the engine.
- **Positive**: Counting whole cards normalizes cards with different numbers of tests, and spreads candidates that per-test rates compress (fra-hard-v2's completed runs passed 92–100% of target-card tests but 2–11 of 11 cards).
- **Negative**: Each benchmark needs attribution data and a relatedness classification, kept current by hand when tests change.
- **Negative**: A single test can swing a whole card, so single runs are noisier.
- **Negative**: Fixing a Known Defect that no target card depends on no longer raises the score, narrowing ADR-016's promise that fixing a real defect gains score.
- **Neutral**: Pass rates per suite remain diagnostics.

## Alternatives Considered

- **Three dimensions with no composite score**: rejected because readers took the target-card pass rate as the headline, and it ignored breakage.
- **Target-card test pass rate as the headline**: rejected because it compresses the top candidates into a few percent and weights a card by its number of tests.
- **Credit every Known Defect fixed**: rejected because fra-hard-v2's 14 defects reach 18 FDN cards against 11 targets, so fixes the task does not need would outweigh the task and drive the rankings.
- **Credit a fix per existing card it reaches**: rejected because fra-hard-v2's one related defect reaches six FDN cards and two engine test files, which would make it worth more than half the task.
- **Treat engine mechanics the baseline lacks as dependencies**: rejected because engine work is the difficulty knob of the hard benchmarks, and nearly every target-card test would be excluded.
- **Store the score in Run Records**: rejected because records are immutable, so a corrected attribution would leave stale scores behind.
- **Floor the score at 0**: rejected because it hides runs that wreck the engine.
- **Re-score hob-medium**: rejected because its graded suites have no Dependency Tests for existing cards and no Known Defect record, so its scores would not be comparable.

## Relevant PRs

- #242 — Makes the Net Card Score the headline, with its test classes, Attributed Cards and Known Defect manifest schema 2.
