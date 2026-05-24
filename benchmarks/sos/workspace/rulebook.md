# MTG Comprehensive Rules Reference

This document is the authoritative rules reference for implementing card behaviors
in the SilverquiLLM benchmark engine. It covers the Comprehensive Rules relevant
to card implementation, organized by topic.

---

## 1. Game Concepts

### 1.1 The Golden Rules
- If a card's text contradicts the rules, the card wins.
- "Can't" beats "can." If one effect says something can happen and another says it can't, the "can't" effect wins.
- If an effect would do something impossible, it does as much as possible and ignores the rest.

### 1.2 Players and Life Totals
- Each player starts at 20 life (standard two-player).
- A player who reaches 0 or less life loses (state-based action).
- A player who draws from an empty library loses (state-based action).
- A player who has 10 or more poison counters loses (state-based action).

---

## 2. Parts of a Card

### 2.1 Card Types
- **Creature** — has power and toughness; can attack and block.
- **Instant** — can be cast any time you have priority; goes to graveyard on resolution.
- **Sorcery** — can only be cast during your main phase with an empty stack; goes to graveyard on resolution.
- **Enchantment** — a permanent that provides ongoing effects.
- **Artifact** — a permanent, typically colorless.
- **Planeswalker** — a permanent with loyalty abilities.
- **Land** — played (not cast) once per turn; produces mana.

### 2.2 Supertypes
- **Legendary** — subject to the legend rule (see SBAs).
- **Basic** — a land with an intrinsic mana ability (Plains, Island, Swamp, Mountain, Forest).
- **Snow** — relevant for snow-matters effects.

### 2.3 Mana Cost and Colors
- Colors: White (W), Blue (U), Black (B), Red (R), Green (G).
- Generic mana (any color/colorless) is represented by a number.
- Converted mana cost (mana value) = total mana in the cost.
- A card's color is determined by the colored mana symbols in its cost (or by a color indicator).

---

## 3. Zones

Seven game zones exist:

| Zone | Description |
|------|-------------|
| **Library** | A player's deck (face-down, ordered). Drawing takes from the top. |
| **Hand** | Cards a player holds. Maximum hand size is 7 (checked at cleanup). |
| **Battlefield** | Where permanents exist. Shared zone. |
| **Graveyard** | Discard pile (face-up, ordered). |
| **Stack** | Where spells and abilities exist while resolving. |
| **Exile** | Removed-from-game zone. |
| **Command** | Zone for commanders, emblems, and other special objects. |

### 3.1 Zone Change Rules
- When a card moves to a new zone, it becomes a new object with no memory of its previous existence (exceptions: effects that specifically track zone changes).
- Tokens that leave the battlefield cease to exist as a state-based action.
- A permanent's controller is, by default, the player who put it onto the battlefield. Effects may cause a permanent to enter under a different player's control.

---

## 4. Turn Structure

### 4.1 Phases and Steps

```
Beginning Phase
  ├── Untap Step (no priority)
  ├── Upkeep Step
  └── Draw Step

Pre-combat Main Phase

Combat Phase
  ├── Beginning of Combat Step
  ├── Declare Attackers Step
  ├── Declare Blockers Step
  ├── Combat Damage Step (first strike / normal)
  └── End of Combat Step

Post-combat Main Phase

Ending Phase
  ├── End Step
  └── Cleanup Step (no priority unless triggers fire)
```

### 4.2 Priority
- The active player receives priority first in each step/phase after turn-based actions and triggered abilities are placed on the stack.
- After a spell/ability resolves, the active player gets priority.
- When all players pass priority in succession with nothing on the stack, the current phase/step ends.
- Players can only cast spells and activate abilities when they have priority.

### 4.3 Untap Step
- All permanents controlled by the active player untap (unless an effect prevents it).
- No player receives priority during this step (unless a triggered ability fires).

### 4.4 Draw Step
- The active player draws one card. This is a turn-based action, not a spell or ability.
- The first player skips their first draw step in a two-player game.

---

## 5. Casting Spells

### 5.1 Timing
- Sorceries and permanents: only during your main phase when the stack is empty.
- Instants and spells with flash: any time you have priority.

### 5.2 Steps to Cast
1. Move the spell to the stack.
2. Choose modes (if modal).
3. Choose targets (if any).
4. Choose how to divide or distribute effects (if applicable).
5. Determine the total cost (mana cost + additional costs − cost reductions).
6. Activate mana abilities (if needed).
7. Pay all costs simultaneously.

### 5.3 Alternative and Additional Costs
- Alternative costs replace the mana cost entirely (e.g., "you may pay {cost} rather than pay this spell's mana cost").
- Additional costs are paid on top of the mana cost (e.g., "as an additional cost, sacrifice a creature").
- Cost reductions reduce the amount paid but never below zero (for generic mana).

---

## 6. The Stack

### 6.1 Last-In, First-Out
- Spells and abilities resolve one at a time, top to bottom.
- After each resolution, the active player receives priority again.
- A spell or ability resolves only if all players pass priority in succession without adding anything to the stack.

### 6.2 Targets and Resolution
- Targets are chosen on casting/activation, not resolution.
- On resolution, targets are rechecked for legality. If all targets are illegal, the spell/ability is countered by game rules.
- If some (but not all) targets are illegal, the spell resolves but ignores the illegal targets.

### 6.3 Countering
- A countered spell goes to its owner's graveyard (unless otherwise specified).
- A countered ability simply ceases to exist.
- Costs are not refunded when a spell or ability is countered.

---

## 7. Combat

### 7.1 Beginning of Combat
- The active player gets priority. Effects that trigger "at the beginning of combat" go on the stack.

### 7.2 Declare Attackers
- The active player chooses which creatures will attack and which player/planeswalker they attack.
- Requirements: creature must be untapped, must have been continuously controlled since the start of the turn (unless haste), and must not have defender.
- Attacking creatures are tapped simultaneously (unless they have vigilance).

### 7.3 Declare Blockers
- The defending player assigns blockers. Each blocking creature is assigned to one attacking creature.
- A creature with menace must be blocked by two or more creatures.
- A creature with flying can only be blocked by creatures with flying or reach.
- Once a creature is blocked, it remains blocked even if all blockers are removed.
- An unblocked creature deals its damage to the defending player/planeswalker.

### 7.4 Combat Damage
- **First strike / double strike**: if any attacking or blocking creatures have first strike or double strike, there is a first-strike combat damage step. These creatures deal damage first.
- **Normal damage step**: creatures without first strike (plus double-strike creatures again) deal damage.
- Damage is dealt simultaneously within each damage step.
- **Trample**: if all blockers are assigned lethal damage, excess damage carries to the defending player/planeswalker. Lethal damage = toughness minus damage already marked, minimum 1 if the creature has deathtouch.
- **Damage assignment order**: if multiple creatures block one attacker, the attacking player assigns damage in the declared order, assigning at least lethal to each before moving to the next.

### 7.5 End of Combat
- "At end of combat" triggers fire. "Until end of combat" effects expire as the combat phase ends (after the end of combat step), before the post-combat main phase begins.

---

## 8. Keyword Abilities

### 8.1 Evasion / Combat Keywords
| Keyword | Rule | Effect |
|---------|------|--------|
| Flying | 702.9 | Can only be blocked by creatures with flying or reach. |
| Reach | 702.5 | Can block creatures with flying. |
| Menace | 702.19 | Must be blocked by two or more creatures. |
| Trample | 702.6 | Excess combat damage assigned to defending player. |
| Vigilance | 702.7 | Attacking doesn't cause this creature to tap. |
| Defender | 702.11 | Can't attack. |
| Haste | 702.3 | Can attack and use {T} abilities the turn it enters the battlefield. |
| Intimidate | 702.13 | Can only be blocked by artifact creatures or creatures sharing a color. |

### 8.2 Damage / Combat Modifiers
| Keyword | Rule | Effect |
|---------|------|--------|
| First Strike | 702.2 | Deals combat damage in the first-strike damage step. |
| Double Strike | 702.15 | Deals combat damage in both the first-strike and normal damage steps. |
| Deathtouch | 702.10 | Any amount of damage dealt by this creature is lethal. |
| Lifelink | 702.13 | Damage dealt by this creature also gains its controller that much life. |
| Indestructible | 702.12 | Can't be destroyed by damage or "destroy" effects. |
| Wither | 702.56 | Damage is dealt in the form of -1/-1 counters. |
| Infect | 702.89 | Deals damage to creatures as -1/-1 counters and to players as poison counters. |

### 8.3 Protection and Evasion
| Keyword | Rule | Effect |
|---------|------|--------|
| Hexproof | 702.8 | Can't be targeted by spells or abilities opponents control. |
| Shroud | 702.4 | Can't be targeted by any spells or abilities. |
| Ward | 702.44 | When targeted by an opponent, counter the spell/ability unless they pay the ward cost. |
| Protection | 702.16 | Can't be damaged, enchanted/equipped, blocked, or targeted by sources of the stated quality (DEBT). |

### 8.4 Utility Keywords
| Keyword | Rule | Effect |
|---------|------|--------|
| Flash | 702.12 | Can be cast any time you could cast an instant. |
| Equip | 702.14 | Sorcery-speed: attach this Equipment to target creature you control. |
| Enchant | 702.15 | Defines what an Aura can be attached to. |
| Prowess | 702.107 | Whenever you cast a noncreature spell, this creature gets +1/+1 until end of turn. |

---

## 9. Triggered Abilities

### 9.1 Structure
- "When/Whenever/At [event], [effect]."
- Triggered abilities trigger automatically when their condition is met.
- They go on the stack the next time a player would receive priority.

### 9.2 Intervening-If
- "When [event], if [condition], [effect]." — the condition is checked both when the ability would trigger AND on resolution. If false at either point, nothing happens.

### 9.3 Leaves-the-Battlefield Triggers
- Use last-known information (the permanent's characteristics as it last existed on the battlefield).

### 9.4 Enter-the-Battlefield (ETB) Triggers
- "When [this] enters the battlefield, [effect]."
- The permanent is on the battlefield when the trigger resolves.

---

## 10. Activated Abilities

### 10.1 Structure
- "[Cost]: [Effect]." — The colon separates cost from effect.
- Activated abilities can be activated any time the controller has priority (unless restricted).
- Mana abilities (that produce mana and don't target) don't use the stack.

### 10.2 Loyalty Abilities
- Planeswalker abilities are activated abilities with a loyalty cost.
- Only one loyalty ability per planeswalker per turn, at sorcery speed.

---

## 11. Static Abilities and Continuous Effects

### 11.1 Layer System
Continuous effects are applied in layers (in order):
1. Copy effects
2. Control-changing effects
3. Text-changing effects
4. Type-changing effects
5. Color-changing effects
6. Ability-adding/removing effects
7. Power/toughness changes:
   - 7a: characteristic-defining abilities
   - 7b: set P/T to specific value
   - 7c: modifications not from counters (+N/+N effects)
   - 7d: counters
   - 7e: effects that switch P/T

### 11.2 Timestamps
- Within the same layer, effects are applied in timestamp order (the order they entered the battlefield or were created).
- Dependencies override timestamps when two effects in the same layer depend on each other.

### 11.3 Replacement Effects
- "If [event] would [happen], [alternative] instead."
- Applied before the original event occurs.
- Each replacement effect can apply to a given event only once.
- The affected player (or controller of the affected object) chooses which replacement effect applies first if multiple apply.

---

## 12. State-Based Actions (SBAs)

Checked whenever a player would receive priority (not during resolution):

| Condition | Result |
|-----------|--------|
| Player at 0 or less life | That player loses. |
| Player with 10+ poison counters | That player loses. |
| Player attempted to draw from empty library | That player loses. |
| Creature with toughness 0 or less | Put into graveyard (not destroyed). |
| Creature with lethal damage | Destroyed (unless indestructible). |
| Creature with deathtouch damage marked | Destroyed (unless indestructible). |
| Planeswalker with 0 loyalty | Put into graveyard. |
| Two+ legendary permanents with same name, same controller | Controller chooses one to keep; rest go to graveyard. |
| Aura not attached or attached illegally | Put into graveyard. |
| Equipment/Fortification attached illegally | Unattached (stays on battlefield). |
| Token not on battlefield | Ceases to exist. |
| +1/+1 and -1/-1 counters on same permanent | Remove in pairs until only one type remains. |

SBAs are performed simultaneously and repeatedly until none apply, then triggered abilities are placed on the stack.

---

## 13. Damage

### 13.1 Damage Rules
- Damage dealt to a creature is marked on it until cleanup.
- Damage doesn't reduce toughness (it is tracked separately).
- If total damage marked >= toughness, the creature has lethal damage (SBA destroys it unless indestructible).
- Damage dealt to a player reduces their life total.

### 13.2 Damage Prevention
- "Prevent the next N damage" — reduces the damage dealt.
- Prevention is a replacement effect (applied before damage is dealt).

### 13.3 Destroy vs. Damage
- "Destroy" is not damage. Indestructible prevents both lethal-damage destruction and "destroy" effects, but not sacrifice, exile, or -X/-X effects.

---

## 14. Counters

### 14.1 +1/+1 and -1/-1 Counters
- Modify creature's power and toughness (layer 7d).
- Cancel each other out (state-based action removes matching pairs).

### 14.2 Loyalty Counters
- Planeswalkers enter with loyalty counters equal to their starting loyalty.
- Loyalty abilities add or remove loyalty counters as costs.

### 14.3 Other Counters
- Various named counters exist (charge, -1/-1, +1/+1, poison, etc.).
- Counter type is significant only if a rule or effect references it specifically.

---

## 15. Multiplayer Considerations (Two-Player Default)

The benchmark primarily models two-player games:
- One active player, one defending player.
- Effects referencing "each opponent" apply to the single opponent.
- "Target player" can be either player unless restricted.

---

## 16. Special Actions

- Playing a land (once per turn, during main phase, doesn't use the stack).
- Turning a face-down permanent face up (doesn't use the stack).
- Paying a special cost (e.g., suspending, morphing).

---

## 17. Engine-Specific Implementation Notes

These rules apply to implementing cards in the SilverquiLLM engine:

1. **Zone transitions**: Always use the engine's `move_to_zone()` API. Never directly manipulate zone lists.
2. **Triggered abilities**: Register triggers via the engine's event system. The engine handles stacking order.
3. **Replacement effects**: Implement as hooks that intercept the relevant event before it completes.
4. **Targeting**: Always validate targets both at declaration and resolution time.
5. **Timestamps**: The engine auto-assigns timestamps on ETB. Rely on the engine's layer system for continuous effects.
6. **SBAs**: The engine checks SBAs automatically. Card implementations should NOT manually check SBAs.
7. **Damage**: Use the engine's `deal_damage()` method which handles lifelink, deathtouch marking, and prevention in the correct order.

---

*This rulebook covers the rules most relevant to implementing cards in the benchmark.
For corner cases not covered here, refer to the official MTG Comprehensive Rules (CR 2024).*
