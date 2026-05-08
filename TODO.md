## Phase 4: Complete the Base Set (FDN 001–291)

Scope: Fix critical engine bugs, centralize zone-transition infrastructure, then implement all remaining Foundations limited format cards (~226 cards). This completes the Base Set for Replay Validation and Pipeline Validation Runs.

---

### Prerequisites

- [x] **Fix ****`is_aura`**** default ****`True`**** in ****`_sba_aura_unattached`**
  Detail: In `engine/state_based_actions.py`, the function `_sba_aura_unattached()` contains `getattr(obj, "is_aura", True)`. This means any object with an `attached_to` attribute but no explicit `is_aura` attr (e.g., Equipment cards like Bonesplitter, Swiftfoot Boots) is incorrectly treated as an unattached aura and sacrificed by SBAs. Change the default to `False`: `getattr(obj, "is_aura", False)`. This is a one-line fix but blocks all Equipment cards from functioning correctly.

  Files: `engine/state_based_actions.py` (line with `getattr(obj, "is_aura", True)` in `_sba_aura_unattached`).

  Acceptance criteria: Only objects that explicitly set `is_aura = True` (Aura subclasses) are checked for legal attachment. Existing equipment tests (Bonesplitter, Swiftfoot Boots, Whispersilk Cloak) still pass. Existing aura tests (Pacifism, Holy Strength) still correctly send unattached auras to graveyard.

  Testability: Add a focused test: equip Bonesplitter to a creature, run `resolve_state_based_actions()`, assert the equipment remains on the battlefield.

- [x] **Wire SBA trigger queueing in ****`resolve_state_based_actions()`**
  Detail: In `engine/state_based_actions.py`, `resolve_state_based_actions()` has a `# TODO: check for triggered abilities and put them on the stack` comment. Per MTG rules 704.3, after each SBA pass that performs actions, any triggered abilities that fired during those actions must be put on the stack before any player receives priority. The SBA loop must repeat until no more SBAs needed AND all pending triggers queued.

  Currently, zone-move helpers like `_move_to_graveyard()` call `game.trigger_manager.unregister(obj)` but `CREATURE_DIES` and `LEAVES_BATTLEFIELD` events are NOT fired from within SBAs — they’re only fired in `engine/game.py`’s `destroy()` and `sacrifice()`. Death triggers don’t fire when creatures die via SBAs (lethal damage, zero toughness).

  Fix: (a) In `_move_to_graveyard()`, fire `EventType.CREATURE_DIES` and `EventType.LEAVES_BATTLEFIELD` events after moving the object. (b) In `resolve_state_based_actions()`, after the SBA loop stabilizes, check if triggers were queued during processing and loop again if so. The outer loop: repeat { run SBA passes until stable; if triggers were put on stack during SBA processing, loop again } until no SBAs performed and no new triggers queued.

  Files: `engine/state_based_actions.py` (`_move_to_graveyard`, `resolve_state_based_actions`).

  Testability: Create a creature with a "when this creature dies" trigger. Deal lethal damage, call `resolve_state_based_actions()`, assert the trigger’s effect was pushed onto the stack.

- [x] **Centralize zone-transition hooks into ****`move_to_zone()`**
  Detail: Trigger registration/unregistration and event firing for zone transitions is duplicated across: `engine/casting.py` (`_resolve_spell` — registers triggers/replacement effects on ETB), `engine/state_based_actions.py` (`_move_to_graveyard` — unregisters on leaving battlefield), `engine/game.py` (`destroy()`, `sacrifice()`, `exile()`, `create_token()` — each independently handles unregistration + event firing). Every new zone-transition path (bounce, flicker, mill, reanimate) would need to duplicate this logic.

  Refactor into a centralized `move_to_zone(game, card, from_zone, to_zone)` function. This function should: (1) remove from source zone, (2) add to destination zone, (3) if leaving battlefield: unregister triggers and replacement effects, fire `LEAVES_BATTLEFIELD`, fire `CREATURE_DIES` if applicable, (4) if entering battlefield: call `register_triggers()` and `register_replacement_effects()`, fire `ENTERS_BATTLEFIELD`, (5) consult replacement effects for zone-change redirection (e.g., exile instead of graveyard). Then update all callers in `casting.py`, `state_based_actions.py`, and `game.py` to use this function.

  Files: `engine/zones.py` (add or extend `move_zone`), `engine/casting.py`, `engine/state_based_actions.py`, `engine/game.py`.

  Testability: All existing tests for casting, destruction, sacrifice, and exile must still pass. Add a test that uses `move_to_zone` to bounce a creature with a registered trigger — verify trigger is unregistered and `LEAVES_BATTLEFIELD` fires.

### Card Porting Batches

- [x] **Batch 1: Remaining vanilla & French vanilla creatures (~25–30 cards)**
  Detail: Implement all remaining FDN creatures with no abilities (vanilla) or only keyword abilities (French vanilla). These are the simplest cards and require zero engine changes. Use the existing `make_vanilla()` factory in `cards/foundations/simple_creatures.py` for pure-stat creatures. For French vanilla creatures with keywords already supported in `engine/types.py::Keyword` (flying, first strike, double strike, trample, vigilance, reach, deathtouch, lifelink, haste, hexproof, menace, defender, flash, indestructible), use `make_vanilla()` with the `keywords` parameter. Register each with `CardMetadata` including correct Scryfall collector numbers. Cross-reference the Scryfall FDN card list against existing implementations to identify what’s missing.

  Files: `cards/foundations/simple_creatures.py` (extend or new file `vanilla_creatures_batch2.py`), `cards/registry.py`.

  Testability: Each creature: instantiate, verify name/cost/power/toughness/keywords match Scryfall data. Integration: cast creature, verify it enters battlefield with correct stats and keywords.

- [ ] **Batch 2: Simple non-targeted instants & sorceries (~15–20 cards)**
  Detail: Implement remaining FDN instants and sorceries that don’t target (or target "you"): draw spells, lifegain, token creation, mill, "each player/opponent" effects. Subclass `Instant` or `Sorcery`, override `on_resolve()`. Use `engine/game.py` helpers: `draw_card()`, `create_token()`, `discard()`.

  Files: `cards/foundations/simple_spells.py` (extend or new file).

  Testability: For each spell: cast it, verify the effect (cards drawn, life gained, tokens created).

- [ ] **Batch 3: Simple targeted instants & sorceries (~15–20 cards)**
  Detail: Implement remaining FDN targeted spells: burn (deal N damage to target), targeted removal (destroy target creature/permanent), bounce (return target to hand), pump (+N/+N until end of turn), and fight spells. Follow existing patterns: override `get_targets()` to return `TargetRequirement`, override `on_resolve()` to use `_get_chosen_target()`. Use `deal_damage()`, `destroy()`, `exile()` from `engine/game.py`. For bounce spells, use the centralized `move_to_zone()` from prereq 3.

  Files: `cards/foundations/simple_spells.py` (extend or new file).

  Testability: For each targeted spell: set up a legal target, cast, verify target is affected.

- [ ] **Batch 4: Non-basic lands (~10–15 cards)**
  Detail: Implement FDN non-basic lands: tap lands (ETB tapped, tap for one of two colors), gain lands (ETB tapped, gain 1 life), utility lands (tap for colorless + activated ability). Subclass `Land`. For ETB-tapped lands, use a replacement effect or flag. For dual-color tap lands, override `get_mana_abilities()` to return two `ManaAbility` entries. For gain lands, register an ETB trigger for lifegain. May need to add a simple "enters tapped" mechanic as a flag on the `Land` class or via replacement effect.

  Files: New file `cards/foundations/lands.py`.

  Testability: Play each land, verify tapped/untapped state, activate mana ability, verify mana produced. For gain lands: verify life gained on ETB.

- [ ] **Batch 5: Creatures with ETB triggers (~20–25 cards)**
  Detail: Implement FDN creatures with "when this creature enters the battlefield" abilities: draw, damage, lifegain, tokens, destroy/exile target, bounce, counters. Depends on prereq 3 for clean ETB event firing. Subclass `Creature`, override `register_triggers()` to register `TriggerRegistration` with `EventType.ENTERS_BATTLEFIELD` and condition checking entering permanent is `self`. Use existing `engine/game.py` helpers for effects. Likely the largest batch.

  Files: New file `cards/foundations/etb_creatures.py`.

  Testability: For each: cast/put onto battlefield, verify trigger fires and effect resolves.

- [ ] **Batch 6: Auras (~10–12 cards)**
  Detail: Implement remaining FDN auras beyond those already in `enchantments.py`. Depends on prereq 1 (is_aura fix). Follow existing patterns: subclass `Aura`, override `get_targets()`, `on_resolve()` (set `self.attached_to`), register continuous effects via `game.effect_manager.add()`. Cover buff auras (+N/+N), debuff auras (-N/-N), keyword-granting auras, lockdown auras (can’t attack/block). For auras with triggered abilities, also override `register_triggers()`.

  Files: `cards/foundations/enchantments.py` (extend or new file).

  Testability: Cast targeting creature, verify attachment and continuous effect. Remove enchanted creature, verify aura goes to graveyard via SBA.

- [ ] **Batch 7: Equipment (~5–8 cards)**
  Detail: Implement remaining FDN equipment beyond those in `artifacts.py`. Depends on prereq 1. Follow Bonesplitter/Swiftfoot Boots pattern: subclass `Artifact`, add `subtypes={"Equipment"}`, implement equip activated ability, register continuous effects for equipped creature. Cover stat-boosting, keyword-granting, and triggered-ability equipment.

  Files: `cards/foundations/artifacts.py` (extend or new file).

  Testability: Cast, equip to creature, verify bonus. Equip to different creature, verify old creature loses bonus.

- [ ] **Batch 8: Creatures with death triggers (~15–20 cards)**
  Detail: Implement FDN creatures with "when this creature dies" abilities. Depends on prereq 2 (SBA trigger queueing). Override `register_triggers()` with `EventType.CREATURE_DIES` and condition `data["creature"] is self`. Effects: draw, damage, tokens, graveyard recursion. Also include "leaves the battlefield" triggers. After prereq 3, `move_to_zone()` handles firing these events consistently.

  Files: New file `cards/foundations/death_trigger_creatures.py`.

  Testability: Put on battlefield, kill it (lethal damage or destroy), verify trigger fires. Critical: death via SBA (deal lethal, call `resolve_state_based_actions()`, verify trigger on stack).

- [ ] **Batch 9: Creatures with activated abilities (~15–20 cards)**
  Detail: Implement FDN creatures with activated abilities: tap abilities, sacrifice abilities, mana abilities on creatures, pump abilities. Override `get_activated_abilities()` to return `ActivatedAbility` objects. Use `engine/abilities.py::ActivatedAbilityInstance` and `activate_ability()` for proper stack interaction. Tap abilities check `is_tapped` and set `is_tapped = True`. Sacrifice abilities remove the creature.

  Files: New file `cards/foundations/activated_creatures.py`.

  Testability: Put on battlefield, activate ability (ensure cost paid), verify effect. For tap abilities: verify can’t activate while tapped or with summoning sickness (unless haste).

- [ ] **Batch 10: Global enchantments & remaining non-aura enchantments (~8–12 cards)**
  Detail: Implement remaining FDN non-aura enchantments: anthem effects (your creatures get +N/+N), keyword-granting, triggered ability enchantments ("whenever you cast a spell", "at the beginning of your upkeep"), static-ability enchantments. Follow `enchantments.py` patterns. Use appropriate `Layer`/`SubLayer` for continuous effects.

  Files: `cards/foundations/enchantments.py` (extend or new file).

  Testability: Cast, verify effect applies. For triggered enchantments: trigger the event, verify it fires.

- [ ] **Batch 11: Remaining artifacts & planeswalkers (~10–15 cards)**
  Detail: Implement remaining FDN artifacts (utility artifacts, mana rocks, artifact creatures) and planeswalkers. For artifacts: follow `artifacts.py` patterns. For planeswalkers: subclass `Planeswalker`, set `starting_loyalty`, override `get_loyalty_abilities()` with `LoyaltyAbility` objects. Fully implement loyalty ability effects (not stubs). Set `Supertype.LEGENDARY` and planeswalker subtype.

  Files: `cards/foundations/artifacts.py` and `cards/foundations/planeswalkers.py` (extend).

  Testability: For artifacts: cast, activate abilities, verify effects. For planeswalkers: cast, activate loyalty abilities (verify loyalty changes), verify effects resolve.

- [ ] **Batch 12: Modal spells, X-cost spells, and remaining complex cards (~10–15 cards)**
  Detail: Implement any remaining FDN cards: modal choices ("choose one/two"), X-cost spells, kicker, and other complex mechanics. Follow `modal_spells.py` patterns: override `get_modes()`. For X-cost spells, add `x_value` attribute set during casting (may need minor `casting.py` extension to support X in mana costs). For kicker, add `kicked` boolean. This is the catch-all batch for everything not covered above.

  Files: `cards/foundations/modal_spells.py` (extend or new file).

  Testability: For modal: test each mode independently. For X spells: test with different X values. For kicker: test kicked and unkicked.
