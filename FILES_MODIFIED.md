# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Upgrade 4 simplified Aura implementations to full oracle text

### Tests
- `tests/audited/fdn/fdn_26/tests.py` — stub (no audited tests yet)
- `tests/audited/fdn/fdn_156/tests.py` — stub (no audited tests yet)
- `tests/audited/fdn/fdn_168/tests.py` — stub (no audited tests yet)
- `tests/audited/fdn/fdn_213/tests.py` — stub (no audited tests yet)

### Implementation
- `cards/fdn/fdn_26/card_impl.py` — Added apply_continuous_effect() hook, cleaned imports, structured Layer 6 double strike grant
- `cards/fdn/fdn_156/card_impl.py` — Split single effect into Layer 4 (type) + Layer 6 (ability) separate ContinuousEffects, added ENGINE LIMITATION for mana ability
- `cards/fdn/fdn_168/card_impl.py` — Split into 4 layers: Layer 4 (type/name), Layer 5 (color), Layer 6 (ability), Layer 7b (SET_PT), added Color import
- `cards/fdn/fdn_213/card_impl.py` — Added apply_continuous_effect() hook, extracted _count_forests() helper, cleaned imports


## Item 2: Upgrade 3 simplified Planeswalker implementations to full oracle text

### Tests
- `tests/audited/fdn/fdn_44/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_81/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_234/tests.py` — Stub (no audited tests yet)

### Implementation
- `cards/fdn/fdn_44/card_impl.py` — Full rewrite: passive properly guards on combat flag, +1 loot, −2 Ninja token, −9 emblem via SPELL_CAST trigger
- `cards/fdn/fdn_81/card_impl.py` — Full rewrite: +2 uses choose_card() to pick one exiled card as playable, +1 uses sacrifice() and END_STEP event, −4 supports _damage_assignments
- `cards/fdn/fdn_234/card_impl.py` — Full rewrite: +1 uses choose_card() for optional creature/land selection, −3 lazy revalidation, −8 ContinuousEffect emblem
- `engine/triggers.py` — Added END_STEP event type to EventType enum


## Item 3: Upgrade 3 simplified Equipment/Creature implementations to full oracle text

### Tests
- `tests/audited/fdn/fdn_5/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_258/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_61/tests.py` — Stub (no audited tests yet)

### Implementation
- `cards/fdn/fdn_5/card_impl.py` — Full rewrite: ETB moved to on_resolve(), DURATION_END_OF_TURN for protection, Layer 7c P/T + Layer 6 flying; added get_targets() with TargetRequirement, controller check in on_resolve(), removed fallback logic
- `cards/fdn/fdn_258/card_impl.py` — Cleaned up: extracted _make_equip_ability(), removed unused imports, proper Layer 6 hexproof+haste
- `cards/fdn/fdn_61/card_impl.py` — Added attack trigger with choose_card() sacrifice + add_counter(), kept death trigger; fixed choose_card signature, synced _original_plus_one_counters

## Item 4: Implement White new cards — batch 1 (10 creatures)

### Implementation
- `cards/fdn/fdn_1/card_impl.py` — Sire of Seven Deaths: 7/7 Eldrazi with 7 keywords (first strike, vigilance, menace, trample, reach, lifelink, ward)
- `cards/fdn/fdn_2/card_impl.py` — Arahbo, the First Fang: Cat lord (+1/+1 ContinuousEffect) + ETB token trigger; self-ETB handled in on_resolve() per KEY_DECISIONS
- `cards/fdn/fdn_3/card_impl.py` — Armasaur Guide: Vigilance + attack trigger (3+ attackers → +1/+1 counter on target)
- `cards/fdn/fdn_4/card_impl.py` — Cat Collector: ETB creates Food token + first life-gain per turn creates Cat token (turn_number tracking for reset)
- `cards/fdn/fdn_8/card_impl.py` — Dauntless Veteran: Attack trigger grants all creatures +1/+1 until EOT via ContinuousEffect
- `cards/fdn/fdn_9/card_impl.py` — Dazzling Angel: Flying + ETB trigger (another creature enters → gain 1 life)
- `cards/fdn/fdn_11/card_impl.py` — Exemplar of Light: Flying + life-gain → +1/+1 counter + once-per-turn draw (turn_number tracking for reset)
- `cards/fdn/fdn_12/card_impl.py` — Felidar Savior: Lifelink + ETB in on_resolve() puts +1/+1 counters on up to two targets (two TargetRequirements)
- `cards/fdn/fdn_15/card_impl.py` — Hare Apparent: ETB creates Rabbit tokens equal to other Hare Apparents you control
- `cards/fdn/fdn_17/card_impl.py` — Herald of Eternal Dawn: Flash, Flying + continuous effect for can't-lose/can't-win with cleanup in unregister_triggers()

## Item 5: Implement White new cards — batch 2 (10 creatures + spells)

### Implementation
- `cards/fdn/fdn_6/card_impl.py` — Claws Out: Instant with Affinity for Cats (ENGINE LIMITATION) + creatures get +2/+2 until EOT via ContinuousEffect
- `cards/fdn/fdn_10/card_impl.py` — Divine Resilience: Instant with Kicker, grants indestructible until EOT (all targets when kicked)
- `cards/fdn/fdn_13/card_impl.py` — Fleeting Flight: Instant combat trick with +1/+1 counter, flying until EOT, combat damage prevention (ENGINE LIMITATION)
- `cards/fdn/fdn_18/card_impl.py` — Inspiring Paladin: 3/3 Human Knight with conditional first strike during your turn via ContinuousEffect
- `cards/fdn/fdn_22/card_impl.py` — Raise the Past: Sorcery returning all creature cards with MV≤2 from graveyard to battlefield via move_to_zone
- `cards/fdn/fdn_23/card_impl.py` — Skyknight Squire: 1/1 Cat Scout with ETB counter trigger and threshold flying+Knight at 3+ counters
- `cards/fdn/fdn_24/card_impl.py` — Squad Rallier: 3/4 Human Scout with activated ability to dig top 4 for creature with power≤2
- `cards/fdn/fdn_25/card_impl.py` — Sun-Blessed Healer: 3/1 Human Cleric with Lifelink, Kicker ETB returns nonland permanent MV≤2 from graveyard
- `cards/fdn/fdn_27/card_impl.py` — Valkyrie's Call: Enchantment with death trigger returning nontoken non-Angel creatures with +1/+1 counter and Angel flying
- `cards/fdn/fdn_28/card_impl.py` — Vanguard Seraph: 3/3 Angel Warrior with Flying and once-per-turn life-gain surveil 1 trigger

## Item 6: Implement Blue new cards — batch 1 (10 creatures)

### Implementation
- `cards/fdn/fdn_29/card_impl.py` — Arcane Epiphany: Instant with cost_reduction() for Wizard control, draws 3 cards
- `cards/fdn/fdn_30/card_impl.py` — Archmage of Runes: 3/6 Giant Wizard with SPELL_CAST trigger drawing card on instant/sorcery (ENGINE LIMITATION for cost reduction of other spells)
- `cards/fdn/fdn_31/card_impl.py` — Bigfin Bouncer: 3/2 Shark Pirate with ETB bounce via on_resolve() and move_to_zone()
- `cards/fdn/fdn_32/card_impl.py` — Cephalid Inkmage: 2/2 Octopus Wizard with ETB surveil 3 and threshold unblockable ContinuousEffect
- `cards/fdn/fdn_33/card_impl.py` — Clinquant Skymage: 1/1 Bird Wizard Flying with DRAWS_CARD trigger for +1/+1 counters
- `cards/fdn/fdn_34/card_impl.py` — Curator of Destinies: 5/5 Sphinx Flying uncounterable with ETB Fact-or-Fiction pile split
- `cards/fdn/fdn_35/card_impl.py` — Drake Hatcher: 1/3 Human Wizard Vigilance+Prowess with combat damage incubation counters and activated ability for Drake tokens
- `cards/fdn/fdn_37/card_impl.py` — Erudite Wizard: 2/3 Human Wizard with second-card-drawn-each-turn +1/+1 counter trigger
- `cards/fdn/fdn_38/card_impl.py` — Faebloom Trick: Instant creating two Faerie tokens with reflexive tap trigger
- `cards/fdn/fdn_39/card_impl.py` — Grappling Kraken: 5/6 Kraken with landfall tap + stun counter on opponent creature

## Item 7: Implement Blue new cards — batch 2 (10 creatures + spells)

### Tests
- `tests/audited/fdn/fdn_40/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_41/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_43/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_45/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_46/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_47/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_48/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_50/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_51/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_53/tests.py` — Stub (no audited tests yet)

### Implementation
- `cards/fdn/fdn_40/card_impl.py` — High Fae Trickster: Flash+Flying creature with continuous effect granting controller cast-as-flash
- `cards/fdn/fdn_41/card_impl.py` — Homunculus Horde: 2/2 with second-card-drawn trigger creating copy token
- `cards/fdn/fdn_43/card_impl.py` — Inspiration from Beyond: Sorcery mill 3 then return instant/sorcery from graveyard (flashback stored)
- `cards/fdn/fdn_45/card_impl.py` — Kiora, the Rising Tide: Legendary Merfolk with ETB draw/discard and threshold attack trigger creating 8/8 token
- `cards/fdn/fdn_46/card_impl.py` — Lunar Insight: Sorcery drawing cards equal to distinct mana values among nonland permanents
- `cards/fdn/fdn_47/card_impl.py` — Mischievous Mystic: Flying 2/1 with second-card-drawn trigger creating 1/1 Faerie token with flying
- `cards/fdn/fdn_48/card_impl.py` — Refute: Counterspell instant that counters any spell then loots (draw+discard)
- `cards/fdn/fdn_50/card_impl.py` — Skyship Buccaneer: Flying 4/3 with Raid ETB draw
- `cards/fdn/fdn_51/card_impl.py` — Sphinx of Forgotten Lore: Flash+Flying with attack trigger granting flashback to graveyard instant/sorcery
- `cards/fdn/fdn_53/card_impl.py` — Uncharted Voyage: Instant putting creature on top/bottom of owner's library then surveil 1

## Item 8: Implement Black new cards (19 cards)

### Implementation
- `cards/fdn/fdn_54/card_impl.py` — Abyssal Harvester: 3/2 Demon Warlock with tap ability to exile creature from graveyard and create Nightmare token copy
- `cards/fdn/fdn_55/card_impl.py` — Arbiter of Woe: 5/4 Demon with additional sac cost, Flying, ETB opponents discard+lose 2, you draw+gain 2 (already implemented)
- `cards/fdn/fdn_56/card_impl.py` — Billowing Shriekmass: 2/3 Spirit Flying with ETB mill 3 and threshold +2/+1 continuous effect
- `cards/fdn/fdn_57/card_impl.py` — Blasphemous Edict: Sorcery with alternative cost (13+ creatures) and each player sacrifices 13 creatures
- `cards/fdn/fdn_58/card_impl.py` — Bloodthirsty Conqueror: 5/5 Vampire Knight Flying+Deathtouch with opponent life-loss trigger for life gain
- `cards/fdn/fdn_59/card_impl.py` — Crypt Feaster: 3/4 Zombie Menace with threshold attack trigger for +2/+0 until EOT
- `cards/fdn/fdn_60/card_impl.py` — Gutless Plunderer: 2/2 Skeleton Pirate Deathtouch with Raid ETB look-at-top-3 mill
- `cards/fdn/fdn_63/card_impl.py` — Infernal Vessel: 2/1 Human Cleric with death trigger returning as Demon with +1/+1 counters (already implemented)
- `cards/fdn/fdn_65/card_impl.py` — Midnight Snack: Enchantment with Raid end-step Food token creation and sacrifice ability for life drain
- `cards/fdn/fdn_66/card_impl.py` — Nine-Lives Familiar: 1/1 Cat with 8 revival counters and death trigger return (already implemented)
- `cards/fdn/fdn_67/card_impl.py` — Revenge of the Rats: Sorcery creating tapped Rat tokens equal to creature cards in graveyard with flashback
- `cards/fdn/fdn_68/card_impl.py` — Sanguine Syphoner: 1/3 Vampire Warlock with attack trigger draining 1 from each opponent
- `cards/fdn/fdn_70/card_impl.py` — Soul-Shackled Zombie: 4/2 Zombie with ETB exile up to 2 cards from graveyard and creature-exile life drain
- `cards/fdn/fdn_71/card_impl.py` — Stab: {B} Instant giving target creature -2/-2 until end of turn
- `cards/fdn/fdn_72/card_impl.py` — Tinybones Bauble Burglar: 1/3 Legendary Skeleton Rogue with discard-exile trigger and tap discard ability
- `cards/fdn/fdn_73/card_impl.py` — Tragic Banshee: 5/3 Spirit with Morbid ETB -1/-1 or -13/-13 on opponent creature
- `cards/fdn/fdn_74/card_impl.py` — Vampire Gourmand: 2/2 Vampire with attack trigger sacrifice-for-draw and unblockable
- `cards/fdn/fdn_75/card_impl.py` — Vampire Soulcaller: 3/2 Vampire Warlock Flying, can't block, ETB return creature from graveyard (already implemented)
- `cards/fdn/fdn_77/card_impl.py` — Zul Ashur Lich Lord: 2/2 Legendary Zombie Warlock with Ward and tap to cast Zombie from graveyard

## Item 9: Implement Red new cards (15 cards)

### Implementation
- `cards/fdn/fdn_78/card_impl.py` — Battlesong Berserker: 3/4 Human Berserker with "whenever you attack" trigger granting target creature +1/+0 and menace until EOT
- `cards/fdn/fdn_79/card_impl.py` — Boltwave: {R} Sorcery dealing 3 damage to each opponent
- `cards/fdn/fdn_80/card_impl.py` — Bulk Up: Instant doubling target creature's power until EOT with Flashback {4}{R}{R}
- `cards/fdn/fdn_82/card_impl.py` — Courageous Goblin: 2/2 Goblin with conditional attack trigger (+1/+0 and menace if you control power 4+)
- `cards/fdn/fdn_83/card_impl.py` — Crackling Cyclops: 0/4 with SPELL_CAST trigger for +3/+0 on noncreature spells
- `cards/fdn/fdn_85/card_impl.py` — Electroduplicate: Sorcery creating token copy with haste and end-step sacrifice, Flashback {2}{R}{R}
- `cards/fdn/fdn_86/card_impl.py` — Fiery Annihilation: Instant dealing 5 damage to creature, exiling attached Equipment, exile-on-death replacement
- `cards/fdn/fdn_87/card_impl.py` — Goblin Boarders: 3/2 Goblin Pirate with Raid ETB +1/+1 counter
- `cards/fdn/fdn_88/card_impl.py` — Goblin Negotiation: {X}{R}{R} Sorcery dealing X damage with excess-damage Goblin token creation
- `cards/fdn/fdn_89/card_impl.py` — Gorehorn Raider: 4/4 with Raid ETB dealing 2 damage to any target
- `cards/fdn/fdn_91/card_impl.py` — Kellan Planar Trailblazer: Legendary 2/1 with two activated abilities for class progression (Scout→Detective→Rogue)
- `cards/fdn/fdn_93/card_impl.py` — Searslicer Goblin: 2/1 with Raid end-step trigger creating 1/1 Goblin token
- `cards/fdn/fdn_94/card_impl.py` — Slumbering Cerberus: 4/2 Dog with skip_untap and Morbid end-step untap trigger
- `cards/fdn/fdn_96/card_impl.py` — Strongbox Raider: 5/2 with Raid ETB exiling top 2, choose one playable until end of next turn
- `cards/fdn/fdn_97/card_impl.py` — Twinflame Tyrant: 3/5 Dragon Flying with damage-doubling continuous effect for damage to opponents

## Item 10: Implement Green new cards (14 cards)

### Implementation
- `cards/fdn/fdn_98/card_impl.py` — Ambush Wolf: Flash 4/2 Wolf with ETB exile from graveyard (already implemented)
- `cards/fdn/fdn_100/card_impl.py` — Beast-Kin Ranger: 3/3 Trample Elf Ranger with +1/+0 EOT on other creature ETB
- `cards/fdn/fdn_101/card_impl.py` — Cackling Prowler: 4/3 Ward Hyena Rogue with Morbid end-step +1/+1 counter
- `cards/fdn/fdn_102/card_impl.py` — Eager Trufflesnout: 4/2 Trample Boar with combat damage Food token trigger
- `cards/fdn/fdn_103/card_impl.py` — Elfsworn Giant: 5/3 Reach Giant with landfall 1/1 Elf Warrior token creation
- `cards/fdn/fdn_104/card_impl.py` — Elvish Regrower: 4/3 Elf Druid with ETB return permanent from graveyard (already implemented)
- `cards/fdn/fdn_105/card_impl.py` — Felling Blow: Sorcery with +1/+1 counter then one-way damage (already implemented)
- `cards/fdn/fdn_106/card_impl.py` — Loot Exuberant Explorer: 1/4 Legendary with extra land and activated dig-for-creature ability
- `cards/fdn/fdn_107/card_impl.py` — Mossborn Hydra: 0/0 Trample with ETB +1/+1 counter and landfall counter doubling
- `cards/fdn/fdn_108/card_impl.py` — Needletooth Pack: 4/5 Dinosaur with Morbid end-step two +1/+1 counters on target
- `cards/fdn/fdn_109/card_impl.py` — Preposterous Proportions: Sorcery giving +10/+10 and vigilance until EOT
- `cards/fdn/fdn_111/card_impl.py` — Quilled Greatwurm: 7/7 Trample with combat damage +1/+1 counter trigger
- `cards/fdn/fdn_112/card_impl.py` — Spinner of Souls: 4/3 Reach Spider with death trigger library dig (already implemented)
- `cards/fdn/fdn_113/card_impl.py` — Sylvan Scavenging: Enchantment with modal end-step (+1/+1 counter or 3/3 Raccoon token)

## Item 11: Implement Multicolor new cards (11 cards)

### Implementation
- `cards/fdn/fdn_115/card_impl.py` — Alesha Who Laughs at Fate: First strike + attack counter + Raid end-step graveyard recursion (MV ≤ power)
- `cards/fdn/fdn_117/card_impl.py` — Ashroot Animist: Trample + attack trigger granting +X/+X and trample until EOT
- `cards/fdn/fdn_118/card_impl.py` — Dreadwing Scavenger: Flying + ETB/attack loot + threshold +1/+1 and deathtouch
- `cards/fdn/fdn_119/card_impl.py` — Elenda Saint of Dusk: Lifelink + life-based conditional P/T boost via ContinuousEffect
- `cards/fdn/fdn_120/card_impl.py` — Fiendish Panda: Life-gain counter trigger + death trigger graveyard recursion (non-Bear, MV ≤ power)
- `cards/fdn/fdn_121/card_impl.py` — Koma World-Eater: Uncounterable trample ward with combat damage four 3/3 Serpent token trigger
- `cards/fdn/fdn_122/card_impl.py` — Kykar Zephyr Awakener: Noncreature spell cast modal trigger (flicker or Spirit token)
- `cards/fdn/fdn_123/card_impl.py` — Niv-Mizzet Visionary: No max hand size + noncombat damage draw trigger with per-event closure
- `cards/fdn/fdn_124/card_impl.py` — Perforating Artist: Deathtouch + Raid end-step punisher (sacrifice/discard/lose 3)
- `cards/fdn/fdn_125/card_impl.py` — Wardens of the Cycle: Morbid end-step modal (gain 2 life or draw + lose 1 life)
- `cards/fdn/fdn_126/card_impl.py` — Zimone Paradox Sculptor: Beginning-of-combat +1/+1 counters + activated ability to double counters

## Item 12: Implement White + Blue reprints (18 cards)

### Implementation
- `cards/fdn/fdn_135/card_impl.py` — Ajani's Pridemate: life-gain trigger adding +1/+1 counters
- `cards/fdn/fdn_136/card_impl.py` — Angel of Finality: already implemented (ETB exile graveyard)
- `cards/fdn/fdn_140/card_impl.py` — Day of Judgment: board wipe destroying all creatures
- `cards/fdn/fdn_141/card_impl.py` — Giada Font of Hope: Angel ETB counter trigger + tap mana ability
- `cards/fdn/fdn_144/card_impl.py` — Mischievous Pup: already implemented (Flash + ETB bounce)
- `cards/fdn/fdn_149/card_impl.py` — Youthful Valkyrie: Angel ETB +1/+1 counter trigger
- `cards/fdn/fdn_151/card_impl.py` — Aetherize: return all attacking creatures to hand
- `cards/fdn/fdn_152/card_impl.py` — Brineborn Cutthroat: Flash + spell-cast-on-opponent-turn counter trigger
- `cards/fdn/fdn_154/card_impl.py` — Extravagant Replication: upkeep token copy trigger
- `cards/fdn/fdn_157/card_impl.py` — Lightshell Duo: Prowess + ETB surveil 2
- `cards/fdn/fdn_158/card_impl.py` — Micromancer: ETB search library for MV 1 instant/sorcery
- `cards/fdn/fdn_159/card_impl.py` — Mocking Sprite: Flying + cost reduction continuous effect
- `cards/fdn/fdn_160/card_impl.py` — An Offer You Can't Refuse: counter noncreature spell + Treasure tokens
- `cards/fdn/fdn_161/card_impl.py` — Omniscience: continuous effect for free casting
- `cards/fdn/fdn_163/card_impl.py` — Self-Reflection: token copy of creature + flashback
- `cards/fdn/fdn_165/card_impl.py` — Think Twice: draw card + flashback
- `cards/fdn/fdn_166/card_impl.py` — Time Stop: end the turn (exile stack, discard to hand size)
- `cards/fdn/fdn_167/card_impl.py` — Tolarian Terror: cost_reduction per instant/sorcery in graveyard + Ward

## Item 13: Implement Black + Red reprints (21 cards)

### Implementation
- `cards/fdn/fdn_170/card_impl.py` — Burglar Rat: kept existing ETB discard-each-opponent trigger
- `cards/fdn/fdn_171/card_impl.py` — Diregraf Ghoul: 2/2 Zombie that enters tapped via on_resolve()
- `cards/fdn/fdn_174/card_impl.py` — Fake Your Own Death: full rewrite with +2/+0 buff and CREATURE_DIES death trigger for graveyard return + Treasure
- `cards/fdn/fdn_177/card_impl.py` — Macabre Waltz: sorcery returning up to 2 creature cards from graveyard then discard
- `cards/fdn/fdn_178/card_impl.py` — Marauding Blight-Priest: GAINS_LIFE trigger draining each opponent 1 life
- `cards/fdn/fdn_183/card_impl.py` — Rise of the Dark Realms: sorcery putting all creature cards from all graveyards onto battlefield
- `cards/fdn/fdn_184/card_impl.py` — Rune-Scarred Demon: 6/6 Flying Demon with ETB library search for any card
- `cards/fdn/fdn_185/card_impl.py` — Stromkirk Bloodthief: end step trigger with opponent life-loss check, +1/+1 counter on target Vampire
- `cards/fdn/fdn_187/card_impl.py` — Zombify: kept existing graveyard-to-battlefield reanimation
- `cards/fdn/fdn_190/card_impl.py` — Brass's Bounty: creates Treasure tokens equal to lands controlled
- `cards/fdn/fdn_193/card_impl.py` — Drakuseth Maw of Flames: attack trigger dealing 4+3+3 damage to chosen targets
- `cards/fdn/fdn_194/card_impl.py` — Etali Primal Storm: attack trigger exiling top cards and simplified free-casting
- `cards/fdn/fdn_196/card_impl.py` — Firebrand Archer: SPELL_CAST noncreature trigger dealing 1 to each opponent
- `cards/fdn/fdn_197/card_impl.py` — Firespitter Whelp: Flying + SPELL_CAST noncreature/Dragon trigger dealing 1 to each opponent
- `cards/fdn/fdn_198/card_impl.py` — Flamewake Phoenix: Flying+Haste with must_attack and Ferocious graveyard recursion at beginning of combat
- `cards/fdn/fdn_199/card_impl.py` — Frenzied Goblin: attack trigger with optional {R} payment for can't-block effect
- `cards/fdn/fdn_202/card_impl.py` — Hidetsugu's Second Rite: instant dealing 10 if target has exactly 10 life
- `cards/fdn/fdn_203/card_impl.py` — Involuntary Employment: gain control + untap + haste + Treasure token creation
`cards/fdn/fdn_205/card_impl.py` - Seismic Rupture: deals 2 damage to each creature without flying 
- `cards/fdn/fdn_208/card_impl.py` — Spitfire Lagac: landfall trigger dealing 1 to each opponent
- `cards/fdn/fdn_210/card_impl.py` — Thrill of Possibility: instant drawing 2 cards (discard cost assumed paid during casting)

## Item 14: Green + Multicolor reprints (24 cards)

### Implementation
- `cards/fdn/fdn_211/card_impl.py` — Affectionate Indrik: ETB fight target creature you don't control
- `cards/fdn/fdn_216/card_impl.py` — Doubling Season: replacement effects for token and counter doubling
- `cards/fdn/fdn_217/card_impl.py` — Dwynen, Gilt-Leaf Daen: Elf lord +1/+1 and attack life-gain trigger
- `cards/fdn/fdn_218/card_impl.py` — Dwynen's Elite: ETB create 1/1 Elf Warrior token if you control another Elf
- `cards/fdn/fdn_221/card_impl.py` — Genesis Wave: reveal top X, put permanents with MV<=X onto battlefield
- `cards/fdn/fdn_222/card_impl.py` — Ghalta, Primal Hunger: cost reduction by total power of creatures controlled
- `cards/fdn/fdn_225/card_impl.py` — Grow from the Ashes: search for basic land(s) with kicker, shuffle library
- `cards/fdn/fdn_226/card_impl.py` — Inspiring Call: draw per +1/+1 counter creature, grant indestructible
- `cards/fdn/fdn_229/card_impl.py` — Nessian Hornbeetle: beginning of combat +1/+1 if you control 4+ power creature
- `cards/fdn/fdn_230/card_impl.py` — Overrun: +3/+3 and trample until end of turn continuous effects
- `cards/fdn/fdn_236/card_impl.py` — Wildwood Scourge: enters with X +1/+1 counters, counter synergy marker
- `cards/fdn/fdn_237/card_impl.py` — Balmor, Battlemage Captain: spell-cast trigger for +1/+0 and trample
- `cards/fdn/fdn_238/card_impl.py` — Consuming Aberration: CDA P/T and spell-cast mill trigger
- `cards/fdn/fdn_239/card_impl.py` — Empyrean Eagle: flying lord +1/+1 continuous effect
- `cards/fdn/fdn_240/card_impl.py` — Good-Fortune Unicorn: ETB +1/+1 counter on other creatures entering
- `cards/fdn/fdn_241/card_impl.py` — Heroic Reinforcements: create 2 Soldier tokens, +1/+1 and haste
- `cards/fdn/fdn_242/card_impl.py` — Lathril, Blade of the Elves: combat damage token creation and tap-10-elves ability
- `cards/fdn/fdn_243/card_impl.py` — Muldrotha, the Gravetide: graveyard casting marker (engine limitation)
- `cards/fdn/fdn_244/card_impl.py` — Progenitus: protection from everything and graveyard replacement effect
- `cards/fdn/fdn_245/card_impl.py` — Ruby, Daring Tracker: added attack trigger for +2/+2 with 4+ power creature
- `cards/fdn/fdn_246/card_impl.py` — Swiftblade Vindicator: fixed subtypes from Warrior to Soldier
- `cards/fdn/fdn_247/card_impl.py` — Tatyova, Benthic Druid: landfall trigger for life gain and card draw
- `cards/fdn/fdn_248/card_impl.py` — Thousand-Year Storm: spell-cast copy trigger tracking storm count
