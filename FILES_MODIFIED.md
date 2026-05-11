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

## Item 9: FDN audited tests Batch 3 — Creatures with triggers and activated abilities

### Implementation
- `tests/audited/fdn/conftest.py` — Added collector-number override mappings for 61b→High-Society Hunter, 219b→Elvish Archdruid, 228b→Mild-Mannered Librarian
- `tests/audited/fdn/16/tests.py` — Audited tests for Helpful Hunter (ETB draw)
- `tests/audited/fdn/496/tests.py` — Audited tests for Inspiring Overseer (ETB life+draw)
- `tests/audited/fdn/653/tests.py` — Audited tests for Cloudblazer (ETB 2 life + draw 2)
- `tests/audited/fdn/42/tests.py` — Audited tests for Icewind Elemental (ETB loot)
- `tests/audited/fdn/720/tests.py` — Audited tests for Pelakka Wurm (ETB gain 7 life + dies draw)
- `tests/audited/fdn/532/tests.py` — Audited tests for Vampire Spawn (ETB drain)
- `tests/audited/fdn/21/tests.py` — Audited tests for Prideful Parent (ETB Cat token)
- `tests/audited/fdn/145/tests.py` — Audited tests for Resolute Reinforcements (ETB Soldier token)
- `tests/audited/fdn/14/tests.py` — Audited tests for Guarded Heir (ETB two Knight tokens)
- `tests/audited/fdn/84/tests.py` — Audited tests for Dragon Trainer (ETB Dragon token)
- `tests/audited/fdn/579/tests.py` — Audited tests for Regal Caracal (ETB Cat tokens + lord)
- `tests/audited/fdn/544/tests.py` — Audited tests for Rapacious Dragon (ETB Treasure tokens)
- `tests/audited/fdn/526/tests.py` — Audited tests for Skeleton Archer (ETB 1 damage)
`tests/audited/fdn/634/tests.py` - Audited tests for Viashino Pyromancer (ETB 2 damage) 
- `tests/audited/fdn/231/tests.py` — Audited tests for Reclamation Sage (ETB destroy artifact/enchantment)
- `tests/audited/fdn/256/tests.py` — Audited tests for Meteor Golem (ETB destroy nonland)
- `tests/audited/fdn/98/tests.py` — Audited tests for Ambush Wolf (ETB exile from graveyard)
- `tests/audited/fdn/31/tests.py` — Audited tests for Bigfin Bouncer (ETB bounce)
- `tests/audited/fdn/508/tests.py` — Audited tests for Exclusion Mage (ETB bounce)
- `tests/audited/fdn/75/tests.py` — Audited tests for Vampire Soulcaller (ETB graveyard recursion)
- `tests/audited/fdn/144/tests.py` — Audited tests for Mischievous Pup (ETB self-bounce)
- `tests/audited/fdn/12/tests.py` — Audited tests for Felidar Savior (ETB +1/+1 counters)
- `tests/audited/fdn/170/tests.py` — Audited tests for Burglar Rat (ETB opponent discard)
- `tests/audited/fdn/55/tests.py` — Audited tests for Arbiter of Woe (ETB discard+drain)
- `tests/audited/fdn/504/tests.py` — Audited tests for Burrog Befuddler (ETB debuff)
- `tests/audited/fdn/714/tests.py` — Audited tests for Massacre Wurm (ETB -2/-2)
- `tests/audited/fdn/104/tests.py` — Audited tests for Elvish Regrower (ETB graveyard recursion)
- `tests/audited/fdn/136/tests.py` — Audited tests for Angel of Finality (ETB exile graveyard)
- `tests/audited/fdn/596/tests.py` — Audited tests for Shipwreck Dowser (ETB return instant/sorcery)
- `tests/audited/fdn/64/tests.py` — Audited tests for Infestation Sage (death trigger Insect token)
- `tests/audited/fdn/252/tests.py` — Audited tests for Gleaming Barrier (death trigger Treasure)
- `tests/audited/fdn/523/tests.py` — Audited tests for Maalfeld Twins (death trigger Zombie tokens)
- `tests/audited/fdn/257/tests.py` — Audited tests for Solemn Simulacrum (death trigger draw)
- `tests/audited/fdn/519/tests.py` — Audited tests for Crow of Dark Tidings (death trigger mill)
- `tests/audited/fdn/235/tests.py` — Audited tests for Wary Thespian (death trigger surveil)
- `tests/audited/fdn/76/tests.py` — Audited tests for Vengeful Bloodwitch (death trigger drain)
- `tests/audited/fdn/609/tests.py` — Audited tests for Midnight Reaper (death trigger draw)
- `tests/audited/fdn/61b/tests.py` — Audited tests for High-Society Hunter (death trigger)
- `tests/audited/fdn/658/tests.py` — Audited tests for Garna, Bloodfist of Keld (other creature dies)
- `tests/audited/fdn/518/tests.py` — Audited tests for Crossway Troublemakers (other creature dies)
- `tests/audited/fdn/607/tests.py` — Audited tests for Kalastria Highborn (vampire death trigger)
- `tests/audited/fdn/605/tests.py` — Audited tests for Driver of the Dead (death trigger recursion)
- `tests/audited/fdn/63/tests.py` — Audited tests for Infernal Vessel (death trigger resurrect)
`tests/audited/fdn/66/tests.py` - Audited tests for Nine-Lives Familiar (death trigger revival) 
- `tests/audited/fdn/120/tests.py` — Audited tests for Fiendish Panda (death trigger recursion)
- `tests/audited/fdn/112/tests.py` — Audited tests for Spinner of Souls (other creature dies reveal)
- `tests/audited/fdn/227/tests.py` — Audited tests for Llanowar Elves (mana ability)
- `tests/audited/fdn/219b/tests.py` — Audited tests for Elvish Archdruid (mana + lord)
- `tests/audited/fdn/245/tests.py` — Audited tests for Ruby, Daring Tracker (mana ability)
- `tests/audited/fdn/49/tests.py` — Audited tests for Rune-Sealed Wall (tap surveil)
- `tests/audited/fdn/52/tests.py` — Audited tests for Strix Lookout (tap loot)
- `tests/audited/fdn/189/tests.py` — Audited tests for Axgard Cavalry (tap grant haste)
- `tests/audited/fdn/204/tests.py` — Audited tests for Krenko, Mob Boss (tap create tokens)
- `tests/audited/fdn/139/tests.py` — Audited tests for Cathar Commando (sacrifice destroy)
- `tests/audited/fdn/195/tests.py` — Audited tests for Fanatical Firebrand (sacrifice damage)
- `tests/audited/fdn/201/tests.py` — Audited tests for Heartfire Immolator (sacrifice damage)
- `tests/audited/fdn/250/tests.py` — Audited tests for Burnished Hart (sacrifice land search)
- `tests/audited/fdn/62/tests.py` — Audited tests for Hungry Ghoul (sacrifice +1/+1)
- `tests/audited/fdn/206/tests.py` — Audited tests for Shivan Dragon (pump ability)
- `tests/audited/fdn/95/tests.py` — Audited tests for Sower of Chaos (can't block ability)
`tests/audited/fdn/114/tests.py` - Audited tests for Treetop Snarespinner (pump counter) 
- `tests/audited/fdn/164/tests.py` — Audited tests for Spectral Sailor (draw ability)
- `tests/audited/fdn/232/tests.py` — Audited tests for Scavenging Ooze (graveyard exile)
- `tests/audited/fdn/182/tests.py` — Audited tests for Reassembling Skeleton (graveyard recursion)
- `tests/audited/fdn/228b/tests.py` — Audited tests for Mild-Mannered Librarian (transform ability)

## Item 10: FDN audited tests Batch 4 — Enchantments, equipment, artifacts, and planeswalkers

### Implementation
- `tests/audited/fdn/conftest.py` — Added collector-directory overrides for 129b (Leyline Axe) and synthetic dirs 800-821 for cards without collector numbers
- `tests/audited/fdn/501/tests.py` — Audited tests for Pacifism (aura, can't attack/block)
- `tests/audited/fdn/529/tests.py` — Audited tests for Untamed Hunger (aura, +2/+1, menace)
- `tests/audited/fdn/722/tests.py` — Audited tests for Unflinching Courage (aura, +2/+2, trample, lifelink)
- `tests/audited/fdn/810/tests.py` — Audited tests for Holy Strength (aura, +1/+2)
- `tests/audited/fdn/811/tests.py` — Audited tests for Unholy Strength (aura, +2/+1)
- `tests/audited/fdn/812/tests.py` — Audited tests for Stab Wound (aura, -2/-2)
- `tests/audited/fdn/813/tests.py` — Audited tests for Arrest (aura, can't attack/block/activate)
- `tests/audited/fdn/565/tests.py` — Audited tests for Angelic Destiny (aura, +4/+4, flying, first strike)
- `tests/audited/fdn/213/tests.py` — Audited tests for Blanchwood Armor (aura)
- `tests/audited/fdn/26/tests.py` — Audited tests for Twinblade Blessing (aura, double strike)
- `tests/audited/fdn/514/tests.py` — Audited tests for Starlight Snare (aura)
- `tests/audited/fdn/156/tests.py` — Audited tests for Imprisoned in the Moon (aura)
- `tests/audited/fdn/168/tests.py` — Audited tests for Witness Protection (aura)
- `tests/audited/fdn/507/tests.py` — Audited tests for Eaten by Piranhas (aura)
- `tests/audited/fdn/709/tests.py` — Audited tests for Confiscate (aura)
- `tests/audited/fdn/557/tests.py` — Audited tests for New Horizons (aura)
- `tests/audited/fdn/641/tests.py` — Audited tests for Ordeal of Nylea (aura)
- `tests/audited/fdn/539/tests.py` — Audited tests for Goblin Oriflamme (global enchantment)
- `tests/audited/fdn/814/tests.py` — Audited tests for Glorious Anthem (global enchantment, +1/+1)
- `tests/audited/fdn/815/tests.py` — Audited tests for Dictate of Heliod (global enchantment, +2/+2)
- `tests/audited/fdn/816/tests.py` — Audited tests for Brave the Sands (global enchantment, vigilance)
- `tests/audited/fdn/817/tests.py` — Audited tests for Levitation (global enchantment, flying)
- `tests/audited/fdn/116/tests.py` — Audited tests for Anthem of Champions (global enchantment, +1/+1)
- `tests/audited/fdn/137/tests.py` — Audited tests for Authority of the Consuls (global enchantment)
- `tests/audited/fdn/138/tests.py` — Audited tests for Banishing Light (global enchantment)
- `tests/audited/fdn/220/tests.py` — Audited tests for Garruk's Uprising (global enchantment, trample)
- `tests/audited/fdn/717/tests.py` — Audited tests for Impact Tremors (global enchantment)
- `tests/audited/fdn/92/tests.py` — Audited tests for Rite of the Dragoncaller (global enchantment)
- `tests/audited/fdn/179/tests.py` — Audited tests for Painful Quandary (global enchantment)
- `tests/audited/fdn/180/tests.py` — Audited tests for Phyrexian Arena (global enchantment)
- `tests/audited/fdn/615/tests.py` — Audited tests for Vampiric Rites (global enchantment)
- `tests/audited/fdn/803/tests.py` — Audited tests for Bonesplitter (equipment, +2/+0)
- `tests/audited/fdn/804/tests.py` — Audited tests for Swiftfoot Boots (equipment, hexproof+haste)
- `tests/audited/fdn/805/tests.py` — Audited tests for Whispersilk Cloak (equipment, hexproof+unblockable)
- `tests/audited/fdn/806/tests.py` — Audited tests for Mask of Memory (equipment)
- `tests/audited/fdn/669/tests.py` — Audited tests for Basilisk Collar (equipment, deathtouch+lifelink)
- `tests/audited/fdn/674/tests.py` — Audited tests for Fireshrieker (equipment, double strike)
- `tests/audited/fdn/130/tests.py` — Audited tests for Quick-Draw Katana (equipment)
- `tests/audited/fdn/253/tests.py` — Audited tests for Goldvein Pick (equipment, +1/+1)
- `tests/audited/fdn/249/tests.py` — Audited tests for Adventuring Gear (equipment)
- `tests/audited/fdn/5/tests.py` — Audited tests for Celestial Armor (equipment)
- `tests/audited/fdn/129b/tests.py` — Audited tests for Leyline Axe (equipment, double strike+trample)
- `tests/audited/fdn/128/tests.py` — Audited tests for Fishing Pole (equipment)
- `tests/audited/fdn/563/tests.py` — Audited tests for Pirate's Cutlass (equipment)
- `tests/audited/fdn/800/tests.py` — Audited tests for Sol Ring (artifact, tap for CC)
- `tests/audited/fdn/801/tests.py` — Audited tests for Arcane Signet (artifact, tap for C)
- `tests/audited/fdn/802/tests.py` — Audited tests for Mind Stone (artifact, tap for C)
- `tests/audited/fdn/807/tests.py` — Audited tests for Altar of the Brood (artifact)
- `tests/audited/fdn/808/tests.py` — Audited tests for Elixir of Immortality (artifact)
- `tests/audited/fdn/809/tests.py` — Audited tests for Relic of Progenitus (artifact)
- `tests/audited/fdn/726/tests.py` — Audited tests for Hedron Archive (artifact, tap for CC)
- `tests/audited/fdn/725/tests.py` — Audited tests for Gilded Lotus (artifact, tap for 3)
- `tests/audited/fdn/534/tests.py` — Audited tests for Carnelian Orb of Dragonkind (artifact, tap for R)
- `tests/audited/fdn/254/tests.py` — Audited tests for Heraldic Banner (artifact)
- `tests/audited/fdn/677/tests.py` — Audited tests for Pyromancer's Goggles (artifact, legendary, tap R)
- `tests/audited/fdn/127/tests.py` — Audited tests for Banner of Kinship (artifact)
- `tests/audited/fdn/131/tests.py` — Audited tests for Ravenous Amulet (artifact)
- `tests/audited/fdn/562/tests.py` — Audited tests for Goblin Firebomb (artifact)
`tests/audited/fdn/673/tests.py` - Audited tests for Feldon's Cane (artifact) 
- `tests/audited/fdn/680/tests.py` — Audited tests for Soul-Guide Lantern (artifact)
- `tests/audited/fdn/679/tests.py` — Audited tests for Sorcerous Spyglass (artifact)
- `tests/audited/fdn/676/tests.py` — Audited tests for Mazemind Tome (artifact)
- `tests/audited/fdn/724/tests.py` — Audited tests for Expedition Map (artifact)
- `tests/audited/fdn/617/tests.py` — Audited tests for Wishclaw Talisman (artifact)
- `tests/audited/fdn/670/tests.py` — Audited tests for Cultivator's Caravan (artifact vehicle)
- `tests/audited/fdn/251/tests.py` — Audited tests for Campus Guide (artifact creature)
- `tests/audited/fdn/255/tests.py` — Audited tests for Juggernaut (artifact creature)
- `tests/audited/fdn/671/tests.py` — Audited tests for Darksteel Colossus (artifact creature, trample+indestructible)
- `tests/audited/fdn/672/tests.py` — Audited tests for Diamond Mare (artifact creature)
- `tests/audited/fdn/675/tests.py` — Audited tests for Gate Colossus (artifact creature)
- `tests/audited/fdn/681/tests.py` — Audited tests for Steel Hellkite (artifact creature, flying)
- `tests/audited/fdn/682/tests.py` — Audited tests for Three Tree Mascot (artifact creature, changeling)
- `tests/audited/fdn/723/tests.py` — Audited tests for Adaptive Automaton (artifact creature)
- `tests/audited/fdn/678/tests.py` — Audited tests for Ramos, Dragon Engine (artifact creature, legendary, flying)
- `tests/audited/fdn/132/tests.py` — Audited tests for Scrawling Crawler (artifact creature)
- `tests/audited/fdn/818/tests.py` — Audited tests for Ajani, Caller of the Pride (planeswalker, 4 loyalty)
- `tests/audited/fdn/819/tests.py` — Audited tests for Chandra, Torch of Defiance (planeswalker, 4 loyalty)
- `tests/audited/fdn/820/tests.py` — Audited tests for Liliana, Dreadhorde General (planeswalker, 6 loyalty)
- `tests/audited/fdn/821/tests.py` — Audited tests for Nissa, Worldwaker (planeswalker, 3 loyalty)
- `tests/audited/fdn/44/tests.py` — Audited tests for Kaito, Cunning Infiltrator (planeswalker, 3 loyalty, token)
- `tests/audited/fdn/81/tests.py` — Audited tests for Chandra, Flameshaper (planeswalker, 6 loyalty, mana)
- `tests/audited/fdn/234/tests.py` — Audited tests for Vivien Reid (planeswalker, 5 loyalty)

## Item 11: FDN audited tests Batch 5 — Non-basic lands, SPG cards, and remaining cards

### Implementation
- `tests/audited/fdn/conftest.py` — Added collision overrides (75b, 76b, 81b) and synthetic dirs 822-829 for remaining no-CN cards
- `tests/audited/fdn/259/tests.py` — Audited tests for Bloodfell Caves (gain land, ETB tapped, {B}/{R})
- `tests/audited/fdn/260/tests.py` — Audited tests for Blossoming Sands (gain land, ETB tapped, {G}/{W})
- `tests/audited/fdn/261/tests.py` — Audited tests for Dismal Backwater (gain land, ETB tapped, {U}/{B})
- `tests/audited/fdn/262/tests.py` — Audited tests for Evolving Wilds (fetch land, sacrifice)
- `tests/audited/fdn/263/tests.py` — Audited tests for Jungle Hollow (gain land, ETB tapped, {B}/{G})
- `tests/audited/fdn/264/tests.py` — Audited tests for Rogue's Passage (colorless mana, unblockable ability)
- `tests/audited/fdn/265/tests.py` — Audited tests for Rugged Highlands (gain land, ETB tapped, {R}/{G})
- `tests/audited/fdn/266/tests.py` — Audited tests for Scoured Barrens (gain land, ETB tapped, {W}/{B})
- `tests/audited/fdn/268/tests.py` — Audited tests for Swiftwater Cliffs (gain land, ETB tapped, {U}/{R})
- `tests/audited/fdn/269/tests.py` — Audited tests for Thornwood Falls (gain land, ETB tapped, {G}/{U})
- `tests/audited/fdn/270/tests.py` — Audited tests for Tranquil Cove (gain land, ETB tapped, {W}/{U})
- `tests/audited/fdn/271/tests.py` — Audited tests for Wind-Scarred Crag (gain land, ETB tapped, {R}/{W})
- `tests/audited/fdn/133/tests.py` — Audited tests for Soulstone Sanctuary (colorless mana, +1/+1 counter ability)
- `tests/audited/fdn/74/tests.py` — Audited tests for Condemn (SPG instant, attacking creature removal)
- `tests/audited/fdn/75b/tests.py` — Audited tests for Sphinx's Tutelage (SPG enchantment, draw-trigger mill)
- `tests/audited/fdn/76b/tests.py` — Audited tests for Grim Tutor (SPG sorcery, tutor + life loss)
- `tests/audited/fdn/77/tests.py` — Audited tests for Embercleave (SPG equipment, flash, cost reduction, ETB attach)
- `tests/audited/fdn/78/tests.py` — Audited tests for Goblin Bushwhacker (SPG creature, kicker)
- `tests/audited/fdn/79/tests.py` — Audited tests for Bloom Tender (SPG creature, color-based mana)
- `tests/audited/fdn/80/tests.py` — Audited tests for Paradise Druid (SPG creature, any-color mana, hexproof)
- `tests/audited/fdn/81b/tests.py` — Audited tests for Akroma's Memorial (SPG artifact, keyword granting)
- `tests/audited/fdn/82/tests.py` — Audited tests for Temporal Manipulation (SPG sorcery, extra turn)
- `tests/audited/fdn/83/tests.py` — Audited tests for Fiend Artisan (SPG creature, hybrid mana, CDA P/T)
- `tests/audited/fdn/99/tests.py` — Audited tests for Apothecary Stomper (modal ETB creature)
- `tests/audited/fdn/224/tests.py` — Audited tests for Gnarlid Colony (kicker creature)
`tests/audited/fdn/568/tests.py` - Audited tests for Charming Prince (modal ETB creature) 
- `tests/audited/fdn/713/tests.py` — Audited tests for Gatekeeper of Malakir (kicker creature)
- `tests/audited/fdn/822/tests.py` — Audited tests for Abzan Charm (modal instant, 3 modes)
- `tests/audited/fdn/823/tests.py` — Audited tests for Boros Charm (modal instant, 3 modes)
- `tests/audited/fdn/824/tests.py` — Audited tests for Prismari Command (modal instant, 4 modes)
- `tests/audited/fdn/825/tests.py` — Audited tests for Sublime Epiphany (modal instant, 5 modes)
- `tests/audited/fdn/826/tests.py` — Audited tests for Dromoka's Command (modal sorcery, 4 modes)
- `tests/audited/fdn/827/tests.py` — Audited tests for Austere Command (modal sorcery, 4 modes)
- `tests/audited/fdn/828/tests.py` — Audited tests for Collective Brutality (modal sorcery, 3 modes)
- `tests/audited/fdn/829/tests.py` — Audited tests for Inscription of Insight (modal sorcery, 3 modes)

## Item 12: SOS audited tests Batch 1 — Trivial and simple complexity cards

### Implementation
- `tests/audited/sos/267/tests.py` — Audited tests for Plains (basic land, trivial)
- `tests/audited/sos/268/tests.py` — Audited tests for Island (basic land, trivial)
- `tests/audited/sos/269/tests.py` — Audited tests for Swamp (basic land, trivial)
- `tests/audited/sos/270/tests.py` — Audited tests for Mountain (basic land, trivial)
- `tests/audited/sos/271/tests.py` — Audited tests for Forest (basic land, trivial)
- `tests/audited/sos/11/tests.py` — Audited tests for Eager Glyphmage (creature, ETB token)
- `tests/audited/sos/36/tests.py` — Audited tests for Stone Docent (creature, graveyard ability)
- `tests/audited/sos/50/tests.py` — Audited tests for Fractal Anomaly (instant, token creation)
- `tests/audited/sos/65/tests.py` — Audited tests for Quick Study (instant, draw two)
- `tests/audited/sos/82/tests.py` — Audited tests for Eternal Student (creature, graveyard ability)
- `tests/audited/sos/94/tests.py` — Audited tests for Pox Plague (sorcery, symmetric effect)
- `tests/audited/sos/100/tests.py` — Audited tests for Send in the Pest (sorcery, discard + token)
- `tests/audited/sos/147/tests.py` — Audited tests for Environmental Scientist (creature, ETB search)
- `tests/audited/sos/158/tests.py` — Audited tests for Planar Engineering (sorcery, sacrifice + search)
- `tests/audited/sos/171/tests.py` — Audited tests for Abstract Paintmage (creature, mana ability)
- `tests/audited/sos/176/tests.py` — Audited tests for Blech, Loafing Pest (legendary creature, counter trigger)
- `tests/audited/sos/177/tests.py` — Audited tests for Bogwater Lumaret (creature, life gain trigger)
- `tests/audited/sos/184/tests.py` — Audited tests for Dina's Guidance (instant, creature tutor)
- `tests/audited/sos/186/tests.py` — Audited tests for Embrace the Paradox (instant, draw + land drop)
- `tests/audited/sos/191/tests.py` — Audited tests for Geometer's Arthropod (creature, X-spell trigger)
- `tests/audited/sos/202/tests.py` — Audited tests for Mind into Matter (sorcery, X draw + cheat)
- `tests/audited/sos/219/tests.py` — Audited tests for Rapturous Moment (sorcery, draw/discard/mana)
- `tests/audited/sos/222/tests.py` — Audited tests for Root Manipulation (sorcery, pump + menace)
- `tests/audited/sos/230/tests.py` — Audited tests for Spirit Mascot (creature, graveyard trigger)
- `tests/audited/sos/232/tests.py` — Audited tests for Stadium Tidalmage (creature, ETB/attack draw)
- `tests/audited/sos/234/tests.py` — Audited tests for Stirring Honormancer (creature, ETB look)
- `tests/audited/sos/246/tests.py` — Audited tests for Zaffai and the Tempests (legendary creature, free cast)
- `tests/audited/sos/249/tests.py` — Audited tests for Mage Tower Referee (artifact creature, multicolor trigger)
- `tests/audited/sos/265/tests.py` — Audited tests for Terramorphic Expanse (land, fetch ability)
- `tests/audited/sos/soa_3/tests.py` — Audited tests for Armageddon (sorcery, destroy all lands)
- `tests/audited/sos/soa_6/tests.py` — Audited tests for Hop to It (sorcery, create 3 tokens)
- `tests/audited/sos/soa_16/tests.py` — Audited tests for Deduce (instant, draw + investigate)
- `tests/audited/sos/soa_21/tests.py` — Audited tests for Preordain (sorcery, scry + draw)
- `tests/audited/sos/soa_22/tests.py` — Audited tests for Sleight of Hand (sorcery, look + pick)
- `tests/audited/sos/soa_24/tests.py` — Audited tests for Stock Up (sorcery, look at 5 + pick 2)
- `tests/audited/sos/soa_25/tests.py` — Audited tests for Ad Nauseam (instant, reveal + life loss)
- `tests/audited/sos/soa_33/tests.py` — Audited tests for Smallpox (sorcery, symmetric sacrifice)
- `tests/audited/sos/soa_34/tests.py` — Audited tests for Stargaze (sorcery, X draw + mill)
- `tests/audited/sos/soa_35/tests.py` — Audited tests for Vampiric Tutor (instant, tutor + life)
- `tests/audited/sos/soa_46/tests.py` — Audited tests for Pyretic Ritual (instant, add RRR)
- `tests/audited/sos/soa_48/tests.py` — Audited tests for Subterranean Tremors (sorcery, X damage)
- `tests/audited/sos/soa_49/tests.py` — Audited tests for Awaken the Woods (sorcery, X dryad tokens)
- `tests/audited/sos/soa_53/tests.py` — Audited tests for Glimpse of Nature (sorcery, creature-cast draw)
- `tests/audited/sos/soa_58/tests.py` — Audited tests for Shared Roots (sorcery lesson, basic land search)
- `tests/audited/sos/soa_59/tests.py` — Audited tests for Triumph of the Hordes (sorcery, pump + infect)
- `tests/audited/sos/soa_62/tests.py` — Audited tests for Culling Ritual (sorcery, destroy low MV + mana)
- `tests/audited/sos/soa_63/tests.py` — Audited tests for Deflecting Palm (instant, damage prevention)
- `tests/audited/sos/soa_64/tests.py` — Audited tests for Expressive Iteration (sorcery, top 3 split)
- `tests/audited/sos/spg_150/tests.py` — Audited tests for Archmage Emeritus (creature, magecraft draw)
- `tests/audited/sos/spg_151/tests.py` — Audited tests for Murmuring Mystic (creature, spell-cast token)
