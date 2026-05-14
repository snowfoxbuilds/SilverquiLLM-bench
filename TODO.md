# TODO

## Phase 10: FDN Card Implementations (174 cards)

Scope: Implement all remaining FDN cards that currently have TODO stubs in `cards/fdn/fdn_{num}/card_impl.py`, and write corresponding Audited Eval tests in `tests/audited/fdn/fdn_{num}/tests.py`. This covers 10 simplified implementations that need full rewrites and 164 cards with no implementation.

Reference: `KEY_DECISIONS.md` for conventions, `CONTEXT.md` for vocabulary, `engine/card.py` for base classes. Each Card Spec (`card_spec.json`) is the source of truth for oracle text and metadata. Tests use `DeterministicPlayer` for reproducible game states. The `conftest.py` in `tests/audited/fdn/` handles per-collector-directory `card_impl` injection — tests import via `from card_impl import ClassName`.

Prerequisite: Phase 10 items 3–4 (FDN spec generation + migration) must be complete — card stubs and `card_spec.json` files must exist in `cards/fdn/`. Note that `cards/foundations/` has been deleted; existing simplified implementations are already in `cards/fdn/fdn_{num}/card_impl.py`. Reference material from foundations can be recovered from Git history if needed.

Conventions (from KEY_[DECISIONS.md](http://decisions.md/) — all items MUST honor):

- **FDN per-card layout**: `cards/fdn/fdn_{num}/card_impl.py` + `card_spec.json`. SPG cards use `spg_` prefix.
- **ETB event ordering**: fire `ENTERS_BATTLEFIELD` BEFORE calling `register_triggers()`. Self-ETB effects go in `on_resolve()`, not triggers.
- **`move_to_zone()`**: single entry point for all zone transitions.
- **`ENGINE LIMITATION`** comments: use this exact phrase when working around engine gaps.
- **`StackObject.targets`**: single source of truth for chosen targets between cast and resolve.
- **Lazy target filters**: filter targets at resolution time using `game` parameter, not at cast time.
- **Continuous effects**: P/T bonuses in Layer 7c (`SubLayer.MODIFY_PT`), keywords in Layer 6 (`Layer.ABILITY`).
- **`ZoneContainer.shuffle()`**: use for library shuffling, not `random.shuffle()`.
- **SBA event ordering**: fire events BEFORE `unregister()` so death triggers match.
- **Audited test injection**: conftest builds registry per collector directory. Each test directory imports only its own card class.
---

- [x] **Upgrade 4 simplified Aura implementations to full oracle text**
  Detail: These cards have existing simplified implementations in `cards/fdn/` that omit mechanics from their full oracle text. Read each card's `card_spec.json` for the full oracle text, compare against the current `card_impl.py`, identify what was simplified, and rewrite to full spec.

  Cards (4):

  - **#26 Twinblade Blessing** (`fdn_26`): {1}{W}{W} Aura. Flash, enchant creature, grants double strike. Base class: `Aura`. Key mechanics: flash keyword, `apply_continuous_effect()` granting `Keyword.DOUBLE_STRIKE` in Layer 6.
  - **#156 Imprisoned in the Moon** (`fdn_156`): {2}{U} Aura. Enchant creature/land/planeswalker, enchanted permanent loses all abilities and is a colorless land with "{T}: Add {C}". Base class: `Aura`. Key mechanics: continuous effect replacing card types/abilities/mana abilities in Layer 4 (type-changing) and Layer 6 (ability removal). Mark remaining gaps with `ENGINE LIMITATION`.
  - **#168 Witness Protection** (`fdn_168`): {U} Aura. Enchant creature, enchanted creature loses all abilities, becomes a green/white Citizen 1/1 named "Legitimate Businessperson". Base class: `Aura`. Key mechanics: continuous effect overriding name, types, colors, P/T, and removing abilities. Layers: type-changing (4), color (5), ability (6), P/T-setting (7b).
  - **#213 Blanchwood Armor** (`fdn_213`): {2}{G} Aura. Enchant creature, +1/+1 for each Forest you control. Base class: `Aura`. Key mechanics: dynamic P/T bonus via `ContinuousEffect` in Layer 7c (`SubLayer.MODIFY_PT`), counting Forests with subtype check.
  Impl files: `cards/fdn/fdn_{26,156,168,213}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{26,156,168,213}/tests.py`

  Testability: Test aura attachment via `on_resolve()`, verify continuous effects apply and remove correctly, test enchanted creature characteristics. Use `DeterministicPlayer` to set up game states with target creatures.

- [x] **Upgrade 3 simplified Planeswalker implementations to full oracle text**
  Detail: These planeswalkers have existing simplified implementations with reduced loyalty abilities. Read each `card_spec.json` for full ability set and rewrite.

  Cards (3):

  - **#44 Kaito, Cunning Infiltrator** (`fdn_44`): {1}{U}{U} Planeswalker (loyalty 3). Passive: combat damage → loyalty counter. +1: unblockable + loot. −2: create 2/1 Ninja token. −9: emblem (whenever a player casts a spell, create 2/1 Ninja token). Base class: `Planeswalker`. Key mechanics: `get_loyalty_abilities()` returning `LoyaltyAbility` instances, token creation, emblem via persistent trigger, passive via `register_triggers()`.
  - **#81 Chandra, Flameshaper** (`fdn_81`): {3}{R}{R} Planeswalker. Review `card_spec.json` for full abilities — likely damage-dealing effects, possible exile-and-cast. Base class: `Planeswalker`.
  - **#234 Vivien Reid** (`fdn_234`): {3}{G}{G} Planeswalker (loyalty 5). +1: look at top 4, reveal creature/land to hand. −3: destroy target artifact/enchantment/creature with flying. −8: emblem giving creatures +2/+2, vigilance, trample, indestructible. Base class: `Planeswalker`. Key mechanics: library manipulation, targeted destruction with `get_targets()` + lazy filters, emblem via `ContinuousEffect`.
  Impl files: `cards/fdn/fdn_{44,81,234}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{44,81,234}/tests.py`

  Testability: Test each loyalty ability independently. Test loyalty counter changes. Test token creation. Test emblem persistence. Verify `get_loyalty_abilities()` returns correct costs and effects.

- [x] **Upgrade 3 simplified Equipment/Creature implementations to full oracle text**
  Detail: Remaining simplified cards — 2 equipment and 1 creature with death triggers.

  Cards (3):

  - **#5 Celestial Armor** (`fdn_5`): {2}{W} Equipment. Flash, ETB auto-attach + grant hexproof/indestructible until end of turn, equipped creature +2/+0 and flying, equip {3}{W}. Current impl has `ENGINE LIMITATION` for colored equip cost and "until end of turn" duration. Base class: `Artifact`. Key mechanics: flash keyword, ETB via `on_resolve()` (per KEY_DECISIONS ETB ordering), equip as `ActivatedAbility`, continuous effects for P/T (Layer 7c) and keywords (Layer 6). Fix: implement proper "until end of turn" cleanup if engine now supports it, otherwise keep `ENGINE LIMITATION`.
  - **#258 Swiftfoot Boots** (`fdn_258`): {2} Equipment. Grants hexproof + haste, equip {1}. Base class: `Artifact`. Key mechanics: `ContinuousEffect` granting keywords in Layer 6, `ActivatedAbility` for equip.
  - **#61 High-Society Hunter** (`fdn_61`): {3}{B}{B} Creature — Vampire Noble. Flying, attack trigger (sacrifice another creature for +1/+1 counter), death trigger (whenever another nontoken creature dies, draw a card). Base class: `Creature`. Key mechanics: `register_triggers()` for attack and death triggers, `plus_one_counters`, sacrifice choice via controller decision. Per KEY_DECISIONS, fire death events before unregister.
  Impl files: `cards/fdn/fdn_{5,258,61}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{5,258,61}/tests.py`

  Testability: Test equipment attach/detach, continuous effect application, equip ability activation. Test death trigger on nontoken creature death, sacrifice during attack. Use `DeterministicPlayer` for combat/decision sequences.

- [x] **Implement White new cards — batch 1 (10 creatures)**
  Detail: First 10 new white FDN creatures. Read each `card_spec.json` for oracle text.

  Cards: #1 Sire of Seven Deaths, #2 Arahbo the First Fang, #3 Armasaur Guide, #4 Cat Collector, #8 Dauntless Veteran, #9 Dazzling Angel, #11 Exemplar of Light, #12 Felidar Savior, #15 Hare Apparent, #17 Herald of Eternal Dawn.

  Expected types: `Creature` (lords, ETB triggers, keyword creatures). Key mechanics: keyword abilities (first strike, vigilance, lifelink, flying, ward), +1/+1 counters, token creation, lord effects via `ContinuousEffect`, triggered abilities via `register_triggers()`.

  Impl files: `cards/fdn/fdn_{1,2,3,4,8,9,11,12,15,17}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{1,2,3,4,8,9,11,12,15,17}/tests.py`

  Testability: Test keyword presence, P/T values, triggered ability firing, token creation, lord bonuses.

- [x] **Implement White new cards — batch 2 (10 creatures + spells)**
  Detail: Remaining 10 new white cards.

  Cards: #6 Claws Out, #10 Divine Resilience, #13 Fleeting Flight, #18 Inspiring Paladin, #22 Raise the Past, #23 Skyknight Squire, #24 Squad Rallier, #25 Sun-Blessed Healer, #27 Valkyrie's Call, #28 Vanguard Seraph.

  Expected types: mix of `Creature`, `Instant`, `Sorcery`. Key mechanics: combat tricks, temporary buffs, graveyard recursion (Raise the Past), token creation (Valkyrie's Call), triggered abilities.

  Impl files: `cards/fdn/fdn_{6,10,13,18,22,23,24,25,27,28}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{6,10,13,18,22,23,24,25,27,28}/tests.py`

  Testability: Test spell targeting with lazy filters, temporary buff duration, graveyard interaction.

- [ ] **Implement Blue new cards — batch 1 (10 creatures)**
  Detail: First 10 new blue FDN cards.

  Cards: #29 Arcane Epiphany, #30 Archmage of Runes, #31 Bigfin Bouncer, #32 Cephalid Inkmage, #33 Clinquant Skymage, #34 Curator of Destinies, #35 Drake Hatcher, #37 Erudite Wizard, #38 Faebloom Trick, #39 Grappling Kraken.

  Expected types: `Creature`, `Instant`. Key mechanics: card draw via `game.draw_card()`, bounce via `move_to_zone()`, cost reduction (use `cost_reduction()` override per KEY_DECISIONS), flash, flying.

  Impl files: `cards/fdn/fdn_{29,30,31,32,33,34,35,37,38,39}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{29,30,31,32,33,34,35,37,38,39}/tests.py`

  Testability: Test draw effects, bounce targets returning to hand, cost reduction conditions.

- [ ] **Implement Blue new cards — batch 2 (10 creatures + spells)**
  Detail: Remaining 10 new blue cards.

  Cards: #40 High Fae Trickster, #41 Homunculus Horde, #43 Inspiration from Beyond, #45 Kiora the Rising Tide, #46 Lunar Insight, #47 Mischievous Mystic, #48 Refute, #50 Skyship Buccaneer, #51 Sphinx of Forgotten Lore, #53 Uncharted Voyage.

  Expected types: `Creature`, `Instant`, `Sorcery`, `Planeswalker` (#45 Kiora). Key mechanics: counterspells, card draw, token creation, planeswalker loyalty abilities.

  Impl files: `cards/fdn/fdn_{40,41,43,45,46,47,48,50,51,53}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{40,41,43,45,46,47,48,50,51,53}/tests.py`

  Testability: Test counterspell resolution, planeswalker loyalty abilities, token creation.

- [ ] **Implement Black new cards (19 cards)**
  Detail: All 19 new black FDN cards.

  Cards: #54 Abyssal Harvester, #55 Arbiter of Woe, #56 Billowing Shriekmass, #57 Blasphemous Edict, #58 Bloodthirsty Conqueror, #59 Crypt Feaster, #60 Gutless Plunderer, #63 Infernal Vessel, #65 Midnight Snack, #66 Nine-Lives Familiar, #67 Revenge of the Rats, #68 Sanguine Syphoner, #70 Soul-Shackled Zombie, #71 Stab, #72 Tinybones Bauble Burglar, #73 Tragic Banshee, #74 Vampire Gourmand, #75 Vampire Soulcaller, #77 Zul Ashur Lich Lord.

  Expected types: `Creature`, `Instant`, `Sorcery`. Key mechanics: death triggers via `register_triggers()` with `EventType.CREATURE_DIES` (fire events before unregister per KEY_DECISIONS SBA ordering), sacrifice effects, graveyard exile/recursion, life drain via `deal_damage()`, discard effects, token creation. All zone transitions through `move_to_zone()`.

  Impl files: `cards/fdn/fdn_{54,55,56,57,58,59,60,63,65,66,67,68,70,71,72,73,74,75,77}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{54,55,56,57,58,59,60,63,65,66,67,68,70,71,72,73,74,75,77}/tests.py`

  Testability: Test death trigger firing, sacrifice mechanics, life total changes, discard resolution.

- [ ] **Implement Red new cards (15 cards)**
  Detail: All 15 new red FDN cards.

  Cards: #78 Battlesong Berserker, #79 Boltwave, #80 Bulk Up, #82 Courageous Goblin, #83 Crackling Cyclops, #85 Electroduplicate, #86 Fiery Annihilation, #87 Goblin Boarders, #88 Goblin Negotiation, #89 Gorehorn Raider, #91 Kellan Planar Trailblazer, #93 Searslicer Goblin, #94 Slumbering Cerberus, #96 Strongbox Raider, #97 Twinflame Tyrant.

  Expected types: `Creature`, `Instant`, `Sorcery`, `Enchantment`. Key mechanics: direct damage via `game.deal_damage()`, haste/menace keywords, attack triggers, temporary P/T boosts, token creation, target selection with lazy filters.

  Impl files: `cards/fdn/fdn_{78,79,80,82,83,85,86,87,88,89,91,93,94,96,97}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{78,79,80,82,83,85,86,87,88,89,91,93,94,96,97}/tests.py`

  Testability: Test damage dealt to targets, attack trigger effects, temporary buffs reset at end of turn.

- [ ] **Implement Green new cards (14 cards)**
  Detail: All 14 new green FDN cards.

  Cards: #98 Ambush Wolf, #100 Beast-Kin Ranger, #101 Cackling Prowler, #102 Eager Trufflesnout, #103 Elfsworn Giant, #104 Elvish Regrower, #105 Felling Blow, #106 Loot Exuberant Explorer, #107 Mossborn Hydra, #108 Needletooth Pack, #109 Preposterous Proportions, #111 Quilled Greatwurm, #112 Spinner of Souls, #113 Sylvan Scavenging.

  Expected types: `Creature`, `Instant`, `Sorcery`, `Enchantment — Aura` (#109). Key mechanics: trample keyword, ETB triggers, fight via mutual damage, `move_to_zone()` for ramp effects, `ZoneContainer.shuffle()` for library shuffles, +1/+1 counters, large creature bodies.

  Impl files: `cards/fdn/fdn_{98,100,101,102,103,104,105,106,107,108,109,111,112,113}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{98,100,101,102,103,104,105,106,107,108,109,111,112,113}/tests.py`

  Testability: Test ETB triggers, trample damage, fight resolution, ramp effects adding lands.

- [ ] **Implement Multicolor new cards (11 cards)**
  Detail: All 11 new multicolor FDN cards — legends and gold spells.

  Cards: #115 Alesha Who Laughs at Fate, #117 Ashroot Animist, #118 Dreadwing Scavenger, #119 Elenda Saint of Dusk, #120 Fiendish Panda, #121 Koma World-Eater, #122 Kykar Zephyr Awakener, #123 Niv-Mizzet Visionary, #124 Perforating Artist, #125 Wardens of the Cycle, #126 Zimone Paradox Sculptor.

  Expected types: `Creature` (legendary, multicolor synergy). Key mechanics: complex triggered abilities (Alesha — end step graveyard recursion if attacked), token creation (Koma — upkeep Serpent tokens, Kykar — spellcast Spirit tokens), multi-color mana costs, legendary supertype. Use lazy target filters for graveyard recursion targeting.

  Impl files: `cards/fdn/fdn_{115,117,118,119,120,121,122,123,124,125,126}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{115,117,118,119,120,121,122,123,124,125,126}/tests.py`

  Testability: Test multicolor mana payment, triggered ability conditions, token creation, legendary rule interactions.

- [ ] **Implement White + Blue reprints (18 cards)**
  Detail: Well-known MTG reprints — 6 white + 12 blue. Oracle text is established; implement from `card_spec.json` directly.

  White (6): #135 Ajani's Pridemate, #136 Angel of Finality, #140 Day of Judgment, #141 Giada Font of Hope, #144 Mischievous Pup, #149 Youthful Valkyrie.

  Blue (12): #151 Aetherize, #152 Brineborn Cutthroat, #154 Extravagant Replication, #157 Lightshell Duo, #158 Micromancer, #159 Mocking Sprite, #160 An Offer You Can't Refuse, #161 Omniscience, #163 Self-Reflection, #165 Think Twice, #166 Time Stop, #167 Tolarian Terror.

  Key mechanics: life-gain triggers (Ajani's Pridemate — +1/+1 counter on lifegain), board wipes (Day of Judgment — destroy all creatures), counterspells (Aetherize — bounce all attacking creatures, An Offer You Can't Refuse), flash creatures (Brineborn Cutthroat — grows on opponent's turn spells), flashback (Think Twice), cost reduction (Tolarian Terror — costs less per instant/sorcery in graveyard).

  Impl files: `cards/fdn/fdn_{135,136,140,141,144,149,151,152,154,157,158,159,160,161,163,165,166,167}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{135,136,140,141,144,149,151,152,154,157,158,159,160,161,163,165,166,167}/tests.py`

  Testability: Test life-gain trigger, board wipe resolution, counterspell targeting, flashback from graveyard, cost reduction calculation.

- [ ] **Implement Black + Red reprints (21 cards)**
  Detail: 9 black + 12 red reprint cards.

  Black (9): #170 Burglar Rat, #171 Diregraf Ghoul, #174 Fake Your Own Death, #177 Macabre Waltz, #178 Marauding Blight-Priest, #183 Rise of the Dark Realms, #184 Rune-Scarred Demon, #185 Stromkirk Bloodthief, #187 Zombify.

  Red (12): #190 Brass's Bounty, #193 Drakuseth Maw of Flames, #194 Etali Primal Storm, #196 Firebrand Archer, #197 Firespitter Whelp, #198 Flamewake Phoenix, #199 Frenzied Goblin, #202 Hidetsugu's Second Rite, #203 Involuntary Employment, #205 Seismic Rupture, #208 Spitfire Lagac, #210 Thrill of Possibility.

  Key mechanics: discard triggers (Burglar Rat — ETB opponent discards), graveyard recursion (Rise of the Dark Realms — all creatures from all graveyards, Zombify — single creature), ETB tutoring (Rune-Scarred Demon), Treasure token creation (Brass's Bounty), attack triggers (Drakuseth — deal damage on attack, Etali — exile top cards and cast free), phoenix recursion (Flamewake Phoenix — ferocious triggers), gain control (Involuntary Employment), direct damage.

  Impl files: `cards/fdn/fdn_{170,171,174,177,178,183,184,185,187,190,193,194,196,197,198,199,202,203,205,208,210}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{170,171,174,177,178,183,184,185,187,190,193,194,196,197,198,199,202,203,205,208,210}/tests.py`

  Testability: Test ETB discard effects, graveyard recursion targeting, Treasure token creation, attack trigger firing, zone transitions via `move_to_zone()`.

- [ ] **Implement Green + Multicolor reprints (24 cards)**
  Detail: 12 green + 12 multicolor reprint cards.

  Green (12): #211 Affectionate Indrik, #212 Bite Down, #216 Doubling Season, #217 Dwynen Gilt-Leaf Daen, #218 Dwynen's Elite, #221 Genesis Wave, #222 Ghalta Primal Hunger, #225 Grow from the Ashes, #226 Inspiring Call, #229 Nessian Hornbeetle, #230 Overrun, #236 Wildwood Scourge.

  Multicolor (12): #237 Balmor Battlemage Captain, #238 Consuming Aberration, #239 Empyrean Eagle, #240 Good-Fortune Unicorn, #241 Heroic Reinforcements, #242 Lathril Blade of the Elves, #243 Muldrotha the Gravetide, #244 Progenitus, #245 Ruby Daring Tracker, #246 Swiftblade Vindicator, #247 Tatyova Benthic Druid, #248 Thousand-Year Storm.

  Key mechanics: fight (Affectionate Indrik — ETB fight, Bite Down — one-way damage), replacement effects (Doubling Season — double counters and tokens), lord effects (Dwynen, Empyrean Eagle — pump creatures of type), cost reduction (Ghalta — costs less per total power), ramp (Grow from the Ashes — search for lands + `ZoneContainer.shuffle()`), counter synergy (Nessian Hornbeetle — upkeep +1/+1 if power 4+), prowess-like triggers (Balmor — spellcast gives +1/+0 and trample), graveyard casting (Muldrotha — cast permanents from graveyard), protection from everything (Progenitus), landfall triggers (Tatyova — draw on land ETB), spell copying (Thousand-Year Storm).

  Impl files: `cards/fdn/fdn_{211,212,216,217,218,221,222,225,226,229,230,236,237,238,239,240,241,242,243,244,245,246,247,248}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{211,212,216,217,218,221,222,225,226,229,230,236,237,238,239,240,241,242,243,244,245,246,247,248}/tests.py`

  Testability: Test fight resolution, replacement effects doubling counters/tokens, lord P/T bonuses, cost reduction, ramp, landfall triggers. Mark complex interactions (Doubling Season, Thousand-Year Storm, Muldrotha) with `ENGINE LIMITATION` where engine support is insufficient.

- [ ] **Implement Artifact reprints + Secluded Courtyard (9 cards)**
  Detail: 8 artifact reprints + 1 land reprint.

  Artifacts (8): #249 Adventuring Gear, #250 Burnished Hart, #251 Campus Guide, #252 Gleaming Barrier, #253 Goldvein Pick, #254 Heraldic Banner, #256 Meteor Golem, #257 Solemn Simulacrum.

  Land (1): #267 Secluded Courtyard.

  Key mechanics: Equipment with landfall (Adventuring Gear — land ETB gives +2/+2 until end of turn), sacrifice for ramp (Burnished Hart — sac to search 2 basics), ETB search (Campus Guide — search basic to top of library), death trigger Treasure (Gleaming Barrier — create Treasure on death), Equipment with damage trigger (Goldvein Pick — create Treasure when equipped creature deals combat damage), mana rock with lord effect (Heraldic Banner — chosen color mana + creatures of that color get +1/+0), ETB removal (Meteor Golem — destroy target nonland permanent), ETB draw + death ramp (Solemn Simulacrum — ETB search basic, death draw), tribal mana land (Secluded Courtyard — choose creature type on entry, tap for colorless or conditional any-color for chosen type).

  Base classes: `Artifact`, `ArtifactCreature`, `Land`.

  Impl files: `cards/fdn/fdn_{249,250,251,252,253,254,256,257,267}/card_impl.py`

  Test files: `tests/audited/fdn/fdn_{249,250,251,252,253,254,256,257,267}/tests.py`

  Testability: Test equipment attach + landfall trigger, sacrifice activation, ETB search with `ZoneContainer.shuffle()`, Treasure token creation, lord bonuses, replacement effect for land type choice. Mark mana spending restriction for Secluded Courtyard with `ENGINE LIMITATION` if engine doesn't support conditional mana.
