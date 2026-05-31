Status: DRAFT

Last updated: 2026-05-30

# Test-Improvement Workflow

How audited tests are improved over time using harvested run results and a combined investigation/discovery skill. This is the manual v1 of the planned v2 Test Harvester, and the operational counterpart to the locking lifecycle in ADR-011. Everything here serves **Implementation-Agnostic Testing** (see [CONTEXT.md](http://context.md/)): tests assert what a card does and must pass against any correct implementation.

## Overview

Three pieces, all gated by Benchmark Tier (ADR-011) — test edits and promotion are legal only in Beta/Benchmarking:

1. A **harvest script** that consolidates per-run results into a queryable dataset.
2. A **combined investigation/discovery skill** an agent runs over that dataset.
3. A **promotion bar** for turning discovered cases into audited tests.
## 1. Harvest script

- **Location**: `scripts/harvest_validated_results.py` (matches the existing repo script-utility pattern). May graduate to a `silverquillm harvest` subcommand later if it earns its keep.
- **Source**: all `docker/<image>/validated_results/<run>/` directories. Per-test detail comes from each `cards/<card>/result.json` (`errors` = failed pytest node IDs, plus pass/fail/total counts) — no need to parse the multi-MB agent logs.
- **Output**: `benchmarks/<bench>/analysis/harvested_results.jsonl`.
- **Format**: long-format JSONL — one row per `(image, run, card, test-node, pass/fail)`, fully denormalized, written in run-append order and grouped at query time (DuckDB / pandas). Each row carries the `tests.py` content hash so audited-test changes across runs are detectable. Coarser rollups are query-time views; optionally load into DuckDB or emit a Parquet sibling for repeated slicing.
### `harvested_results.jsonl` row schema

One JSON object per line; one row per `(image, run, card, test-node)`:

- `image` (string) — agent image dir, e.g. `local-pi-blind`.
- `run` (string) — `run_name`, e.g. `sos-2026-05-16T19-49`.
- `card` (string) — card ID, e.g. `sos_57`.
- `test_node` (string) — pytest node ID, e.g. `tests.py::test_mana_sculpt_refund`.
- `outcome` (string) — `pass` | `fail`, derived from `result.json.errors` (a node listed in `errors` is `fail`, else `pass`).
- `tests_hash` (string) — content hash of the card's audited `tests.py` used for this run, so audited-test changes across runs are detectable.
- `passed` / `failed` / `total` (int) — per-card rollup counts copied onto each row for convenience.
- `complexity_tier` (string, optional) — from `card_spec.json` when available.
- `harvested_at` (string) — ISO-8601 timestamp of the harvest run.
Rows are append-only in run order; rollups (per-card, per-image, per-test-node failure breadth) are query-time views. Cross-impl breadth = count of distinct `image` values with `outcome = fail` for a given `(card, test_node, tests_hash)`.

## 2. Investigation + discovery skill

- **Location**: `.claude/skills/` in the bench repo (a Claude Code native skill, e.g. `.claude/skills/test-investigation/SKILL.md`), version-controlled alongside the audited tests it edits. Not in `docker/<image>/skills/` — those mount into benchmark-subject agents and are the wrong audience.
- **Combined, not two skills**: the same skill does both failure-investigation and test-discovery.
- **Fault attribution = cross-impl breadth only** (no oracle re-run): a test failing across many independent implementations is ranked suspect. Breadth is a triage/prioritization heuristic, **not** an automated verdict — a human makes the final test-fault vs impl-fault call, and the skill never auto-edits audited tests.
- **Known tradeoff**: breadth alone can't separate a convention-coupled test from a genuinely hard card; the human-review gate absorbs this.
### `SKILL.md` contract

The skill lives at `.claude/skills/test-investigation/SKILL.md` (Claude Code native skill format), version-controlled alongside the audited tests it edits.

- **Frontmatter**: `name` (`test-investigation`), `description` (when to invoke), and the allowed tools/commands the skill may run.
- **Inputs**: path to `benchmarks/<bench>/analysis/harvested_results.jsonl`; the target benchmark and its tier (must be Beta/Benchmarking — refuse if Released); optional card / test-node filters.
- **Two modes, one skill**:
  - *Investigation* — for a failing `(card, test_node)`, rank by cross-impl breadth, summarize the failure, and present a test-fault vs impl-fault hypothesis for a human to decide. Never edits audited tests automatically.
  - *Discovery* — mine agent-written `tests.py` for behaviors the audited suite does not cover and emit promotion candidates.
- **Outputs**: a human-reviewable report (suspect tests ranked by breadth; candidate promotions), not committed test edits. A human applies all edits after review.
- **Hard rules**: no oracle re-run for attribution (breadth-only triage); canonical-engine-API-only when drafting; obey ADR-011 tier locks; promotion candidates must pass the matching Test Oracle Impl gate (ADR-010) before human review.
## 3. Discovery → promotion bar

- Candidate tests mined from agent-written `tests.py` are **never** promoted verbatim.
- Rewrite to the audited standard: integration-style, behavioral/outcome-based, canonical-engine-API-only, `DeterministicPlayer`-scripted (see [TEST-SUITE.md](http://test-suite.md/)).
- Must pass the matching Test Oracle Impl gate (ADR-010) and the canonical-API-only check, then clear human review.
- Legal only in Beta/Benchmarking. Released locks audited tests, so promotion stops at Release and published scores do not drift afterward.
## Cadence

The workflow is **on-demand** (it is the manual v1), but a harvest + investigation pass is **required before any Benchmarking→Released transition** — the moment audited tests are frozen for good, and therefore the last chance to catch convention-coupled or low-discrimination tests. It is not run on every benchmark run and not automated in CI; doing so would contradict the manual, human-gated design.

## Relation to the v2 Test Harvester

This workflow is the manual v1 of the planned v2 Test Harvester: an automated pass that harvests validated results and **scores audited test quality** — cross-impl failure breadth, discrimination between strong and weak implementations, and convention-coupling — to surface suspect tests and promotion candidates with less human triage. The self-eval / N×N cross-eval framing is retired (see [PROJECT-OVERVIEW.md](http://project-overview.md/) → Evaluation Architecture); v2 automates the harvest + triage described above, not a per-agent eval matrix. By design the harvester is not run after Release.

## Tier gating

All test edits and promotions obey Benchmark Tier locks (ADR-011): `workspace/` locked at Benchmarking; oracle impls/engine and audited tests additionally locked at Released. The CI check enforces the base branch's tier.
