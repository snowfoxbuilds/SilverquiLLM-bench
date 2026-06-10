Status: DRAFT

Last updated: 2026-06-10

# MSH Benchmark

Structure and scope of the MSH benchmark: card pool, repo layout, the sharing boundary with the harness, and what changed from V1 (SOS).

## Context

SOS (V1) surfaced engine shortfalls that audited tests had to work around (turn structure, cost/mana introspection, positional choice scripting). MSH is the next benchmark generation: a brand-new card pool that minimizes training-data contamination, with an engine and test API designed for richer, more faithful card behavior.

## Design

### Card pool

- Set: Magic: The Gathering | Marvel Super Heroes (MSH), the 112th Magic expansion. Release 2026-06-26; prerelease 2026-06-19 to 06-25; MTG Arena 2026-06-23.
- Card definitions are available now via the official card image gallery and Scryfall's MSH set page, including the new set mechanics power-up and teamwork.
- A brand-new set means no model has seen MSH implementations; the fresh mechanics are natural stress tests for the Player Choice / Decision Model (see [MSH-DECISION-MODEL.md](http://msh-decision-model.md/)).
### Repo layout and sharing boundary

- `benchmarks/msh` is fully decoupled from `benchmarks/sos`: breaking and sweeping changes are allowed immediately, with no compatibility constraints.
- Shared: the benchmark harness — runner / evaluator / CLI in `silverquillm/` — refactored benchmark-agnostic where needed.
- New or duplicated under `benchmarks/msh`: engine, test API (Player Query / Player Decision / Intent native from day one), oracles, audited tests, conformance gate, and card data.
- SOS is frozen as the V1 benchmark: tag the final commit for comparability; no retrofits (fdn_81 coupling, the `sos_*`-only conformance gate, and the hardcoded `_AUDITED_CARDS` stay as-is unless SOS is ever rerun).
### Scoring

- Complexity tiers are dropped completely: no `complexity_tier` in card data or specs, no weighted scoring, no per-tier breakdowns. Scoring is raw pass/total. If difficulty grouping is ever needed, the checkpoint capability DAG covers it (see [MSH-CHECKPOINTS.md](http://msh-checkpoints.md/)).
### V1 carryover issues to resolve or consciously accept

From the 2026-06-10 repo audit, open items that carry into MSH:

- Engine capability gaps: single main phase / no turn-crossing / no turn-skip; no mid-resolution stack removal; no `mana_spent` introspection; no split/adventure casting; self-ETB effects via `on_resolve` instead of triggers; `set_board_state` gaps; only 3 counter types; silently filtered combat illegality; simultaneous-trigger ordering deferred; self-draining resolutions; unported V1 mechanics (multiplayer, sideboard/BO3, companion/partner, dungeons/Ring, day/night, voting, ante).
- Harness: long per-card timeouts (approx. 15–28 min); `_AUDITED_CARDS` hardcoded to 10 — generalize via `_discover_oracle_cards()` before the first MSH oracles; the AST conformance gate scans only `sos_*`.
- Hygiene: stale `KNOWN-ISSUES.md` and `TODO.md` Phase 19 checkboxes; the Phase 19 promotion pipeline has produced zero promoted oracles; unreviewed churn on main since 6/9.
## Decisions

- **`benchmarks/msh`**** decoupled from ****`benchmarks/sos`**: engine, test API, oracles, audited tests, conformance gate, and card data are per-benchmark; only the harness is shared. [SETTLED — 2026-06-10]
- **SOS frozen as V1**: tag the final commit; no retrofits. [SETTLED — 2026-06-10]
- **Complexity tiers dropped**: raw pass/total scoring only. [SETTLED — 2026-06-10]
- **Baseline state**: `benchmarks/msh` starts as a baseline dup of `benchmarks/sos` with MSH card stubs. [SETTLED — 2026-06-10]
- **Benchmark identity fixed at baseline**: `config.json` carries `id: "msh"` and tier Beta (ADR-011 vocabulary); the SOS-derived `prototype_cards.json` / `prototype_gaps.md` were deleted rather than regenerated. Real card data comes from `fetch_data.py` → `data/msh.json`. [SETTLED — Grilling 2026-06-10]
- **Repo-level ****`tests/`**** harness goes benchmark-parameterized**: discovery driven by `benchmarks/*/config.json` (per-benchmark audited-card lists and `{id}_*` scan scope, replacing the hardcoded `_AUDITED_CARDS` and `sos_*` glob); MSH gets its own conformance rule-set written against the Player Query API; the SOS checker stays byte-for-byte frozen. [SETTLED — Grilling 2026-06-10]
- **Single canonical audited-test tree**: MSH audited tests live only in `benchmarks/msh/data/tests/`, staged into the oracle workspace at run/bootstrap time; no committed second copy and no sync tripwire — structurally eliminates the V1 drift class (sos_257 incident). [SETTLED — Grilling 2026-06-10]
