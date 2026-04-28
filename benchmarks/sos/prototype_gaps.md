# Prototype Engine Gap Analysis

**Cards selected:** 5

## Plains (trivial)

- **Type:** Basic Land — Plains
- **Mana cost:** 
- **Oracle text:** ({T}: Add {W}.)

## Eager Glyphmage (simple)

- **Type:** Creature — Cat Cleric
- **Mana cost:** {3}{W}
- **Oracle text:** When this creature enters, create a 1/1 white and black Inkling creature token with flying.

## Ajani's Response (medium)

- **Type:** Instant
- **Mana cost:** {4}{W}
- **Oracle text:** This spell costs {3} less to cast if it targets a tapped creature.
Destroy target creature.

## Rancorous Archaic (complex)

- **Type:** Creature — Avatar
- **Mana cost:** {5}
- **Oracle text:** Trample, reach
Converge — This creature enters with a +1/+1 counter on it for each color of mana spent to cast it.

## Ral Zarek, Guest Lecturer (expert)

- **Type:** Legendary Planeswalker — Ral
- **Mana cost:** {1}{B}{B}
- **Oracle text:** +1: Surveil 2.
−1: Any number of target players each discard a card.
−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.
−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.

## Engine Gaps

- Mana color-of-mana-spent tracking missing from engine/mana.py — needed for the Converge mechanic
