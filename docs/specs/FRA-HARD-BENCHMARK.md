Status: DRAFT

Last updated: 2026-10-02

# FRA Hard Benchmark

`fra-hard` is a ten-card implementation benchmark combining five Reality Fracture cards with the five previously selected HOB hard cards.

## Context

This pool tests substantial engine extensions across copying, casting permissions, zone changes, preparation, and planeswalker rules.
It uses the V2 Player Query / Player Decision protocol and the independent Karn execution contract.
The HOB selections retain their original card identities; they are not relabeled as FRA cards.

## Design

### Card Pool

The operator selected this pool on 2026-10-02.
Collector numbers identify the original printings, not alternate treatments.

| Set | Collector number | Card |
| --- | --- | --- |
| FRA | 1 | Emrakul, the Exigent Doom |
| FRA | 49 | Bloodline Recollector // Ancestral Craving |
| FRA | 64 | Sanctum Lurker |
| FRA | 159 | Uldaros Theorix |
| FRA | 179 | Hall of Echoes |
| HOB | 33 | Bilbo, Thief in the Night |
| HOB | 76 | Inside Information |
| HOB | 86 | Supper for Spiders |
| HOB | 167 | Thranduil, the Elvenking |
| HOB | 174 | Glamdring, Foe-hammer // Gleam of Death |

`benchmarks/fra-hard/config.json` records each selected card as a qualified `set:collector_number` identifier.
The primary set is FRA and the additional set is HOB.
An unqualified collector number in an existing benchmark still denotes its primary set.
Staging, oracle selection, grading, and result reporting preserve the set of each card.
Collector numbers in different sets are distinct targets even when their numbers match.

### Workspaces and instructions

The candidate Workspace is a self-contained copy of the HOB-generation V2 engine and FDN reference baseline.
It contains ten behavior-free card stubs with Card Specs under `cards/fra/fra_<N>/` and `cards/hob/hob_<N>/`.
Both parts of preparation and Adventure cards belong to their one target card.
Each Benchmark Run implements the entire ten-card pool in one Workspace.

Hard-tier guidance supplies workspace conventions and Card Specs without per-card implementation hints.
Candidates may change the engine, but their implementations must preserve FDN and engine behavior.
The Player Query / Player Decision protocol is described in [Decision Model](DECISION-MODEL.md).

The host-only Test Oracle Workspace is independent of the candidate Workspace.
Oracle-specific engine extensions and target implementations live under `data/test_oracle_workspace/`.
They are never staged into the candidate Workspace.
Audited Tests live under `data/tests/audited/<set>/<card_id>/tests.py` and are mirrored into the Test Oracle Workspace for validation.
Candidate-authored tests do not replace these suites.

### Evaluation

The three evaluation dimensions are target-card correctness across FRA and HOB, FDN card regression, and engine regression.
Target results retain canonical IDs such as `fra_159` and `hob_33`.
There is no extra weighting for a card's set or rarity.

Audited Tests exercise observable gameplay through the public engine and test interfaces.
The candidate and oracle Workspaces provide byte-identical `test_utils.py` helpers and matching API documentation.
For this benchmark, `resolve_stack` checks state-based actions before resolving the stack, including when the stack is empty.
Each selected card has at most 30 tests, covering its positive behavior, restrictions, and relevant interactions.
Validation must account for all ten selected cards and fail on missing implementations, missing suites, or unsynchronized oracle test copies.
The oracle must also pass FDN and engine regression checks.

The audited coverage includes target legality and zone changes, permission lifetimes, mana and life payment boundaries, copy characteristics, countered spells and abilities, and effects whose controller changes before resolution.
Separate oracle regression tests exercise interactions between selected cards without importing another target's implementation into a per-card hidden suite.
The test envelope uses the baseline engine's two-player games; multiplayer variants and arbitrary additional casting costs are outside the validated scope.

Execution and network-less candidate grading follow [Karn Benchmark Contract](KARN-BENCHMARK-CONTRACT.md).
The benchmark starts in Beta while candidate calibration is pending.
Completing the oracle and tests does not by itself promote the benchmark to Benchmarking or claim that candidate calibration has occurred.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-010](../adr/ADR-010-test-oracle-workspace-uses-independent-engine.md) | Oracle mechanics use an independent engine while audited behavior remains portable |
| [ADR-011](../adr/ADR-011-three-tier-benchmark-locking.md) | Benchmark tier locking |
| [ADR-012](../adr/ADR-012-independent-host-for-karn-benchmark-candidates.md) | Independent execution of prebuilt Karn candidates |
