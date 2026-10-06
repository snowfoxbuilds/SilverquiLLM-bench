# Smoke benchmark — FDN pipeline validation

A tiny, real benchmark whose only job is to exercise the end-to-end pipeline
cheaply. Its problem set is a handful of **already-validated FDN cards**
(known-good oracle implementations and audited tests), so the pipeline can be
run — staged, driven, harvested, evaluated — without waiting on a full HOB pool.

## Purpose

- **Pipeline Validation Run**: confirm the runner stages a workspace, launches a
  candidate, harvests `workspace_final/`, and scores the three audited dimensions
  end-to-end.
- **Candidate calibration**: a fast, low-cost target to sanity-check a new
  Karn construct before spending a real HOB run on it.

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
RUN-ARTIFACTS-AND-TELEMETRY.md → Smoke runs.

## Layout

- `config.json` — identity + `leaderboard.eligible: false`.
- `workspace/` — a hard copy of the Known-Best Workspace (sibling benchmarks
  never share), with its Audited Engine Tests as `engine_tests/`. The target
  cards (`cards/fdn/fdn_129`, `fdn_205`, `fdn_232`) are reduced to generated
  stubs carrying their predefined classes, for the candidate to fill; every
  other FDN card stays a filled reference implementation. Its engine and FDN
  implementations carry the Known Defects listed in `data/known_defects.json`,
  each applied from its patch in `data/known_defects/<id>.patch`. The agent
  documents (`AGENTS.md`, `PROJECT_MAP.md`, `test_utils.md`, `skills/`) are
  smoke's own.
- `data/pool.json` — spec data (name, mana cost, type line, oracle text) for the
  three target cards.
- `data/tests/audited/` — hard copies of the Known-Best Workspace's FDN Audited
  Tests (`fdn/`, which include the three targets' suites) and Audited Engine
  Tests (`engine/`). A target's suite grades card correctness only, never FDN
  Card Regression.
- `data/test_oracle_workspace/` — the Test Oracle Workspace: a hard copy of the
  Known-Best Workspace, whose implementations of the three targets are smoke's
  Test Oracle Impls.
- `data/known_defects.json` — the Known Defect manifest: the regression Audited
  Tests the unmodified Workspace fails, each traced to its defect.

## Targets

| Card | Collector # | Type | Why |
| --- | --- | --- | --- |
| Seismic Rupture | 205 | Sorcery | Cast pipeline, state-based actions, area damage. |
| Leyline Axe | 129 | Artifact — Equipment | Equip attach/detach lifecycle, continuous effects, the intent/decision layer. |
| Scavenging Ooze | 232 | Creature — Ooze | Activated ability, +1/+1 counters, graveyard interaction, lifegain. |

Three distinct card types across three distinct mechanics — a broad, still-cheap
slice of the engine. `tests/test_smoke_benchmark.py` proves the target suites are
green on smoke's own engine with the Test Oracle Impls swapped in, and
`tests/test_ported_benchmarks.py` checks the Known Defect manifest.

## Re-porting

Smoke follows the Known-Best Workspace. After the Known-Best Workspace changes,
re-port it with:

```bash
python3 scripts/port_from_known_best.py smoke
```

This rewrites the copied engine, FDN cards, Test Interface, test helpers and Audited Tests,
regenerates the target stubs and reapplies the Known Defect patches; a patch
that no longer applies stops the port, and the defect is then re-recorded
against the new Known-Best code. `tests/test_port_from_known_best.py` fails
while smoke is behind (`--check` reports what a port would change).
