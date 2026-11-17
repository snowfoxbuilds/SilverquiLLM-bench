# Smoke benchmark — FDN pipeline validation

A tiny, real benchmark whose only job is to show, cheaply, that a candidate
runs end to end. Its problem set is one **already-validated FDN card**
(a known-good oracle implementation and audited tests), staged nearly finished:
the candidate's whole task is a one-keyword change. A run is staged, driven,
harvested and evaluated like any other, but it measures whether the candidate
works at all, not how well it implements cards.

## Purpose

- **Pipeline Validation Run**: confirm the runner stages a workspace, launches a
  candidate, harvests `workspace_final/`, and scores the three audited dimensions
  end-to-end.
- **Candidate check**: a fast, low-cost target to confirm a new Karn construct
  boots, authenticates, edits the Workspace and exits cleanly before spending a
  real benchmark run on it. Smoke is deliberately not a miniature benchmark:
  its cost should be the candidate's fixed overhead, not card work.

It **replaces** the retired card-subset ("workload") / filtered runs: cheap
validation is a dedicated benchmark, not a partial run of a real one
(HOB-BENCHMARKS.md → Run shape).

## Never leaderboard-published

`config.json` sets `leaderboard.eligible: false` — the never-published marker.
The smoke benchmark is run **like any other benchmark** (one container session
over its whole problem set, one Workspace), but its results never enter a
leaderboard.

Distinct from the historical `silverquillm legacy smoke` **command**, which is container-boot
validation only (a synthetic workspace, no real cards) — see
the removed `RUN-ARTIFACTS-AND-TELEMETRY.md` → Smoke runs in git history.

## Layout

- `config.json` — identity + `leaderboard.eligible: false`.
- `workspace/` — a hard copy of the Known-Best Workspace (sibling benchmarks
  never share), with its Audited Engine Tests as `engine_tests/`. The target,
  `cards/fdn/fdn_142` (Healer's Hawk), is its Known-Best implementation with
  flying removed by its Starting Patch, `data/starting_patches/fdn_142.patch`,
  and ships without its FDN Reference Test; every other FDN card stays a filled
  reference implementation. Its engine and FDN
  implementations carry the Known Defects listed in `data/known_defects.json`,
  each applied from its patch in `data/known_defects/<id>.patch`. The agent
  documents (`AGENTS.md`, `PROJECT_MAP.md`, `test_utils.md`, `skills/`) are
  smoke's own.
- `data/pool.json` — spec data (name, mana cost, type line, oracle text) for the
  target card.
- `data/tests/audited/` — hard copies of the Known-Best Workspace's FDN Audited
  Tests (`fdn/`, which include the target's suite) and Audited Engine
  Tests (`engine/`). A target's suite grades card correctness only, never FDN
  Card Regression.
- `data/test_oracle_workspace/` — the Test Oracle Workspace: a hard copy of the
  Known-Best Workspace, whose Healer's Hawk is smoke's Test Oracle Impl.
- `data/known_defects.json` — the Known Defect manifest: the regression Audited
  Tests the unmodified Workspace fails, each traced to its defect.

## Target

| Card | Collector # | Type | Staged as |
| --- | --- | --- | --- |
| Healer's Hawk | 142 | Creature — Bird | Complete but for flying; the candidate adds it. |

The engine already supports flying, so a candidate needs no engine work and no
new tests: a run's cost is close to the candidate's fixed overhead. The staged
Hawk fails the flying tests in its audited suite and passes the rest, so a
candidate that changes nothing scores 0 of 1 card and one that adds flying
scores 1 of 1. `tests/test_smoke_benchmark.py` proves the target suite is green
on smoke's own engine with the Test Oracle Impl swapped in and red on the staged
target, and `tests/test_ported_benchmarks.py` checks the Known Defect manifest.

## Re-porting

Smoke follows the Known-Best Workspace. After the Known-Best Workspace changes,
re-port it with:

```bash
silverquillm build port-from-known-best smoke
```

This rewrites the copied engine, FDN cards, Test Interface, test helpers and Audited Tests,
reapplies the Starting Patch to the Known-Best Healer's Hawk and reapplies the
Known Defect patches; a patch
that no longer applies stops the port, and the patch is then re-recorded
against the new Known-Best code. `tests/test_port_from_known_best.py` fails
while smoke is behind (`--check` reports what a port would change).
