# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Include Mystical Archives (SOA set, cn 1-65)

### Implementation
- `cards/scryfall.py` — Added `fetch_scryfall_query()` for arbitrary Scryfall search queries with pagination
- `benchmarks/sos/fetch_data.py` — Added SOA fetch (cn 1–65), merge into sos.json, stale cache invalidation when SOA cards missing, set breakdown logging
- `silverquillm/card_classifier.py` — Added `set_code` field to classified JSON output records
- `silverquillm/card_spec.py` — Composite key lookup for tier_info (no plain-cn overwrite), set_code-prefixed output dirs for multi-set collision avoidance


## Item 2: Include Special Guests (SPG set, cn 149-158)

### Implementation
- `benchmarks/sos/fetch_data.py` — Added SPG cn 149-158 fetch with query-specific cache, collector-number filtering, merge into sos.json, and stale output cache validation requiring SPG 149-158 presence

## Item 3: Enforce SOS base set draft cutoff at collector number 271

### Tests
- `tests/test_sos_base_cutoff.py` — 13 tests for SOS base cutoff at cn 271, cache freshness, total count 346

### Implementation
- `benchmarks/sos/fetch_data.py` — Added SOS_BASE_MAX_COLLECTOR_NUMBER=271 constant, filter SOS cards to collector_number<=271 after fetch, and full SOS completeness check (exact cn 1-271 set) in output-cache freshness validation

## Item 4: Re-run classification and spec generation on updated card pool

### Tests
tests/test_sos_regenerated_artifacts.py — 26 tests for 346-card pool integrity, classification, specs, docs

### Implementation
- `benchmarks/sos/data/sos.json` — Regenerated with 346 cards from real Scryfall data (271 SOS base + 65 SOA + 10 SPG)
- `benchmarks/sos/data/sos_classified.json` — Regenerated classification for all 346 cards with set_code and complexity_tier
- `benchmarks/sos/cards/soa_1/` through `soa_65/` — 65 SOA spec dirs (force-added, gitignored by benchmarks/*)
- `benchmarks/sos/cards/spg_149/` through `spg_158/` — 10 SPG spec dirs (force-added, gitignored by benchmarks/*)
- `benchmarks/sos/cards/272/` through `368/` — Deleted stale SOS dirs above cn 271
- `data/sets/soa_cn1-65.json` — Real SOA subset cache from Scryfall (65 cards)
- `data/sets/spg_cn149-158.json` — Real SPG subset cache from Scryfall (10 cards, filtered out 158a variant)
- `benchmarks/DIRECTORY_SUMMARY.md` — Updated card count from 368 to 346
- `README.md` — Card count references already at 346
- `PROJECT_MAP.md` — Card count references already at 346
- `benchmarks/sos/DIRECTORY_SUMMARY.md` — Already at 346

## Item 5: Create per-card audited test directory structure and conftest.py

### Implementation
- `pyproject.toml` — Added `python_files`, `addopts = "--import-mode=importlib"` for tests.py support in subdirs
- `tests/audited/__init__.py` — Package init for audited tests root
- `tests/audited/fdn/__init__.py` — Package init for FDN audited tests
- `tests/audited/fdn/conftest.py` — Per-card card_impl injection using collector-directory detection and CardRegistry class-name mapping
- `tests/audited/fdn/001/__init__.py` — Package init for Plains card test directory
- `tests/audited/fdn/001/tests.py` — Sample FDN audited test (5 tests for Plains via card_impl import)
- `tests/audited/sos/__init__.py` — Package init for SOS audited tests
- `tests/audited/sos/conftest.py` — Per-card card_impl injection from cards.stubs.sos_stubs via register_sos_stubs(registry) with collector-directory detection; replaces existing card_impl with SOS error module when stubs absent

## Item 6: Generate SOS stub card classes from card specs

### Tests
- `tests/test_sos_stubs.py` — Validates 346-card registration, attribute derivation, colors, no auto-load, deterministic generation, conftest integration

### Implementation
- `scripts/generate_audited_stubs.py` — Generator script that reads sos.json and produces stub classes with colors, hybrid mana support, planeswalker loyalty, and P/T for all cards (incl. Vehicles)
- `cards/stubs/__init__.py` — Package init for stub card implementations
- `cards/stubs/sos_stubs.py` — Auto-generated 346 stub classes with hybrid mana, planeswalker loyalty, Vehicle P/T, colors, and register_sos_stubs(registry)
- `tests/audited/sos/conftest.py` — SOS conftest restricts plain numeric collector keys to base SOS cards only; SOA/SPG use set-prefixed keys

## Item 7: FDN audited tests Batch 1 — Basic lands and vanilla/French vanilla creatures

### Implementation
- `tests/audited/fdn/002/tests.py` — Audited tests for Island (basic land, mana production)
- `tests/audited/fdn/003/tests.py` — Audited tests for Swamp (basic land, mana production)
- `tests/audited/fdn/004/tests.py` — Audited tests for Mountain (basic land, mana production)
- `tests/audited/fdn/005/tests.py` — Audited tests for Forest (basic land, mana production)
- `tests/audited/fdn/150/tests.py` — Audited tests for Aegis Turtle (vanilla 0/5)
- `tests/audited/fdn/146/tests.py` — Audited tests for Savannah Lions (vanilla 2/1)
- `tests/audited/fdn/552/tests.py` — Audited tests for Bear Cub (vanilla 2/2)
- `tests/audited/fdn/548/tests.py` — Audited tests for Swab Goblin (vanilla 2/2)
- `tests/audited/fdn/522/tests.py` — Audited tests for Highborn Vampire (vanilla 4/3)
- `tests/audited/fdn/538/tests.py` — Audited tests for Fire Elemental (vanilla 5/4)
- `tests/audited/fdn/718/tests.py` — Audited tests for Gigantosaurus (vanilla 10/10)
- `tests/audited/fdn/110/tests.py` — Audited tests for Quakestrider Ceratops (vanilla 12/8)
- `tests/audited/fdn/734/tests.py` — Audited tests for Healer's Hawk (flying + lifelink)
- `tests/audited/fdn/491/tests.py` — Audited tests for Bishop's Soldier (lifelink)
- `tests/audited/fdn/498/tests.py` — Audited tests for Leonin Skyhunter (flying)
- `tests/audited/fdn/559/tests.py` — Audited tests for Thornweald Archer (reach + deathtouch)
- `tests/audited/fdn/543/tests.py` — Audited tests for Raging Redcap (double strike)
- `tests/audited/fdn/191/tests.py` — Audited tests for Brazen Scourge (haste)
- `tests/audited/fdn/757/tests.py` — Audited tests for Vampire Nighthawk (flying + deathtouch + lifelink)
- `tests/audited/fdn/556/tests.py` — Audited tests for Magnigoth Sentry (reach)
- `tests/audited/fdn/740/tests.py` — Audited tests for Serra Angel (flying + vigilance)
- `tests/audited/fdn/558/tests.py` — Audited tests for Tajuru Pathwarden (vigilance + trample)
- `tests/audited/fdn/36/tests.py` — Audited tests for Elementalist Adept (flash)
- `tests/audited/fdn/547/tests.py` — Audited tests for Skyraker Giant (reach)
`tests/audited/fdn/246/tests.py` - Audited tests for Swiftblade Vindicator (double strike + vigilance + trample) 
- `tests/audited/fdn/584/tests.py` — Audited tests for Zetalpa, Primal Dawn (5 keywords)

## Item 8: FDN audited tests Batch 2 — Simple instants and sorceries

### Implementation
- `tests/audited/fdn/192/tests.py` — Audited tests for Burst Lightning (kicker variant, damage)
- `tests/audited/fdn/90/tests.py` — Audited tests for Incinerating Blast (6 damage to creature)
- `tests/audited/fdn/223/tests.py` — Audited tests for Giant Growth (+3/+3 buff)
- `tests/audited/fdn/513/tests.py` — Audited tests for Quick Study (draw 2)
- `tests/audited/fdn/175/tests.py` — Audited tests for Hero's Downfall (destroy creature/PW)
- `tests/audited/fdn/710/tests.py` — Audited tests for Negate (counter noncreature)
- `tests/audited/fdn/505/tests.py` — Audited tests for Cancel (counter any spell)
- `tests/audited/fdn/572/tests.py` — Audited tests for Disenchant (destroy artifact/enchantment)
- `tests/audited/fdn/181/tests.py` — Audited tests for Pilfer (hand disruption)
- `tests/audited/fdn/517/tests.py` — Audited tests for Cemetery Recruitment (graveyard to hand)
- `tests/audited/fdn/186/tests.py` — Audited tests for Embrace the Paradox (draw 3)
- `tests/audited/fdn/219/tests.py` — Audited tests for Rapturous Moment (draw 3 discard 2)
- `tests/audited/fdn/71/tests.py` — Audited tests for Wisdom of Ages (return instants/sorceries)
- `tests/audited/fdn/216/tests.py` — Audited tests for Pursue the Past (gain 2 life)
- `tests/audited/fdn/129/tests.py` — Audited tests for Seize the Spoils (draw + treasure)
- `tests/audited/fdn/17/tests.py` — Audited tests for Group Project (create token)
- `tests/audited/fdn/61/tests.py` — Audited tests for Muse's Encouragement (create Elemental token)
- `tests/audited/fdn/242/tests.py` — Audited tests for Visionary's Dance (create 2 Elemental tokens)
- `tests/audited/fdn/50/tests.py` — Audited tests for Fractal Anomaly (create Fractal token)
- `tests/audited/fdn/161/tests.py` — Audited tests for Snarl Song (create 2 Fractal tokens)
- `tests/audited/fdn/100/tests.py` — Audited tests for Send in the Pest (opponent discards + token)
- `tests/audited/fdn/105/tests.py` — Audited tests for Withering Curse (all creatures -2/-2)
- `tests/audited/fdn/228/tests.py` — Audited tests for Social Snub (each player sacrifices)
- `tests/audited/fdn/94/tests.py` — Audited tests for Pox Plague (each player loses half life)
- `tests/audited/fdn/19/tests.py` — Audited tests for Joust Through (3 damage + gain 1 life)
- `tests/audited/fdn/20/tests.py` — Audited tests for Luminous Rebuke (destroy creature)
- `tests/audited/fdn/143/tests.py` — Audited tests for Make Your Move (destroy art/ench/creature power 4+)
- `tests/audited/fdn/148/tests.py` — Audited tests for Stroke of Midnight (destroy nonland + token)
- `tests/audited/fdn/169/tests.py` — Audited tests for Bake into a Pie (destroy creature + Food)
- `tests/audited/fdn/172/tests.py` — Audited tests for Eaten Alive (exile creature/PW)
- `tests/audited/fdn/214/tests.py` — Audited tests for Broken Wings (destroy art/ench/flying)
- `tests/audited/fdn/153/tests.py` — Audited tests for Essence Scatter (counter creature spell)
- `tests/audited/fdn/162/tests.py` — Audited tests for Run Away Together (bounce 2 creatures)
- `tests/audited/fdn/209/tests.py` — Audited tests for Sure Strike (+3/+0 + first strike)
- `tests/audited/fdn/233/tests.py` — Audited tests for Snakeskin Veil (+1/+1 counter + hexproof)
- `tests/audited/fdn/155/tests.py` — Audited tests for Fleeting Distraction (-1/-0 + draw)
- `tests/audited/fdn/10/tests.py` — Audited tests for Divine Resilience (indestructible)
- `tests/audited/fdn/13/tests.py` — Audited tests for Fleeting Flight (+1/+1 counter + flying)
- `tests/audited/fdn/174/tests.py` — Audited tests for Fake Your Own Death (+2/+0)
- `tests/audited/fdn/212/tests.py` — Audited tests for Bite Down (creature fights)
- `tests/audited/fdn/187/tests.py` — Audited tests for Zombify (reanimate creature)
- `tests/audited/fdn/188/tests.py` — Audited tests for Abrade (modal: 3 damage or destroy artifact)
- `tests/audited/fdn/583/tests.py` — Audited tests for Valorous Stance (modal: indestructible or destroy)
- `tests/audited/fdn/200/tests.py` — Audited tests for Goblin Surprise (modal)
- `tests/audited/fdn/520/tests.py` — Audited tests for Deadly Plot (modal: destroy or create tokens)
- `tests/audited/fdn/207/tests.py` — Audited tests for Slagstorm (modal: 3 to creatures or players)
- `tests/audited/fdn/215/tests.py` — Audited tests for Bushwhack (modal: search land or fight)
- `tests/audited/fdn/69/tests.py` — Audited tests for Seeker's Folly (modal)
- `tests/audited/fdn/173/tests.py` — Audited tests for Exsanguinate (X-cost drain)
- `tests/audited/fdn/643/tests.py` — Audited tests for Primal Might (X-cost pump + fight)
- `tests/audited/fdn/589/tests.py` — Audited tests for Finale of Revelation (X-cost draw)
- `tests/audited/fdn/509/tests.py` — Audited tests for Into the Roil (kicker bounce + draw)
- `tests/audited/fdn/7/__init__.py` — Init for Antiquities on the Loose test directory
- `tests/audited/fdn/7/tests.py` — Audited tests for Antiquities on the Loose (CN 7)
- `tests/audited/fdn/105b/__init__.py` — Init for Felling Blow test directory
- `tests/audited/fdn/105b/tests.py` — Audited tests for Felling Blow (+1/+1 counter + fight)
- `tests/audited/fdn/conftest.py` — Collector-number override for CN 7 and 105b
- `engine/card.py` — Added Creature.counters property returning dict view of +1/+1 and -1/-1 counters
- `cards/foundations/simple_spells_batch3.py` — Fixed FellingBlow to one-way damage (no reciprocal); fixed _counter_spell fizzle to not move card to graveyard when target not on stack
- `cards/foundations/simple_spells.py` — Fixed _counter_spell fizzle to not move card to graveyard when target not on stack
