# Phase 6 — FDN replay parity report (MSH Task #1)

Validation of the migrated MSH engine + FDN implementations against the FDN
replay corpus, compared to the Phase 0 V1 baseline (`PHASE0_CALLSITES.md`).

## How the replay now drives the engine

- **Benchmark-parameterized engine target.** `silverquillm/replay/cli.py` gains a
  `--benchmark <id>` flag that resolves `benchmarks/<id>/config.json` and prepends
  `benchmarks/<id>/workspace` to `sys.path`, so the executor's flat
  `from engine.X import …` imports bind to that benchmark's engine. SOS resolves to
  the frozen V1 engine, MSH to the Player Query engine.
- **Intent-based seat player.** `executor._make_replay_player` instantiates the
  intent-based `DeterministicPlayer` for the MSH engine (and falls back to the V1
  scripted player for the frozen SOS engine, which `ImportError`s on
  `engine.intent_player`). The MSH player is given a permissive **Baseline Intent**
  (empty pattern) so any system-level query the replay raises is answered in
  GRE-observed (first-offered) order. The replay continues to drive *actions*
  imperatively (`play_land`, `draw_card`, zone moves), so seat choices only arise
  for genuine choice-layer queries.
- **New divergence types.** `DivergenceType` gains `QUERY_UNANSWERED` (no
  replay-derived intent matched a raised query) and `PROTOCOL_ERROR` (engine-side
  boundary-validation failure). `classify_step_exception` maps a `ProtocolError`
  family exception → `PROTOCOL_ERROR` and an `UnmatchedQueryError` → `QUERY_UNANSWERED`
  (by MRO class-name, so the shared code imports no MSH-only classes). An
  unanswerable query is therefore a **recorded divergence, never a crash**.

## Parity result

Corpus: `data/replays/` → `sample_replay.json` (the FDN replay present;
`card_id_map.json` is metadata). Run via `parse_replay → ReplayExecutor →
validate_replay` with the MSH engine on `sys.path`.

| Replay file | Snapshots | Successful | Divergences (V1 baseline) | Divergences (MSH) | New divergence types |
| --- | --- | --- | --- | --- | --- |
| `sample_replay.json` | 12 | 12 | **0** | **0** | none |

**Parity bar (per-file divergences ≤ V1 baseline): MET** — 0 ≤ 0.

## Triage

No new divergences arose, so the mechanical triage procedure has nothing to
process: there is no migration bug to fix and no pre-existing engine gap newly
surfaced. The replay's 12 snapshots drive actions that raise no choice-layer
Player Queries (consistent with the V1 baseline, where the scripted player's
empty script was never consulted), so the intent layer's Baseline Intent is not
exercised by this corpus; it is in place for replays that do raise queries.

## SOS untouched

- `git diff --stat origin/main -- benchmarks/sos/` shows zero changes under
  `benchmarks/sos/`.
- SOS replay validation runs unchanged: `_make_replay_player` returns the frozen
  `engine.player.DeterministicPlayer` (V1) when the SOS engine is on `sys.path`,
  and a full run of `sample_replay.json` against the SOS engine completes without
  crashing (the executor change is a backward-compatible factory). The replay
  shared-layer changes are additive (new enum members, a new factory, a new
  classifier, a new CLI flag) — no V1 behavior path is altered.
