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
  Candidate Bundle before spending a real HOB run on it.

It **replaces** the retired card-subset ("workload") / filtered runs: cheap
validation is a dedicated benchmark, not a partial run of a real one
(HOB-BENCHMARKS.md → Run shape).

## Never leaderboard-published

`config.json` sets `leaderboard.eligible: false` — the never-published marker.
The smoke benchmark is run **like any other benchmark** (one container session
over its whole problem set, one Workspace), but its results never enter a
leaderboard.

Distinct from the `silverquillm smoke` **command**, which is container-boot
validation only (a synthetic workspace, no real cards) — see
RUN-ARTIFACTS-AND-TELEMETRY.md → Smoke runs.

## Layout

- `config.json` — identity + `leaderboard.eligible: false`.
- `workspace/` — a hard copy of the hob-medium workspace (sibling benchmarks
  never share). The target cards (`cards/fdn/fdn_129`, `fdn_205`, `fdn_232`) are
  reduced to stubs for the candidate to fill; every other FDN card stays a filled
  reference implementation.
- `data/pool.json` — spec data (name, mana cost, type line, oracle text) for the
  three target cards.
- `data/tests/audited/fdn/fdn_<cn>/tests.py` — the audited grader suite per
  target: the target's own FDN Reference Tests, already validated against the
  known-good hob-medium implementation.

## Targets

| Card | Collector # | Type | Why |
| --- | --- | --- | --- |
| Seismic Rupture | 205 | Sorcery | Cast pipeline, state-based actions, area damage. |
| Leyline Axe | 129 | Artifact — Equipment | Equip attach/detach lifecycle, continuous effects, the intent/decision layer. |
| Scavenging Ooze | 232 | Creature — Ooze | Activated ability, +1/+1 counters, graveyard interaction, lifegain. |

Three distinct card types across three distinct mechanics — a broad, still-cheap
slice of the engine. `tests/test_smoke_benchmark.py` proves the audited suite is
green against the hob-medium reference implementations.
