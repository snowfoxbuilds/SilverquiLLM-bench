# FDN Replay Validation — Final Parity Report

Status: CLOSED (grilling 2026-08-27)

This is the closing artifact for the FDN Replay Validation burn-down
(PROJECT-OVERVIEW.md Phase 3). It **transcribes** the settled measurements from
`KEY_DECISIONS.md` (Phases M/N/O, final entries 2026-08-12/14); it is not a
re-measurement — the replay corpus is operator-held (see Reproduction). All
numbers here match `KEY_DECISIONS.md` verbatim.

## Closure statement

FDN Replay Validation is **closed**. The residue is 100% machine-attributed and
accepted; **none of it is engine-attributable**, so there are no further
burn-down phases.

- **Observer mode is fully clean**: 271/271 games diverge-free, divergence rate
  **0.0**, report md5 `0ac34605e8c0bb2323ef458caf2ad9f2` (unchanged since
  Phase F). Observer mode is the frozen-behavior oracle-sync path.
- **Simulate mode residue is accepted**: the engine is *driven* through
  gameplay, then compared before resync. The remaining divergences are all
  attributed to documented limitation classes — a proven **floor** of genuine
  17lands-stream limitations plus **attributed families** of bounded,
  resync-corrected cadence offsets and known card-content gaps. Cadence work
  reopens only if a future benchmark surfaces an actual engine bug in this area.

## Final simulate numbers (Phase O)

- **Total divergences: 5,222** — simulate report md5
  `5b6b691d3d3ae94905708d2109213d62` (two runs md5-identical).
- **Triage completeness gate**: records 5,222, tagged **5,222/5,222**,
  **complete=True, untagged=0** (`scripts/triage_divergences.py` exits non-zero
  on any untagged/unknown tag).
- **Floor: 564** — the genuine stream limitations the corpus cannot overcome:

  | Floor tag | Count |
  | --- | --- |
  | hidden-information | 453 |
  | unfunded-activation | 65 |
  | ambiguous-ability | 46 |
  | **floor total** | **564** |

- **Attributed families: 4,658** — fixable/known engine & card-content gaps,
  none an engine bug:

  | Family tag | Count |
  | --- | --- |
  | resolution-cadence | 4,233 |
  | unimplemented-effect | 402 |
  | driving-context | 23 |
  | replay-infra | 0 |
  | **family total** | **4,658** |

  Floor 564 + families 4,658 = **5,222**.

## Phase ledger

The burn-down progression, transcribed from `KEY_DECISIONS.md`. The `floor`
column exists only from Phase M onward — Phase M is what introduced the
machine-checked 7-tag limitation taxonomy; earlier phases predate it. Observer
mode stayed 271/271 clean (rate 0.0, md5 `0ac34605…`) at every step.

| Step | Simulate total | Floor | Mechanism (one line) |
| --- | --- | --- | --- |
| baseline | 10,072 | — | First full-corpus simulate measurement, pre-burn-down (re-verified 2026-08-10). |
| Phase F | 9,387 (−685) | — | Closing-phase P/T + MISSING reductions; own-ETB tokens now mint and compare. |
| correction | 9,597 | — | Honest re-exposure: land the silently-dropped counter annotations (+62) and refuse speculative deferred folds (+148); settled pre-Phase-G baseline. |
| Phase M | 5,814 | 560 | Capstone: outcome-matched multi-ability driving + machine-checked limitation floor. Attribution-only, corpus-neutral (5,814 → 5,814). |
| Phase N | 5,268 (−546) | 556 | Pre-comparison P/T re-derivation for trigger-resolution cadence (issue #56). |
| Phase O | 5,222 (−46) | 564 | Token producibility — mint-cadence offset vs missing minter (issue #57). |

**Note on the correction → Phase M gap.** Phases G–L (unlisted above) carried
the corpus 9,597 → 5,814 — the dominant single move was Phase G's
arrival-aligned resolution (9,597 → 7,085, −2,512, `zone_contents` cadence).
Phase M's baseline (5,814) is post-Phases I/J; Phase M itself changed no count
(it added the attribution floor). So "Phase M 5,814" is both the state entering
and after M.

**Per-phase floor / family detail (M → N → O):**

| Tag | Phase M | Phase N | Phase O |
| --- | --- | --- | --- |
| hidden-information | 447 | 445 | 453 |
| unfunded-activation | 65 | 65 | 65 |
| ambiguous-ability | 48 | 46 | 46 |
| **floor** | **560** | **556** | **564** |
| resolution-cadence | 4,601 | 4,058 | 4,233 |
| unimplemented-effect | 630 | 631 | 402 |
| driving-context | 23 | 23 | 23 |
| **total** | **5,814** | **5,268** | **5,222** |

Phase O's −46 is genuine: 46 false "no engine impl that mints it" MISSING_CARD
records removed for tokens the impls demonstrably mint (MISSING_CARD 130 → 84);
unimplemented-effect 631 → 402 splits into −46 MISSING removed, −175
re-attributed to resolution-cadence (impl-minted mint-cadence offsets), and −8
re-attributed to hidden-information (the correlation-refused 1/1 black Rat
94169, a same-colour copy collision).

## Limitation taxonomy

The classifier (`silverquillm/replay/limitations.py`, `classify_limitation`) is
a **total** function mapping every simulate-mode divergence to exactly one of
seven tags — three *floor* tags and four *family* tags. Definitions are quoted
from `limitations.py`.

**Floor tags** — genuine stream limitations the corpus cannot overcome. Each is
mechanism-proven on a golden by
`benchmarks/hob-medium/workspace/engine_tests/test_replay_limitations.py::TestLimitationEvidence`:

- **unfunded-activation** — the activation/cast cost is not covered by any
  stream-attested resource (no ManaPaid within look-ahead, no attested
  manaPool, or a card-private counter cost the stream never carries).
- **ambiguous-ability** — a multi-ability source whose exact ability the stream
  under-determines; GRE carries no per-card ability-grpId map, so ≥2 candidate
  predictions match the observed delta and the executor refuses to guess (from
  `ValidationReport.ambiguous_sources`).
- **hidden-information** — the compared value depends on zone content GRE does
  not attest to the observing seat (grpId-0 hidden hand/library shells, a
  library-driven power/toughness, or an out-of-set/unmappable token identity).

**Family tags** — fixable engine / card-content gaps (future work), none an
engine bug on the observer path:

- **unimplemented-effect** — GRE attests a token/effect the engine's card
  implementation does not yet produce (a dormant upkeep/end-step minter or an
  unimplemented token identity).
- **resolution-cadence** — the engine produces the effect but applies it at a
  different snapshot boundary than GRE (a bounded, resync-corrected timing
  offset in zone/life/tapped/power-toughness, or a creature-death race).
- **driving-context** — the executor could not reconstruct the exact driven
  cast/activation from the stream (no legal target, sorcery-speed, or a
  timing/zone context the drive-time engine state does not match).
- **replay-infra** — an executor-side harness impossibility (engine library
  empty on a GRE-observed draw, step-event plumbing) — kept distinct from
  engine/card bugs.

`FLOOR_TAGS` is derived from `LIMITATION_TAGS`; `CORRELATION_REFUSED_TOKENS`
(grpId 94169) floors the copy-collision Rat to `hidden-information` (Phase O).

## Reproduction

The corpus is **operator-held** at `/mnt/data/benchmark-replays/fdn`
(gitignored; the in-repo `data/replays/` carries only `sample_replay.json` and
the id maps). This report is a transcription of the recorded measurements, not a
re-run against that corpus. To reproduce end-to-end where the corpus is
available:

```bash
# 1. Full-corpus simulate report (drives the engine, compares before resync).
benchmark validate /mnt/data/benchmark-replays/fdn \
    --benchmark hob-medium --simulate \
    --report benchmarks/hob-medium/analysis/report.json

# 2. Triage + completeness gate (tags every divergence; non-zero on any
#    untagged/unknown tag, i.e. proves complete=True / untagged=0).
python3 scripts/triage_divergences.py benchmarks/hob-medium/analysis/report.json \
    --corpus /mnt/data/benchmark-replays/fdn \
    --out-dir benchmarks/hob-medium/analysis
```

Observer mode (the clean 271/271, rate 0.0 baseline) is the same command without
`--simulate`. Both reports are deterministic and byte-identical across runs from
a fixed corpus; the md5s above pin them.
