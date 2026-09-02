---
name: test-investigation
description: >
  Invoke when you need to triage failing audited tests or discover promotion
  candidates from agent-written tests.  Operates on Harvested Results produced
  by `scripts/harvest_validated_results.py` and the cross-impl breadth summary.
  Two modes: (a) Investigation — rank failing (card, test_node) pairs by breadth
  and present a test-fault vs impl-fault hypothesis for human decision;
  (b) Discovery — surface promotion candidates from agent-written tests for
  human review.  Outputs a human-reviewable report only; never commits test
  edits.
allowed-tools:
  - Read
  - Grep
  - Bash
  - scripts/harvest_validated_results.py
  - scripts/mine_promotion_candidates.py
  - scripts/check_promotion_candidate.py
---

# Test Investigation Skill

Combined investigation and discovery skill for the manual v1 Test Harvester.
Use this skill to triage failing audited tests and to surface promotion
candidates from agent-written tests.  All outputs are human-reviewable reports
— **no committed test edits**.

Refer to [TEST-SUITE.md](../../../docs/specs/TEST-SUITE.md) for the audited-test
standard that governs the tests this skill examines.

## Inputs

| Input | Source | Required |
|---|---|---|
| Harvested Results dataset | `benchmarks/<bench>/analysis/harvested_results.jsonl` | Yes |
| Cross-impl breadth summary | `benchmarks/<bench>/analysis/harvested_summary.json` (produced by `python scripts/harvest_validated_results.py --summary`) | Yes |
| Benchmark Tier | `benchmarks/<bench>/config.json` field `tier` | Yes |
| Card filter | Optional card ID(s) to restrict scope | No |
| Test-node filter | Optional test-node pattern(s) to restrict scope | No |

### Benchmark Tier gate

Read the `tier` field from `benchmarks/<bench>/config.json` before doing any
work.  Only **Beta** and **Benchmarking** tiers are permitted.

> **REFUSAL RULE — Released tier.**  If the Benchmark Tier is **Released**, the
> skill MUST refuse to operate.  No test edits, no promotions, no investigation
> reports.  A Released benchmark's audited tests, Test Oracle Impls, and
> Workspace are all locked (ADR-011).  Exit immediately with a clear message
> explaining why.

SOS is currently in **Benchmarking**.

## Mode (a): Investigation

Use Investigation mode when one or more audited `(card, test_node)` pairs are
failing and you need to determine whether the fault lies in the test or in
agent implementations.

### Procedure

1. **Load the breadth view.**  Read
   `benchmarks/<bench>/analysis/harvested_summary.json` (produced by
   `python scripts/harvest_validated_results.py --summary`).  Each entry ranks
   a `(card, test_node)` pair by how many *independent* implementations fail it.

2. **Rank by cross-impl breadth.**  The more independent implementations that
   fail the same test node, the stronger the signal that the test itself may be
   at fault (test-fault suspect).  A node that fails only one implementation is
   more likely an impl-fault.

3. **Present a hypothesis.**  For each investigated `(card, test_node)`, state
   clearly:
   - The breadth (number of distinct failing images).
   - Whether the failure pattern suggests **test-fault** (high breadth — many
     independent correct implementations all fail) or **impl-fault** (low
     breadth — only one or a few implementations fail).
   - Any `tests_hash` changes across runs that may indicate the test was
     modified mid-benchmark.

4. **Never auto-edit audited tests.**  The audited test suite lives at
   `benchmarks/sos/data/tests/audited/<set>/<card>/tests.py` and is governed by
   [TEST-SUITE.md](../../../docs/specs/TEST-SUITE.md).  This skill produces
   hypotheses only — **the human makes the final fault call**.

### Hard constraints (Investigation)

- **Breadth-only triage** — do NOT re-run the Test Oracle to attribute faults.
  Attribution is breadth-based; no oracle re-run.
- **Canonical-engine-API-only** — when drafting any illustrative fix for a
  suspect test, use only public APIs present in the canonical engine (the
  Workspace engine, not the Test Oracle Workspace engine).  This upholds
  Implementation-Agnostic Testing.
- The human decides.  Never auto-apply edits to audited tests.

## Mode (b): Discovery

Use Discovery mode to surface promotion candidates — high-quality tests written
by agents during Tested Mode runs that could be promoted into the audited suite.

### Procedure

1. **Run the discovery miner.**  Invoke `scripts/mine_promotion_candidates.py`
   (item 8) to scan agent-written `tests.py` files in Validated Results and
   identify candidates worth reviewing.

2. **Gate each candidate.**  Before presenting a candidate for human review, run
   `scripts/check_promotion_candidate.py` (item 9).  The gate runs three checks
   and a candidate MUST NOT be surfaced unless all pass:
   - **Tier lock** (ADR-011) — only Beta/Benchmarking tiers permit promotion.
   - **Canonical-API check** — rejects a candidate that references an engine
     symbol present only in the Test Oracle Workspace engine.  This covers not
     just module/class/function names but also class attributes, methods,
     properties, and `self.<attr>` instance attributes (e.g. `mana_spent`,
     `restricted_mana`, `rng`), so a test coupling to an oracle-only primitive
     that lives *inside* a class is caught — not silently passed.
   - **Test Oracle Impl gate** (ADR-010) — the candidate must pass against the
     matching oracle `card_impl.py`.

3. **Present for human review.**  List each passing candidate with:
   - The card and test node(s) it covers.
   - Which agent/run produced it.
   - Confirmation that it passed the Test Oracle Impl gate.

4. **No committed test edits.**  Discovery outputs are a report for human
   review.  The human decides whether to promote a candidate into the audited
   suite.

## Hard rules

All of these apply in both Investigation and Discovery modes:

1. **Breadth-only triage** — no oracle re-run for fault attribution.  Use the
   cross-impl breadth ranking from `harvested_summary.json` exclusively.
2. **Human makes the final fault call** — this skill presents hypotheses and
   candidates; it never auto-edits audited tests or commits changes.
3. **Canonical-engine-API-only** — when drafting test prose or illustrative
   fixes, use only APIs present in the canonical engine.  This preserves
   Implementation-Agnostic Testing.
4. **Obey ADR-011 Benchmark Tier locks** — refuse to operate on a Released
   benchmark.  Only Beta and Benchmarking tiers permit test investigation and
   discovery.
5. **Promotion candidates must pass the Test Oracle Impl gate** (ADR-010) via
   `scripts/check_promotion_candidate.py` before being surfaced for human
   review.
6. **Outputs are a human-reviewable report only** — no committed test edits.
   The audited suite at `benchmarks/sos/data/tests/audited/` is modified only
   by human action after reviewing this skill's output.

## Vocabulary

This skill uses the capitalized terms defined in
[CONTEXT.md](../../../CONTEXT.md):

- **Harvested Results** — the consolidated JSONL dataset from all Validated
  Results.
- **Validated Results** — per-run result artifacts under
  `docker/<image>/validated_results/<run>/`. Also mirrored as immutable run
  records in the private results repo; `harvest_validated_results.py
  --results-repo <clone>` reads them from there with identical rows.
- **Implementation-Agnostic Testing** — the principle that tests assert
  observable behavior, not implementation details.
- **Benchmark Tier** — the lifecycle state (Beta / Benchmarking / Released)
  controlling what may change.
- **Test Oracle Impl** — host-side `card_impl.py` used as the validation oracle
  for audited tests.
