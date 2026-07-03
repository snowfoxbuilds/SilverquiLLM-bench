# Key decisions log

- **sos_97 (skip turns):** `GameState.skip_turns` is a dict of seat index →
  pending skip count consumed in `advance_phase`'s end-of-turn wrap: when a
  player with pending skips would begin a turn, one skip is consumed and the
  turn passes to whoever is next (extra-turn queue first, then normal
  rotation). Skipped turns don't increment `turn_number`.
- **sos_97 (coin flips):** `game.rng` (a `random.Random`) is created lazily by
  the −7 effect if absent; tests seed it for determinism. Heads = 1.
- **sos_97 (surveil order):** Kept cards stay on top in their original order —
  "the rest back on top in any order" makes any deterministic order a legal
  choice.

- **E1:** TODO named only `cast_spell`, but `SpellCastTriggeredEvent` is also
  fired from `cast_spell_free` — casting without paying the mana cost is still
  casting (rule 601), so cast triggers (e.g. Casualty, sos_257's pump) must see
  free casts. Copies via `copy_spell` still bypass it (copies are not cast).
- **sos_1 (engine):** `AttacksTriggeredEvent` existed but was never fired
  anywhere; added a fire in `declare_attackers_step` (rule 508.1g) — minimal
  additive edit, required for any attack trigger to work via the real path.
- **sos_257 (restricted mana):** ManaPool gained a separate
  `_restricted_pool` plus `add_restricted`/`get_restricted` and an additive
  `allow_restricted` kwarg on `can_pay`/`pay`; `cast_spell` passes
  `allow_restricted=True` only for instant/sorcery casts. Restricted mana is
  spent before normal mana of the same type. "Instant/sorcery-only" is the
  only restriction shape supported (commented in mana.py).
- **sos_257 (animation):** P/T are properties that raise `AttributeError`
  until animated — the zero-toughness SBA keys on `hasattr(obj, "toughness")`,
  so a pre-animation land must not expose toughness 0. Animation mutates in
  place and refreshes `_original_card_types` so `apply_all` resets don't strip
  the creature type. Animated land is not summoning sick (per plan). The pump
  trigger is registered on entry but gated on the animated state.
- **sos_57 (Wizard timing):** Oracle reads "If you control a Wizard, add …
  at the beginning of your next main phase" — the condition gates *creating*
  the delayed ability, so it's checked when Mana Sculpt resolves (TODO sketched
  checking at fire time). A Wizard dying before the main phase doesn't cancel
  the mana.
- **sos_57 ("next main phase"):** Only precombat mains fire an event (E2), so
  "your next main phase" resolves to your next *precombat* main. Countering
  during your own precombat main defers the mana to next turn — accepted
  limitation, matches the plan's E2 scope.
- **sos_57 (amount spent):** Added `ManaPool.last_payment_amount` and stamped
  `card.mana_spent` in `cast_spell` (the seam table's "amount of mana spent"
  column had no existing implementation). Free casts leave it absent → 0.
- **sos_120 (Paradigm copy):** TODO pointed at `copy_spell`, but that copies a
  StackObject — the Capstone sits in exile with no stack object. Used
  `copy.copy` of the card, placed in exile, cast via
  `cast_spell_free(..., Zone.EXILE)`. The copy inherits
  `_paradigm_registered=True` so it never re-registers the trigger, and the
  resolved copy is removed from its landing zone (rule 707.10a — a copy
  ceases to exist). Self-exile works by moving stack→exile during
  `on_resolve`; the engine's later stack→graveyard move no-ops safely.
- **sos_13 (prepared):** Rule 722 (Preparation Cards) is in RULEBOOK.txt.
  Implemented per 722.3c: the Swords copy is created in exile when the
  creature becomes prepared (not lazily at cast time), it ceases to exist if
  the creature leaves the battlefield while prepared, and casting it *pays*
  {W} (TODO sketched a free cast; the rulebook has no free-cast wording —
  mana is paid in the activated-ability cost step, then the spell goes
  through `cast_spell_free` purely as the cast-from-exile stack path).
  Election is exposed via `get_activated_abilities()[0]` — the only
  index-addressable driver the engine offers.
- **sos_13 (ETB):** Self-ETB triggers never fire in this engine (event is
  fired before the entering card registers its triggers — asserted by
  engine_tests). The ETB ability therefore runs in `on_resolve`, matching
  fdn_205, the reference ETB-creature that ships with tests.
- **sos_1 (exile instead):** TODO suggested a `ReplacementEffect` setting
  `destination="exile"`, but `move_to_zone` only consults replacements when a
  card leaves the battlefield, and `_resolve_spell` passes no replacement event
  for stack→graveyard. Implemented card-locally by wrapping the free-cast
  spell's StackObject `on_resolve` to redirect graveyard→exile after
  resolution. Limitation (commented): a counter that bins the spell directly
  bypasses the redirect.
