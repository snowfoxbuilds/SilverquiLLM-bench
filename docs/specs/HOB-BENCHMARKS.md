Status: DRAFT (created at grilling 2026-08-27; amended at grilling 2026-09-02 — pools recorded, set/pool relationship sharpened, work tracking moved to issues)

# HOB Benchmarks

The three HOB-generation benchmarks — hob-easy, hob-medium, hob-hard — succeeding the abandoned MSH benchmark (see MSH-BENCHMARK.md, ABANDONED).

## Context

MSH aged out as a contamination-fresh pool before any benchmark ran on it. Its pool-agnostic work — the V2 engine with the Player Query / Player Decision protocol ([DECISION-MODEL.md](DECISION-MODEL.md)), the intent-based DeterministicPlayer (V2), the migrated FDN implementations, and the replay-validation substrate (closed clean; see PROJECT-OVERVIEW.md Phase 3) — carries forward wholesale.

**Card pool source**: Magic: The Gathering | The Hobbit, main expansion set code HOB, released 2026-08-14; raw set data pinned at `data/sets/hob.json`. The set is **321 printings of 193 unique cards**: collector numbers 001–193 are the first printings (187 main-set cards, Mirkwood at 188, five basic lands at 189–193) and 194–321 are alternate printings — booster-fun variants and extra basics — of cards already in 001–193. Pools always reference a card's first-printing collector number; pool derivation from `hob.json` must ignore 194–321 *(grilling 2026-09-02)*. Mechanics: Adventure (primary returning), Storied, Recruit, hone counters, Amass.

## The three benchmarks

One benchmark = one problem set. Each tier is a **separate benchmark** with its own `config.json`, card pool, audited-test tree, and ADR-011 lock tier — never workloads or modes of a shared benchmark. The three benchmarks are three **selective subsets** of the HOB set, never the whole set (unlike SOS, whose Card Pool is the entire SOS Draft Set) *(grilling 2026-09-02)*. The operator picks all cards. Work starts with hob-medium.

| Benchmark | Cards | Agent-visible instructions | Tests | Engine-change requirement |
| --- | --- | --- | --- | --- |
| `hob-easy` | 23 straightforward | Clear instructions + pitfalls | Pure implementation + large-context handling | Little/none |
| `hob-medium` | 5 medium | Detailed instructions + pitfalls | Regular implementation task | Some |
| `hob-hard` | 5 difficult | None (card spec only) | Reasoning / exploration | Extensive |

Required-engine-change depth is the difficulty knob. Tiers differ only in *what the agent is given*, never in how they are scored.

## Pools

Operator picks, made 2026-08-28 (hard, medium) and 2026-09-01 (easy) on issue #62; recorded here at grilling 2026-09-02 as the authoritative pool lists. Collector numbers are first printings (see Card pool source). Each benchmark's `config.json` `cards` and `data/` pool are populated from these lists by the pool-work issues; hob-easy is 23 cards (the 2026-08-27 sizing target of 20 was a placeholder).

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

- A Benchmark Run is one container session consuming the benchmark's **entire** problem set in a single Workspace. There is no card-subset ("workload") notion — that term is retired (CONTEXT.md).
- Cheap pipeline validation / candidate calibration uses a dedicated **smoke benchmark**: its own small problem set of already-validated FDN cards (known-good oracles and audited tests), never leaderboard-published, run like any other benchmark.
- Checkpoints are retired (MSH-CHECKPOINTS.md, RETIRED). ADR-008/009 resume legs cover crash recovery.
- Runs happen under the worker-type candidate contract (issue #39): run spec = candidate + mode + benchmark + budget. **No scored HOB run happens on the legacy entrypoint lineage** — the first scored HOB run is the new contract's first consumer.

## Repo layout

- No `benchmarks/hob/` umbrella. `benchmarks/msh/` is `git mv`-renamed to `benchmarks/hob-medium/`, persisting the FDN/engine git history; MSH pool artifacts (`data/msh.json`, MSH card stubs, `fetch_data.py` MSH targeting) are deleted in the move.
- `hob-easy/` and `hob-hard/` are created later as **hard copies** of the FDN set + engine (the SOS↔MSH decoupling rule applies between sibling benchmarks too; drift between tiers is accepted by design).
- Full HOB set data is fetched once to the shared `data/sets/hob.json` (raw Scryfall material, benchmark-neutral). Each benchmark's `data/` holds only its own pool, derived from it.

## Engine rules

- **Freeze**: the agent-visible workspace engine locks when a tier enters Benchmarking (ADR-011 machinery). Within a lock tier, every candidate sees the identical engine — this is what makes "requires some engine changes" a stable property of the benchmark. Oracle iteration touches HOB card implementations, audited tests, and instruction docs only — never the FDN implementations or the staged workspace engine.
- **Agent envelope**: agents may modify the workspace engine freely — no additive-only rule, no diff policing. The three audited dimensions are the entire judgment, all run against the harvested engine: HOB card correctness, FDN card regression, engine regression. Audited tests judge card behavior by simulating gameplay (implementation-agnostic testing); this mechanism is already implemented.

## Instruction documents

- Two granularities per tier: a benchmark-level conventions document (engine conventions, what a good implementation looks like, the envelope rule above) and a per-card `instructions.md` beside `card_spec.json`, staged into the workspace card directory.
- Pitfalls are **discovered, not invented**: authored from what the oracle implementation actually surfaced (oracle-first workflow; the oracle iterates while benchmarks run).
- Instruction docs shape difficulty as much as the pool does: they are locked benchmark data, frozen with the tier at Benchmarking; changing them afterward is a benchmark-version event.
- Per tier: hob-easy clear, hob-medium detailed, hob-hard none.

## Evaluation

Oracle-first audited tests are the sole scored method for all three tiers (Audited Eval, unchanged pipeline): oracle implementation → audited tests drafted against it → human failure-review → agent runs scored on the three dimensions.

## Decisions

- **FDN replay validation closed**; residue 100% attributed, no further burn-down phases. [SETTLED — Grilling 2026-08-27]
- **MSH abandoned as a benchmark; pool-agnostic work kept.** [SETTLED — Grilling 2026-08-27]
- **Tiers are separate benchmarks**, not workloads/modes. [SETTLED — Grilling 2026-08-27]
- **"Workload" retired**; run spec = candidate + mode + benchmark + budget; smoke via dedicated smoke benchmark. [SETTLED — Grilling 2026-08-27]
- **Layout**: `msh` → `hob-medium` rename preserving history; easy/hard as later hard copies; shared raw set data in `data/sets/hob.json`. [SETTLED — Grilling 2026-08-27]
- **Engine freeze at Benchmarking; oracle iterates on HOB impls/tests only.** [SETTLED — Grilling 2026-08-27]
- **Tests-as-envelope**: engine freely modifiable; the three audited dimensions are the whole judgment. [SETTLED — Grilling 2026-08-27]
- **Checkpoints retired.** [SETTLED — Grilling 2026-08-27]
- **Instruction docs**: tier conventions doc + per-card `instructions.md`, oracle-derived, locked with the tier. [SETTLED — Grilling 2026-08-27]
- **Engine-change depth is the difficulty knob** (easy little/none, medium some, hard extensive). [SETTLED — Grilling 2026-08-27]
- **Pools picked for all three tiers** (see Pools); hob-easy is 23 cards, not the 20 first targeted. [SETTLED — Grilling 2026-09-02]
- **HOB benchmarks are selective subsets** of the HOB set; pools reference first-printing collector numbers (001–193), and the alternate printings at 194–321 are never pool members. [SETTLED — Grilling 2026-09-02]
- **Work tracking lives in GitHub issues, not `TODO.md`**: `TODO.md` / `docs/TODO_COMPLETED.md` are retired and deleted; pending work is an issue under the HOB-generation tracking issue #67. #62 stays at its groundwork scope with `hob-medium/config.json` `cards` empty; the hob-medium pool / oracle / audited-test / instruction-doc work is a follow-on issue, and the hob-easy / hob-hard trees come later still. [SETTLED — Grilling 2026-09-02]
- **Candidate contract**: candidates enter as self-contained Candidate Bundles (adapter-agnostic; claude + codex today, Pi later); identity independently recomputed; bench driver imitates the substrate job-dir contract at full fidelity (synthetic-issue task file, `input/` tree, `output/proposal.json` applied post-exit). [SETTLED — Grilling 2026-08-27]
