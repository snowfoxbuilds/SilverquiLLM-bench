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
