## Phase 6: SOS Draft Set Completion & Audited Test Suites

Scope: Fix the SOS card pool to include all draft-relevant cards (Mystical Archives + Special Guests), establish per-card audited test infrastructure, write comprehensive audited test suites for all 301 FDN Draft Set cards, and prepare audited tests for the 346-card SOS Draft Set.

See `CONTEXT.md` for domain vocabulary (Draft Set, Card Pool, Audited Eval). See `TEST-SUITE.md` Decisions for audited test conventions.

---

### SOS Draft Set Card Pool

- [x] **Include Mystical Archives (SOA set, cn 1–65)**
  Detail: The SOS Draft Set includes 65 Mystical Archive cards from the SOA set (collector numbers 1–65). These are currently missing from `fetch_data.py`. Update the Scryfall fetch to also pull `e:soa cn>=1 cn<=65`. Reference: [Scryfall SOA search](https://scryfall.com/search?order=set&q=e%3Asoa%20cn%E2%89%A51%20cn%E2%89%A465&unique=prints).

  Changes needed:

  - `benchmarks/sos/fetch_data.py`: Add a second Scryfall API query for `set=soa` with collector number range 1–65. Merge results into the same `sos.json` output, preserving the `set_code` field so SOA cards are distinguishable from SOS base set cards.
  - Ensure `card_classifier.py` and `card_spec.py` handle multi-set card pools (cards with `set_code="soa"` alongside `set_code="sos"`).
  Testability: After fetch, `sos.json` contains cards with `set_code="soa"` and collector numbers 1–65. Count should be exactly 65 SOA cards.

- [x] **Include Special Guests (SPG set, cn 149–158)**
  Detail: The SOS Draft Set includes 10 Special Guest cards from the SPG set (collector numbers 149–158). These are currently missing from `fetch_data.py`. Update the Scryfall fetch to also pull `e:spg cn>=149 cn<=158`. Reference: [Scryfall SPG search](https://scryfall.com/search?order=set&q=e%3Aspg%20cn%E2%89%A5149%20cn%E2%89%A4158&unique=prints).

  Changes needed:

  - `benchmarks/sos/fetch_data.py`: Add a third Scryfall API query for `set=spg` with collector number range 149–158. Merge results into `sos.json` with `set_code="spg"`.
  - These are distinct from the FDN Special Guests (SPG 074–083) already implemented in Phase 5.
  Testability: After fetch, `sos.json` contains 10 cards with `set_code="spg"` and collector numbers 149–158.

- [x] **Enforce SOS base set draft cutoff at collector number 271**
  Detail: SOS base set cards with collector number > 271 are alternate-art reprints / duplicates and should be excluded from the Draft Set. Update `fetch_data.py` to filter out SOS cards (`set_code="sos"`) with `int(collector_number) > 271`.

  Changes needed:

  - `benchmarks/sos/fetch_data.py`: After fetching SOS base set cards, filter to only `int(collector_number) <= 271`. This filter applies only to `set_code="sos"` cards — SOA and SPG cards have their own collector number ranges and are not affected.
  - The final card pool should be: SOS base (≤271) + SOA (1–65) + SPG (149–158) = **346 cards total**.
  Testability: No card in `sos.json` has `set_code="sos"` and `int(collector_number) > 271`. Total card count = 346.

- [x] **Re-run classification and spec generation on updated card pool**
  Detail: After updating `sos.json`, re-run the card classifier and card spec generator to produce updated `sos_classified.json` and per-card spec directories.

  Changes needed:

  - Run `python -m silverquillm.card_classifier` to regenerate `benchmarks/sos/data/sos_classified.json`
  - Run `python -m silverquillm.card_spec` to regenerate `benchmarks/sos/cards/` per-card specs
  - Verify `NEW_MECHANICS` list in `fetch_data.py` still covers all SOS/SOA/SPG mechanics (Prepared, Converge, Miracle, Opus — check if SOA Mystical Archives introduce any additional keywords)
  - Update `PROJECT_MAP.md`, `DIRECTORY_SUMMARY.md`, and `README.md` card count references from "368" to "346"
  Testability: `sos_classified.json` has entries for all 346 cards. Every card has a corresponding spec directory under `benchmarks/sos/cards/`.

---

### Audited Test Infrastructure

- [x] **Create per-card audited test directory structure and **[**conftest.py**](http://conftest.py/)
  Detail: Set up the directory structure for audited tests following the per-card convention settled in [TEST-SUITE.md](http://test-suite.md/). Each card gets its own directory with a `tests.py` file that imports from `card_impl`. A `conftest.py` at each set level handles the `card_impl` module injection.

  Directory structure:

  ```javascript
tests/audited/
├── fdn/
│   ├── conftest.py          # card_impl injection for FDN
│   ├── {collector_number}/
│   │   └── tests.py
│   └── ...
└── sos/
    ├── conftest.py          # card_impl injection for SOS
    ├── {collector_number}/
    │   └── tests.py
    └── ...
  ```

  The `conftest.py` must:

  1. **Detect the card under test** from the test file's parent directory name (collector number).
  2. **For FDN**: Look up the card's engine implementation class from `CardRegistry` (the card is already registered by `cards/foundations/*.py`). Create a synthetic `card_impl` module that exposes the class.
  3. **For SOS**: Look up the card's stub class from the stub registration module (created in the next item). Create a synthetic `card_impl` module that exposes the class.
  4. **Inject ****`card_impl`** into `sys.modules` before the test runs, so `from card_impl import ClassName` works.
  This design means the same test files work both during development (conftest provides the engine's own class or stub) and during evaluation (the evaluator overrides `card_impl` with the agent's implementation via `shutil.copy`).

  Key reference: The evaluator's existing `card_impl` swap mechanism in `silverquillm/evaluator.py` uses `shutil.copy2(impl_path, tmp / "card_impl.py")`. The conftest approach must be compatible — when the evaluator provides `card_impl.py` explicitly, the conftest should detect it and NOT override.

  Testability: Create one sample FDN test file (e.g., `tests/audited/fdn/001/tests.py` for Plains) and verify that `pytest tests/audited/fdn/001/` runs and the test can `from card_impl import Plains`.

- [x] **Generate SOS stub card classes from card specs**
  Detail: Auto-generate minimal stub implementations for all 346 SOS Draft Set cards. Stubs let audited tests execute and produce meaningful assertion failures ("wrong P/T", "no trigger fired") rather than `KeyError` crashes from `CardRegistry.create_instance()`.

  Changes needed:

  - Create a script `scripts/generate_audited_stubs.py` that:
    1. Reads `benchmarks/sos/data/sos.json` for card data
    2. For each card, generates a minimal stub class that inherits from `CardImpl` (or `Creature`/`Land`/`Instant` etc. based on `type_line`)
    3. Sets basic attributes: `name`, `mana_cost`, `power`, `toughness`, `card_types`, `subtypes`, `colors` — all derived from Scryfall data
    4. Registers each stub in `CardRegistry` so `cast_spell(game, player, "Card Name")` works
    5. Does NOT implement any abilities — stubs are intentionally empty beyond basic attributes
  - Output: `cards/stubs/sos_stubs.py` with all 346 stub classes + a `register_sos_stubs(registry)` function
  - The stub module must be importable but NOT auto-loaded by the default registry (it should only be loaded explicitly by the SOS [conftest.py](http://conftest.py/) or by a test runner flag)
  Class naming: Use the same `card_name_to_class_name()` from `silverquillm/template_gen.py` for consistent naming.

  Testability: After generation, all 346 cards can be instantiated via `CardRegistry.create_instance(name)` when stubs are loaded. Verify count matches `sos.json`.

---

### FDN Audited Test Suite (301 cards)

All FDN audited tests follow the per-card structure: `tests/audited/fdn/{collector_number}/tests.py`. Each test file imports from `card_impl` (injected by conftest). Tests use `test_utils` helpers exclusively (`create_game`, `set_board_state`, `cast_spell`, etc.). Tag each test with a category marker: `@pytest.mark.basic`, `@pytest.mark.ability`, `@pytest.mark.edge`, `@pytest.mark.interaction`, `@pytest.mark.rules`.

The FDN Draft Set is 301 cards: FDN 001–291 + SPG 074–083. This includes basic lands. Every card gets tests.

For each card, the Implementer should:

1. Look up the card's implementation in `cards/foundations/*.py` to understand its behavior
2. Look up its Scryfall data (name, oracle text, type, P/T, keywords) from the card registry
3. Write tests that verify: basic stats, core abilities, edge cases, and rules interactions
4. Follow test count guidelines: 2–3 for vanilla, 5–8 for simple abilities, 10–20 for complex cards
Key engine conventions to be aware of (from `KEY_DECISIONS.md`):

- Self-ETB effects use `on_resolve()`, not triggers (register_triggers fires AFTER ETB event)
- P/T bonuses in Layer 7c (SubLayer.MODIFY_PT), keywords in Layer 6
- Protection is a continuous effect cleared in `_reset_characteristics()`, reapplied each layer pass
- Identity-based zone lookups: `contains()` / `remove()` use `is` (not `==`)
- `cards_drawn_this_turn` counter tracks per-turn card draws
- ENGINE LIMITATION comments document known gaps — don't write tests that exercise documented limitations
- [x] **FDN audited tests: Batch 1 — Basic lands and vanilla/French vanilla creatures (~30 cards)**
  Detail: Write per-card test files for all 5 basic lands (Plains, Island, Swamp, Mountain, Forest) and ~25 vanilla/French vanilla creatures from FDN.

  Basic lands: Test tapping for correct mana color, untapping on untap step, and that they enter untapped.

  Vanilla creatures: Test correct P/T, casting, combat (attacking, blocking, damage assignment).

  French vanilla: Test each keyword — flying (evasion + blocking flyers), trample (excess damage), first strike (damage timing), vigilance (no tap on attack), deathtouch (lethal with 1 damage), lifelink (life gain on damage), reach (can block flyers), menace (must be blocked by 2+), haste (can attack/tap immediately).

  Card list for reference: Use `cards/foundations/basic_lands.py`, `cards/foundations/simple_creatures.py`, `cards/foundations/vanilla_creatures_batch2.py` to identify all cards in this batch.

  Files: One `tests.py` per card under `tests/audited/fdn/{collector_number}/tests.py`.

  Testability: All tests pass against the current engine. Every card in the batch has a corresponding test file.

- [x] **FDN audited tests: Batch 2 — Simple instants and sorceries (~60 cards)**
  Detail: Write per-card test files for all simple instants and sorceries from FDN (batches 1–3 from Phase 4 implementation files).

  Test coverage per card:

  - Targeting validation (valid target, invalid target, no valid targets → spell fizzles)
  - Resolution effects (damage, life gain/loss, bounce, counter, destroy, exile)
  - Edge cases: target dies before resolution (fizzle), targeting hexproof/shroud creatures
  - Kicker costs (if applicable): kicked vs unkicked resolution
  - Modal spells: each mode tested independently
  Card list: Use `cards/foundations/simple_spells.py`, `simple_spells_batch2.py`, `simple_spells_batch3.py`, `complex_spells.py` to identify cards.

  Files: One `tests.py` per card under `tests/audited/fdn/{collector_number}/tests.py`.

  Testability: All tests pass against the current engine.

- [ ] **FDN audited tests: Batch 3 — Creatures with triggers and activated abilities (~65 cards)**
  Detail: Write per-card test files for all ETB trigger creatures (~29), death trigger creatures (~17), and activated ability creatures (~19) from FDN.

  ETB triggers: Test trigger firing on entry, trigger conditions ("if"/"when"/"may"), trigger with valid/no valid targets, interaction with bounce (re-entry → retrigger), blink effects.

  Death triggers: Test trigger on destruction, sacrifice, lethal damage. Test that trigger fires from battlefield to graveyard (not from other zones). Test "dies" vs "leaves the battlefield" distinction.

  Activated abilities: Test cost payment (tap, mana, sacrifice), timing restrictions (sorcery-speed vs instant-speed), effect resolution, activation with insufficient resources.

  Remember: Self-ETB effects use `on_resolve()` per KEY_DECISIONS — test the observable effect, not the trigger mechanism.

  Card list: Use `cards/foundations/etb_creatures.py`, `death_trigger_creatures.py`, `activated_creatures.py`.

  Files: One `tests.py` per card under `tests/audited/fdn/{collector_number}/tests.py`.

  Testability: All tests pass against the current engine.

- [ ] **FDN audited tests: Batch 4 — Enchantments, equipment, artifacts, and planeswalkers (~70 cards)**
  Detail: Write per-card test files for all auras (~10), global enchantments (~10), equipment (~7), artifacts (~27+), and planeswalkers (~3) from FDN.

  Auras: Attachment legality, SBA detach when target is invalid, enchant effect application, stacking multiple auras.

  Global enchantments: Static ability application, layer ordering, interaction with entering/leaving battlefield.

  Equipment: Equip cost, re-equip to different creature, equipped creature dies (equipment stays on battlefield), continuous effect application (P/T in Layer 7c, keywords in Layer 6 per KEY_DECISIONS).

  Artifacts: Activated abilities, tap costs, sacrifice costs, enters-the-battlefield effects.

  Planeswalkers: Starting loyalty, +/− loyalty abilities, targeting planeswalkers with damage, uniqueness rule (legend rule).

  Card list: Use `cards/foundations/simple_permanents.py`, `enchantments.py`, `equipment.py`, `artifacts.py`, `artifacts_batch2.py`, `planeswalkers.py`.

  Files: One `tests.py` per card under `tests/audited/fdn/{collector_number}/tests.py`.

  Testability: All tests pass against the current engine.

- [ ] **FDN audited tests: Batch 5 — Non-basic lands, SPG cards, and remaining cards (~76 cards)**
  Detail: Write per-card test files for non-basic lands (~13), SPG Special Guests (074–083, 10 cards), and any remaining FDN cards not covered in Batches 1–4.

  Non-basic lands: Test enters-tapped (if applicable), activated abilities, mana production (color/amount), special abilities.

  SPG cards (074–083): These are the 10 Special Guests from Phase 5 — Condemn, Grim Tutor, Sphinx's Tutelage, Embercleave, Goblin Bushwhacker, Paradise Druid, Bloom Tender, Akroma's Memorial, Temporal Manipulation, Fiend Artisan. These are complex cards with hybrid mana, cost reduction, protection, and other Phase 5 engine extensions.

  For SPG cards, reference KEY_DECISIONS: hybrid mana payment ordering, cost reduction controller setup, Embercleave self-ETB uses `on_resolve()`, equipment P/T in Layer 7c.

  **After all batches are complete**: Verify that every FDN card registered in `CardRegistry` (filter to `set_code` in `{"fdn", "spg"}` with FDN/SPG collector number ranges) has a corresponding `tests/audited/fdn/{collector_number}/tests.py` file. The total should be 301 test files.

  Card list: Use `cards/foundations/lands.py`, `special_guests.py`, and cross-reference the full registry.

  Files: One `tests.py` per card under `tests/audited/fdn/{collector_number}/tests.py`.

  Testability: All tests pass against the current engine. Total FDN audited test file count = 301.

---

### SOS Audited Test Suite (346 cards)

All SOS audited tests follow the same per-card structure: `tests/audited/sos/{collector_number}/tests.py`. Each test file imports from `card_impl` (injected by conftest, which loads the stub class during development). Tests use `test_utils` helpers exclusively. Same category markers as FDN.

For each card, the Implementer should:

1. Read the card spec from `benchmarks/sos/cards/{collector_number}/spec.json` for oracle text, type, P/T, keywords, and complexity tier
2. Write tests that verify the behavior described in the oracle text — treat the oracle text as the spec
3. For SOS-specific mechanics (Prepared, Converge, Miracle, Opus), test both the basic mechanic behavior and edge cases
4. Tests will execute against stub classes during development (stubs only have basic attributes, so ability tests will fail — this is expected and correct)
These tests are designed to be **plug-and-play** with any agent's implementation via the evaluator's `card_impl` swap mechanism. They are the "audited eval" column in the cross-evaluation matrix.

- [ ] **SOS audited tests: Batch 1 — Trivial and simple complexity cards**
  Detail: Write per-card test files for all SOS Draft Set cards classified as `trivial` or `simple` in `sos_classified.json`. These are the cards agents should get right — vanilla/French vanilla creatures, simple targeted spells, basic enchantments.

  Test count per card: 2–5 for trivial, 5–8 for simple.

  Focus on: basic stats verification, core ability functionality, straightforward interactions.

  The card spec at `benchmarks/sos/cards/{collector_number}/spec.json` is the source of truth for expected behavior.

  Files: One `tests.py` per card under `tests/audited/sos/{collector_number}/tests.py`.

  Testability: Tests are syntactically valid and importable. Tests run against stub classes (most ability tests will fail as expected — stubs have correct attributes but no ability logic). Verify every trivial/simple card has a test file.

- [ ] **SOS audited tests: Batch 2 — Moderate complexity cards**
  Detail: Write per-card test files for all SOS Draft Set cards classified as `moderate` in `sos_classified.json`. These cards have multiple abilities, conditional triggers, or keyword interactions.

  Test count per card: 8–15.

  Test coverage: Each ability independently, ability interactions, trigger conditions, timing edge cases.

  For SOS-specific mechanics:

  - **Prepared**: Test the "prepared" alternate cost path vs normal cast. Prepared lets you pay a cost during your turn to set up an effect that triggers later.
  - **Converge**: Test with 1, 2, 3, 4, 5 colors of mana spent. Reference existing Converge support: `mana.py` tracks `last_payment_colors`, `casting.py` stores `colors_spent`.
  - **Miracle**: Test miracle cost when drawn as first card of turn vs normal cast from hand.
  - **Opus**: Test each opus mode selection and resolution.
  Files: One `tests.py` per card under `tests/audited/sos/{collector_number}/tests.py`.

  Testability: Same as Batch 1 — syntactically valid, importable, expected failures against stubs.

- [ ] **SOS audited tests: Batch 3 — Complex and extreme complexity cards**
  Detail: Write per-card test files for all SOS Draft Set cards classified as `complex` or `extreme` in `sos_classified.json`. These are the true benchmark differentiators — multi-step resolution, state-dependent behavior, unusual interactions.

  Test count per card: 10–25.

  Test coverage:

  - Complex resolution sequences tested step-by-step
  - State-dependent behavior (P/T that changes with game state, conditional abilities)
  - "Trap" tests that catch common misinterpretations of oracle text (ambiguous wording, ordering of effects)
  - Multi-card interaction scenarios where this card interacts with common game patterns
  Files: One `tests.py` per card under `tests/audited/sos/{collector_number}/tests.py`.

  **After all SOS batches are complete**: Verify that every card in `sos_classified.json` has a corresponding `tests/audited/sos/{collector_number}/tests.py` file. Total should be 346 test files.

  Testability: Same as Batch 1. Total SOS audited test file count = 346.

---

### Pipeline & Documentation

- [ ] **Wire per-card audited tests into the evaluation pipeline**
  Detail: Update the evaluator and CLI to discover and run per-card audited test files instead of a single monolithic test file.

  Current state: `benchmark eval --audited-tests` accepts a single file path. The evaluator runs that one file against all cards.

  Target state: `benchmark eval --audited-dir tests/audited/sos/` discovers per-card test files automatically. For each card in the results directory, the evaluator:

  1. Resolves the card's collector number from the card_id
  2. Finds `{audited_dir}/{collector_number}/tests.py`
  3. Copies the agent's implementation as `card_impl.py` into a temp directory (existing mechanism)
  4. Copies the per-card `tests.py` into the same temp directory
  5. Runs pytest on the temp directory
  6. Records results per card in `result.json`
  Changes needed:

  - `silverquillm/evaluator.py`: Add `run_audited_eval_per_card(impl_path, card_id, audited_dir)` that handles the per-card discovery and test execution. Keep the existing `run_audited_eval()` for backwards compatibility.
  - `silverquillm/cli.py`: Change `--audited-tests` to `--audited-dir` (or add as alternative). Update the eval loop to call `run_audited_eval_per_card()` for each card.
  - `silverquillm/results.py`: No changes needed — `audited_eval` field in `result.json` already supports per-card results.
  - `silverquillm/scorer.py`: No changes needed — already reads audited eval from `result.json`.
  Testability: `benchmark eval --audited-dir tests/audited/fdn/` runs FDN audited tests against the engine's own implementations and reports 100% pass rate.
