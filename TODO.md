## Phase 5: Replay Validation Pipeline

Scope: Implement engine extensions and the 10 FDN Special Guests cards (SPG #74–83), build the 17lands GRE JSON replay parser, and build the validation pipeline that replays recorded games against the engine using state-diff comparison in observer mode. See [ADR-003](https://www.notion.so/37a8b903f91b4309a15b91d149a90f7c) for the architectural rationale and [17lands Replay Data Schema](https://www.notion.so/35b6a7adc8ed80978dccdf724213b6f8) for the data format.

---

### Engine Extensions for SPG Cards

- [x] **Hybrid mana parsing and cost payment**
  Detail: Extend `ManaCost.parse()` to handle hybrid mana symbols like `{B/G}`. A hybrid symbol can be paid with either color. Fiend Artisan (SPG #83) costs `{B/G}{B/G}` — each symbol payable with black or green.

  Changes needed:

  - `engine/mana.py`: Update `ManaCost.parse()` regex to recognize `{X/Y}` hybrid symbols
  - `engine/mana.py`: Update `ManaPool.pay()` to handle hybrid choices (try each option, backtrack if needed)
  - `engine/types.py`: Add `HybridManaSymbol` type if needed
  Keep it generic — support any two-color hybrid, not just B/G. Phyrexian mana (`{W/P}`) is NOT needed yet.

  Reference: Check `KEY_DECISIONS.md` for mana parsing conventions from Phase 1.

  Testability: Unit test parsing `{B/G}{B/G}` → correct ManaCost. Test payment with pool containing only black, only green, and mixed. Test that `{W/U}` and other hybrid pairs also work.

- [x] **Cost reduction during casting**
  Detail: Implement a cost-reduction hook in the casting pipeline. Embercleave (SPG #77) costs `{4}{R}{R}` but costs `{1}` less for each attacking creature you control.

  Changes needed:

  - `engine/casting.py`: Add a `get_cost_reduction(game_state, card, controller)` hook called during cost calculation, before mana payment. Cards override this to return a generic mana reduction amount.
  - `engine/card.py` or `CardImpl`: Add `cost_reduction(self, game_state) -> int` method (default 0). Embercleave overrides this.
  - Reduction only applies to generic mana (cannot reduce colored costs below their minimum).
  Design note: Simplified model — single-card self-reduction only. Full MTG cost reduction (Trinisphere, multiple reductions) deferred.

  Testability: Unit test that a card with cost `{4}{R}{R}` and reduction of 3 costs `{1}{R}{R}`. Test reduction can’t go below 0 generic. Test with 0 reduction (full cost).

- [x] **Protection from qualities (keyword ability)**
  Detail: Implement "protection from [quality]" keyword. Akroma’s Memorial (SPG #81) grants protection from black and from red. Protection prevents: **D**amage from sources with that quality, **E**nchanting/equipping by permanents with that quality, **B**locking by creatures with that quality, **T**argeting by spells/abilities from sources with that quality (DEBT mnemonic).

  Changes needed:

  - `engine/abilities.py` or `engine/keywords.py`: Add `ProtectionAbility(quality)` class. Quality can be a color, card type, or arbitrary predicate.
  - `engine/combat.py`: Check protection during blocking legality
  - `engine/targeting.py`: Check protection during target legality
  - `engine/damage.py`: Apply damage prevention from protected sources
  - `engine/continuous_effects.py`: Auras/Equipment on protected permanents fall off (SBA)
  Start with color-based protection only. Framework should be extensible to other qualities later.

  Testability: Test creature with protection from red: can’t be targeted by red spells, can’t be blocked by red creatures, doesn’t take damage from red sources, red auras fall off.

- [x] **Extra turns infrastructure (stub)**
  Detail: Implement "take an extra turn after this one" as a working feature. Temporal Manipulation (SPG #82) is `{3}{U}{U}` sorcery — "Take an extra turn after this one."

  Changes needed:

  - `engine/game_state.py`: Add `extra_turns: list[int]` (list of player seat IDs, FIFO queue)
  - `engine/turn.py`: At end of turn, before passing to next player, check `extra_turns`. If non-empty, pop first entry and give that player the next turn.
  Mark as ENGINE LIMITATION — complex interactions ("skip your next turn", multiple extra turns from different sources) are not fully handled.

  Testability: Test extra turn is granted after casting. Test normal turn order resumes after extra turn. Test multiple extra turns queue correctly (FIFO).

---

### SPG Card Implementations

- [x] **SPG Batch 1: Simple spells and utility creatures (5 cards)**
  Detail: Implement the simpler Special Guest cards that need minimal or no new engine extensions:

  1. **Condemn** (SPG #74) — {W} instant. Put target attacking creature on the bottom of its owner’s library. Its controller gains life equal to its toughness. Needs: target validation (must be attacking), bottom-of-library zone move, life gain based on toughness.
  2. **Grim Tutor** (SPG #76) — {1}{B}{B} sorcery. Search your library for a card, put it into your hand, then shuffle. You lose 3 life. Needs: library search (player choice), shuffle, life loss. Check if search/shuffle already exists from Phase 4 cards.
  3. **Goblin Bushwhacker** (SPG #78) — {R} creature 1/1 Goblin Warrior. Kicker {R}. When it enters the battlefield, if it was kicked, creatures you control get +1/+0 and gain haste until end of turn. Kicker exists from Phase 4 Batch 12. Needs: kicked ETB trigger, mass temporary buff + haste grant.
  4. **Paradise Druid** (SPG #80) — {1}{G} creature 2/1 Elf Druid. Has hexproof as long as it’s untapped. {T}: Add one mana of any color. Needs: conditional hexproof (continuous effect checking `isTapped`), any-color mana ability.
  5. **Bloom Tender** (SPG #79) — {1}{G} creature 1/1 Elf Druid. {T}: For each color among permanents you control, add one mana of that color. Needs: color-among-permanents scan, multi-color mana production.
  Files: `cards/foundations/special_guests.py` (all 10 SPG cards in one file).

  Testability: Per-card unit tests. Condemn: test on attacking creature, verify bottom-of-library + life gain. Grim Tutor: test search + life loss. Bushwhacker: test kicked vs unkicked. Paradise Druid: test hexproof while untapped, loses hexproof when tapped for mana. Bloom Tender: test with various color distributions among controlled permanents.

- [ ] **SPG Batch 2: Complex permanents and spells (5 cards)**
  Detail: Implement the mechanically complex Special Guest cards. These depend on the engine extensions from earlier items.

  1. **Sphinx’s Tutelage** (SPG #75) — {2}{U} enchantment. Whenever you draw a card, target opponent mills 2. If two nonland cards that share a color were milled this way, repeat this process. {5}{U}: Draw a card, then discard a card. Needs: draw trigger, mill mechanic (top N cards from library → graveyard), repeat-loop logic (check milled cards for shared color among nonlands), activated draw+discard ability.
  2. **Embercleave** (SPG #77) — {4}{R}{R} legendary artifact — Equipment. Flash. Costs {1} less for each attacking creature you control. ETB: attach to target creature you control. Equipped creature gets +1/+1, double strike, trample. Equip {3}. Depends on: cost reduction extension. Needs: Flash keyword, ETB auto-attach, double strike keyword, equip ability. Check if Flash/double strike already exist.
  3. **Akroma’s Memorial** (SPG #81) — {7} legendary artifact. Creatures you control have flying, first strike, vigilance, trample, haste, and protection from black and from red. Depends on: protection extension. Needs: mass keyword granting via continuous effect (Layer 6). Most keywords should already exist from Phase 4.
  4. **Temporal Manipulation** (SPG #82) — {3}{U}{U} sorcery. Take an extra turn after this one. Depends on: extra turns infrastructure. Simple implementation — just calls the extra turn API on resolve.
  5. **Fiend Artisan** (SPG #83) — {B/G}{B/G} creature */* Nightmare. P/T each equal to number of creature cards in your graveyard. {X}{B/G}, {T}, Sacrifice another creature: Search library for creature with MV ≤ X, put onto battlefield, shuffle. Activate only as a sorcery. Depends on: hybrid mana extension. Needs: characteristic-defining ability (P/T = graveyard count, Layer 7a), activated ability with X cost + hybrid + tap + sacrifice, MV-restricted search, sorcery-speed-only restriction.
  Files: `cards/foundations/special_guests.py` (same file as Batch 1).

  Testability: Sphinx’s Tutelage: test draw trigger mills, test repeat loop when colors match, test it stops when colors don’t match, test activated ability. Embercleave: test cost reduction with varying attacker counts, test flash timing, test ETB attach, test double strike + trample on equipped creature. Akroma’s Memorial: test all 6 keywords granted + both protection colors. Temporal Manipulation: test extra turn granted. Fiend Artisan: test P/T tracks graveyard count, test activated ability with various X values, test sorcery-speed restriction.

---

### Replay Parsing

- [ ] **Card ID mapping (grpId → card name)**
  Detail: Download 17lands FDN card list from [17lands.com/public_datasets](http://17lands.com/public_datasets). Build a `dict[int, str]` mapping `grpId → card_name`. Store as `data/replays/card_id_map.json`. This is required before any replay can be interpreted — the GRE data uses integer `grpId` values for all card references.

  Also build a reverse map `card_name → grpId` for test convenience. Include set code and collector number in the mapping for disambiguation.

  Files: `data/replays/card_id_map.json`, script `scripts/build_card_id_map.py`.

  Testability: Map resolves all `grpId` values found in the sample replay JSON (from the [17lands Replay Data Schema](https://www.notion.so/35b6a7adc8ed80978dccdf724213b6f8) page) to valid FDN/SPG card names. No unmapped IDs in the sample data.

- [ ] **17lands GRE JSON parser**
  Detail: Parse 17lands replay data — clean JSON files containing pre-parsed GRE message streams. Format: `{seat_id, opponent_seat_id, events: [...]}` where each event is a `GameStateMessage` with `GameStateType_Full` or `GameStateType_Diff`. See [17lands Replay Data Schema](https://www.notion.so/35b6a7adc8ed80978dccdf724213b6f8) for the full schema.

  The parser must:

  1. **State reconstruction**: Start from first `GameStateType_Full`, apply diffs sequentially — merge zones by `zoneId`, upsert `gameObjects` by `instanceId`, process `diffDeletedInstanceIds`, manage `persistentAnnotations` and `diffDeletedPersistentAnnotationIds`
  2. **Action extraction**: From state diffs, infer what happened — land plays (hand → battlefield via `ObjectIdChanged`), spell casts (hand → stack → resolve), draws (library → hand), ability activations (`GameObjectType_Ability` on stack with `parentId`), combat (`turnInfo` step transitions), creature deaths (→ graveyard)
  3. **Object tracking**: Track cards across zone transitions via `AnnotationType_ObjectIdChanged` (`orig_id` → `new_id`). When a card moves zones, its `instanceId` changes but `grpId` stays the same.
  4. **Card name resolution**: Map `grpId` → card name using the card ID mapping
  5. **Output**: Produce a `ReplayGame` object: game setup (players, seats, format, deck info from initial library), ordered list of `GameSnapshot` objects (one per `gameStateId`), game result
  Files: New module `silverquillm/replay/` with `parser.py`, `types.py` (ReplayGame, GameSnapshot, ReplayAction types), `state.py` (GRE state reconstruction logic).

  Testability: Parse the sample replay data from the schema page. Assert correct game setup (Bo3 limited, seat 1 = user, seat 2 = opponent), correct opening hands (7 cards each), correct land plays on turns 1–5 (fetchland sequence for opponent), correct life totals (20/20 through turn 5). Test that `ObjectIdChanged` annotations correctly track the fetchland: land enters battlefield → ability on stack → land sacrifices to graveyard → Forest enters battlefield tapped.

---

### Validation Runner

- [ ] **Replay executor (state-diff observer mode)**
  Detail: Build a `ReplayExecutor` that steps through `GameSnapshot` objects from the parser and validates engine behavior using state-diff comparison:

  1. Initialize engine game state from the first `GameStateType_Full` snapshot (players, life totals, opening hands via `grpId` → card mapping)
  2. For each consecutive snapshot pair, diff zones/objects to extract what changed (the "action")
  3. **Seat 1 (17lands user):** Full validation — infer the action from the diff (land play, spell cast, combat, etc.), execute it through the engine API (`play_land`, `cast_spell`, `declare_attackers`, etc.), and compare the engine’s resulting state against the next GRE snapshot
  4. **Seat 2 (opponent):** Oracle injection — observe what they played from public game objects (battlefield/stack), inject those state changes directly into the engine without validating legality from their hidden hand
  5. Compare engine state vs GRE snapshot at each step: life totals, zone contents (by `grpId`), battlefield permanents (tapped state, P/T), graveyard contents
  Handle: `grpId` → CardRegistry lookup, `AnnotationType_ObjectIdChanged` for tracking cards across zone transitions, phase/step transitions from `turnInfo` diffs.

  Files: `silverquillm/replay/executor.py`.

  Testability: Execute a simple replay (few turns, lands + vanilla creatures) against the engine. Assert each step succeeds and engine state matches GRE snapshots.

- [ ] **Divergence detection and reporting**
  Detail: When the engine can’t execute a replay action or produces different state, record a `Divergence` with: `gameStateId`, expected state (from GRE snapshot), actual state (from engine), action attempted, and severity:

  - `MISSING_CARD`: Card `grpId` in replay not implemented in engine
  - `ILLEGAL_ACTION`: Engine rejects an action that the GRE shows happened
  - `STATE_MISMATCH`: Engine processes the action but resulting state differs (wrong life total, wrong zone contents, wrong P/T)
  - `ENGINE_ERROR`: Engine throws an unhandled exception
  After execution, produce a `ValidationReport`: total snapshots processed, successful comparisons, divergences by type, per-card divergence rates (which `grpId`s are involved in the most divergences), first divergence point (for debugging).

  Files: `silverquillm/replay/validation.py`.

  Testability: Introduce a deliberate engine bug (e.g., wrong damage amount), run replay, assert divergence is detected and categorized as STATE_MISMATCH. Test MISSING_CARD detection by removing a card implementation.

- [ ] **CLI: ****`benchmark validate`**** command**
  Detail: Add `benchmark validate <replay_path_or_dir>` command. Options: `--cards` (filter to replays containing specific cards by name), `--verbose` (show each action and state comparison), `--report` (output JSON report file), `--stop-on-divergence` (halt at first mismatch for debugging). Summary output: games attempted, games completed without divergence, divergence rate, top divergence causes, per-card divergence rates.

  Files: Extend `silverquillm/cli.py`, new `silverquillm/replay/cli.py`.

  Testability: Run `benchmark validate data/replays/` end-to-end, verify report is generated with expected structure (JSON with games_attempted, divergences, per_card_rates fields).
