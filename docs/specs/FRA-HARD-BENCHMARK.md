Status: DRAFT

Last updated: 2026-10-05

# FRA Hard Benchmark

`fra-hard-v2` is a ten-card implementation benchmark combining five Reality Fracture cards with the five previously selected HOB hard cards.

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

`benchmarks/fra-hard-v2/config.json` records each selected card as a qualified `set:collector_number` identifier.
The primary set is FRA and the additional set is HOB.
An unqualified collector number in an existing benchmark still denotes its primary set.
Staging, oracle selection, grading, and result reporting preserve the set of each card.
Collector numbers in different sets are distinct targets even when their numbers match.

### Workspaces and instructions

The candidate Workspace is ported from the Known-Best Workspace with `scripts/port_from_known_best.py`: the Known-Best engine and FDN implementations plus the benchmark's Known Defects.
It contains ten behavior-free card stubs with Card Specs under `cards/fra/fra_<N>/` and `cards/hob/hob_<N>/`, and `cards/fra/tokens.py` predefines the Jace token "empower Jace" creates and its abilities.
Both parts of preparation and Adventure cards belong to their one target card.
Each stub predefines one behavior-free class per face and per printed line of text, such as `GlamdringFoehammer` and `GleamOfDeath`, or `EmrakulTheExigentDoomAbility1`; how those classes relate is the candidate's design (grilling 2026-10-04).
Each Benchmark Run implements the entire ten-card pool in one Workspace.

Hard-tier guidance supplies workspace conventions and Card Specs without per-card implementation hints.
Candidates may change the engine, but their implementations must preserve FDN and engine behavior.
The Player Query / Player Decision protocol is described in [Decision Model](DECISION-MODEL.md).
The workspace documents describe the Priority Query as how the game runs — the set of choices a real player may make at that moment — state that every option carries the predefined class it stands for in its `printed` attr and that an illegal choice is rejected with `InvalidPlayerChoiceError`, and say nothing about how a multi-face card should be modelled or presented (grilling 2026-10-04).

The host-only Test Oracle Workspace is independent of the candidate Workspace.
Oracle-specific engine extensions are kept as `data/oracle_patches/*.patch` against the Known-Best engine and applied when the oracle is ported; target implementations live under `data/test_oracle_workspace/`.
They are never staged into the candidate Workspace.
Audited Tests live under `data/tests/audited/<set>/<card_id>/tests.py` and are mirrored into the Test Oracle Workspace for validation.
Candidate-authored tests do not replace these suites.

### Evaluation

The three evaluation dimensions are target-card correctness across FRA and HOB, FDN card regression, and engine regression.
Target results retain canonical IDs such as `fra_159` and `hob_33`.
There is no extra weighting for a card's set or rarity.

Audited Tests exercise observable gameplay through the public engine and test interfaces.
The candidate and oracle Workspaces provide the byte-identical, benchmark-owned [Test Interface](TEST-INTERFACE.md) and its documentation; `test_utils.py` is only the Reference Tests' helper module (grilling 2026-10-05).
Each selected card has at most 30 tests, covering its positive behavior, restrictions, and relevant interactions.
Validation must account for all ten selected cards and fail on missing implementations, missing suites, or unsynchronized oracle test copies.
The oracle must also pass FDN and engine regression checks.

The audited coverage includes target legality and zone changes, permission lifetimes, mana and life payment boundaries, copy characteristics, countered spells and abilities, and effects whose controller changes before resolution.
Separate oracle regression tests exercise interactions between selected cards.
Selected per-card hidden suites also exercise explicit cross-card interactions: Bilbo imports the Workspace's Glamdring implementation to test the discount on a legal cast from exile after its Adventure resolves, with a payment control without Bilbo; Hall imports Bloodline Recollector to test preparing and casting the copied inset spell (grilling 2026-10-03).
These interactions intentionally depend on both selected implementations; a failure can originate in either card or the shared engine.
The test envelope uses the baseline engine's two-player games; multiplayer variants and arbitrary additional casting costs are outside the validated scope.

Play is driven through Priority Queries, so the casting call's signature is not part of the test contract (grilling 2026-10-04).
Adopting them made fra-hard-v2 a separate benchmark, `benchmarks/fra-hard-v2/`, with the same pool, ported from the Known-Best Workspace and starting in Beta.
fra-hard v1 stays read-only with its runs and grades: it takes no fixes and no new runs, and its runs are never regraded against fra-hard-v2's suites (grilling 2026-10-04).

Execution and network-less candidate grading follow [Karn Benchmark Contract](KARN-BENCHMARK-CONTRACT.md).
The benchmark starts in Beta while candidate calibration is pending.
Completing the oracle and tests does not by itself promote the benchmark to Benchmarking or claim that candidate calibration has occurred.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-010](../adr/ADR-010-test-oracle-workspace-uses-independent-engine.md) | Oracle mechanics use an independent engine while audited behavior remains portable |
| [ADR-011](../adr/ADR-011-three-tier-benchmark-locking.md) | Benchmark tier locking |
| [ADR-012](../adr/ADR-012-independent-host-for-karn-benchmark-candidates.md) | Independent execution of prebuilt Karn candidates |
| [ADR-017](../adr/ADR-017-priority-actions-are-player-queries.md) | Priority actions are Player Queries chosen through the players' answers |
| [ADR-018](../adr/ADR-018-audited-tests-play-as-two-players-at-a-table.md) | Audited Tests build a position, play it and judge it only as players at the table would |
