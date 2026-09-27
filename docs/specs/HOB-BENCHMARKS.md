Status: DRAFT

Last updated: 2026-09-26

# HOB Benchmarks

The three HOB-generation benchmarks — hob-easy, hob-medium, hob-hard — succeeding the abandoned MSH benchmark. The MSH pages (MSH-BENCHMARK.md, MSH-CHECKPOINTS.md) were deleted from `docs/specs/` at grilling 2026-09-02; their text survives only in git history.

## Context

MSH aged out as a contamination-fresh pool before any benchmark ran on it. Its pool-agnostic work — the V2 engine with the Player Query / Player Decision protocol ([DECISION-MODEL.md](DECISION-MODEL.md)), the intent-based DeterministicPlayer (V2), the migrated FDN implementations, and the replay-validation substrate (closed clean, residue 100% attributed with no further burn-down phases; see PROJECT-OVERVIEW.md Phase 3) — carries forward wholesale *(grilling 2026-08-27)*.

## The three benchmarks

One benchmark = one problem set. Each tier is a **separate benchmark** with its own `config.json`, card pool, audited-test tree, and lock tier — never workloads or modes of a shared benchmark *(grilling 2026-08-27)*. The three benchmarks are three **selective subsets** of the HOB set, never the whole set (unlike SOS, whose Card Pool is the entire SOS Draft Set) *(grilling 2026-09-02)*. The operator picks all cards. Work starts with hob-medium.

| Benchmark | Cards | Agent-visible instructions | Tests | Engine-change requirement |
| --- | --- | --- | --- | --- |
| `hob-easy` | 23 straightforward | Clear instructions + pitfalls | Pure implementation + large-context handling | Little/none |
| `hob-medium` | 5 medium | Detailed instructions + pitfalls | Regular implementation task | Some |
| `hob-hard` | 5 difficult | None (card spec only) | Reasoning / exploration | Extensive |

Required-engine-change depth is the difficulty knob *(grilling 2026-08-27)*. Tiers differ only in *what the agent is given*, never in how they are scored.

## Card pool source

Magic: The Gathering | The Hobbit, main expansion set code HOB, released 2026-08-14; raw set data pinned at `data/sets/hob.json`. The set is **321 printings of 193 unique cards**: collector numbers 001–193 are the first printings (187 main-set cards, Mirkwood at 188, five basic lands at 189–193) and 194–321 are alternate printings — booster-fun variants and extra basics — of cards already in 001–193. Pools always reference a card's first-printing collector number; pool derivation from `hob.json` must ignore 194–321 *(grilling 2026-09-02)*. Mechanics: Adventure (primary returning), Storied, Recruit, hone counters, Amass.

## Pools

Operator picks, made 2026-08-28 (hard, medium) and 2026-09-01 (easy) on issue #62; recorded here at grilling 2026-09-02 as the authoritative pool lists. Collector numbers are first printings (see Card pool source). Each benchmark's `config.json` `cards` and `data/` pool are populated from these lists by the pool-work issues; hob-easy is 23 cards (the 2026-08-27 sizing target of 20 was a placeholder). Work tracking lives in GitHub issues under the HOB-generation tracking issue #67, not in `TODO.md` (`TODO.md` and `docs/TODO_COMPLETED.md` are retired and deleted); #62 stays at its groundwork scope with `hob-medium/config.json` `cards` empty, the hob-medium pool / oracle / audited-test / instruction-doc work is a follow-on issue, and the hob-easy / hob-hard trees come later still *(grilling 2026-09-02)*.

**hob-hard (5)** — extensive engine changes:

| # | Card | Why it's hard |
| --- | --- | --- |
| 33 | Bilbo, Thief in the Night | Cast-zone-conditional cost reduction + attack-triggered graveyard casting with exile-instead replacement |
| 76 | Inside Information | Play from opponent's library exile, turn-scoped permission, pay-life alternative cost |
| 86 | Supper for Spiders | Turn-scoped from-battlefield death tracking, mass reanimation under your control, permanent type/subtype overwrite to Food with granted ability |
| 167 | Thranduil, the Elvenking | Dynamically borrows all activated abilities of Elf cards in graveyard |
| 174 | Glamdring, Foe-hammer // Gleam of Death | Adventure mechanic (no engine support today) + power-scaled cost reduction on Equipment |

**hob-medium (5)** — one or two scoped engine additions each:

| # | Card | New engine surface |
| --- | --- | --- |
| 12 | The Eagles Are Coming! | Kicker + delayed trigger at next upkeep |
| 36 | Elrond, Moon-Reader | Ability-activation trigger (once/turn) + exile-return-at-end-step delayed trigger |
| 70 | Gollum, Riddle Master | As-enters choice + parity-filtered opponent-cast trigger + modal with persistent choice memory |
| 131 | The Notary Hobbits | ETB token copies (except-not-legendary) + count-based mana ability |
| 169 | Tom, Bert, and William | Sacrifice-cost draw engine + death-trigger return as non-creature artifact (self characteristic override) |

**hob-easy (23)** — implementable with existing engine primitives (scry/fight/recruit-style helpers are card-level code):

| # | Card | Interest |
| --- | --- | --- |
| 10 | Dwarven Shortsword | ETB create token, then attach to it |
| 13 | Esgaroth Garrison | Characteristic-defining power + recruit |
| 16 | Iron Hills Blacksmith | Creates an Equipment token with its own equip ability |
| 20 | Magnificent End | Cost reduction conditional on targeting a tapped creature |
| 21 | Moment of Glory | Flashback + cast-from-graveyard bonus |
| 27 | Stone by Sunlight | Modal; type-add + indestructible until end of turn |
| 35 | Confusticate and Bebother | Modal counter-unless-pays / loot |
| 48 | Mirkwood Meditator | Landfall optional base-P/T change |
| 58 | Uneasy Partings | Target-conditional cost reduction + owner's top/bottom choice |
| 64 | Desolation Prowler | Pay-life activation, once-per-turn limit |
| 66 | Dreaded Bat-Cloud | Cost reduction if a creature died this turn |
| 69 | Gnashing of Teeth | Modal + would-die→exile replacement rider |
| 84 | Stir Up Trouble | Additional cost with a choice (sacrifice or pay {4}) |
| 95 | Dwarven Mauler | Reduces equip-ability activation costs |
| 97 | Gandalf, Spark Starter | Damage divided as you choose among up to three targets |
| 107 | Pinecone Strike | "Choose one or both" modal + exile-instead |
| 125 | Galion, Elvenking's Butler | Sets another creature's base P/T to his until end of turn |
| 139 | Warg Tactics | Modal removal / keyword grants |
| 140 | Wargling | Ferocious conditional attack trigger |
| 143 | Woodland Weavemaster | Scaling mana ability restricted to Elf spells/sources |
| 145 | Bard the Bowman | Second-card-drawn-each-turn trigger |
| 171 | The Black Arrow | Flash Equipment; ETB ping with conditional Dragon destroy |
| 172 | Dwarven Mattock | ETB auto-attach + grants ward |

Deliberately excluded from every pool: Sagas and Vehicles (each a whole new subsystem) and cards with observable randomness (#98 Getaway Barrel, #134 Part in Friendship), which conflict with the deterministic replay substrate.

## Run shape

- A Benchmark Run is one container session consuming the benchmark's **entire** problem set in a single Workspace. There is no card-subset ("workload") notion — that term is retired (CONTEXT.md) *(grilling 2026-08-27)*.
- Cheap pipeline validation / candidate calibration uses a dedicated **smoke benchmark**: its own small problem set of already-validated FDN cards (known-good oracles and audited tests), never leaderboard-published, run like any other benchmark.
- Checkpoints are retired (the MSH-CHECKPOINTS.md design page is deleted; see git history); resume legs cover crash recovery instead *(grilling 2026-08-27)*.
- Runs use [Karn Benchmark Contract](KARN-BENCHMARK-CONTRACT.md): run spec = candidate + benchmark + budget (grilling 2026-09-26).
  Karn builds the immutable image and v4 Construct Definition before the run; the bench launches the candidate independently and grades its harvested implementation.
  No PR metadata, Implementer proposal, or production test/docs/lint gate is required.
  The first scored HOB run uses this contract; the legacy entrypoint lineage remains ineligible.

## Repo layout

- No `benchmarks/hob/` umbrella. `benchmarks/msh/` is `git mv`-renamed to `benchmarks/hob-medium/`, persisting the FDN/engine git history; MSH pool artifacts (`data/msh.json`, MSH card stubs, `fetch_data.py` MSH targeting) are deleted in the move *(grilling 2026-08-27)*.
- `hob-easy/` and `hob-hard/` are created later as **hard copies** of the FDN set + engine (the SOS↔MSH decoupling rule applies between sibling benchmarks too; drift between tiers is accepted by design).
- Full HOB set data is fetched once to the shared `data/sets/hob.json` (raw Scryfall material, benchmark-neutral). Each benchmark's `data/` holds only its own pool, derived from it.

## Engine rules

- **Freeze**: the agent-visible workspace engine locks when a tier enters Benchmarking (the tier-locking machinery). Within a lock tier, every candidate sees the identical engine — this is what makes "requires some engine changes" a stable property of the benchmark. Oracle iteration touches HOB card implementations, audited tests, and instruction docs only — never the FDN implementations or the staged workspace engine *(grilling 2026-08-27)*.
- **Agent envelope**: agents may modify the workspace engine freely — no additive-only rule, no diff policing. The three audited dimensions are the entire judgment, all run against the harvested engine: HOB card correctness, FDN card regression, engine regression *(grilling 2026-08-27)*. Audited tests judge card behavior by simulating gameplay (implementation-agnostic testing); this mechanism is already implemented.

## Instruction documents

- Two granularities per tier: a benchmark-level conventions document (engine conventions, what a good implementation looks like, the envelope rule above) and a per-card `instructions.md` beside `card_spec.json`, staged into the workspace card directory *(grilling 2026-08-27)*.
- Pitfalls are **discovered, not invented**: authored from what the oracle implementation actually surfaced (oracle-first workflow; the oracle iterates while benchmarks run).
- Instruction docs shape difficulty as much as the pool does: they are locked benchmark data, frozen with the tier at Benchmarking; changing them afterward is a benchmark-version event.
- Per tier: hob-easy clear, hob-medium detailed, hob-hard none.
- Planning and task guidance are part of each benchmark's instruction data; the Karn integration adds no independent basic/planned selector (grilling 2026-09-26).

## hob-medium benchmark assets

hob-medium is the HOB benchmark completed in the Karn v4 integration workstream, including its oracle (grilling 2026-09-26).
Its Card Pool is the five already-selected entries in the Pools section; no new card selection is required.
The agent-visible Workspace contains the V2 engine and FDN baseline, the selected HOB Card Specs and behavior-free candidate stubs, and the benchmark's instruction documents.

The host-only Test Oracle Workspace mirrors that baseline and holds a Test Oracle Impl for every selected card.
Oracle mechanics that require engine additions live in its independent engine, not in the candidate baseline merely to make the oracle work.
Audited Tests exercise observable behavior through the canonical public API and pass against the matching oracle.
Each card has at most 30 Audited Tests, following the project testing conventions.

Benchmark validation accounts for every selected card and reports missing or stub oracle implementations and missing tests; silently skipping them does not establish completeness.
The target card set is hob, while the benchmark is hob-medium; validation and promotion resolve those identities separately.
All three evaluation dimensions have explicit test coverage, including an FDN regression suite validated against the V2 baseline.
Existing SOS tests can supply source material, but copying them alone does not establish V2 compatibility.
Medium's instructions and pitfalls are derived from the oracle work and follow the existing Benchmark Tier locking rules.

Development runs and incomplete observations remain useful data; the integration retains their evidence without a leaderboard eligibility gate (grilling 2026-09-26).

## Evaluation

Oracle-first audited tests are the sole scored method for all three tiers (Audited Eval, unchanged pipeline): oracle implementation → audited tests drafted against it → human failure-review → agent runs scored on the three dimensions.

## Relevant ADRs

| ADR | Decision |
|---|---|
| [ADR-008](../adr/ADR-008-resume-legs-are-independent-benchmark-runs.md) | Resume Legs Are Independent Benchmark Runs |
| [ADR-009](../adr/ADR-009-resume-reads-prefer-run-time-artifacts-over-harvest-time-artifacts.md) | Resume Reads Prefer Run-Time Artifacts Over Harvest-Time Artifacts |
| [ADR-010](../adr/ADR-010-test-oracle-workspace-uses-independent-engine.md) | Oracle mechanics use an independent engine while tests remain portable across implementations |
| [ADR-011](../adr/ADR-011-three-tier-benchmark-locking.md) | Three-Tier Benchmark Locking |
| [ADR-0012](../adr/ADR-0012-independent-host-for-karn-benchmark-candidates.md) | Independent execution of prebuilt Karn candidates |
