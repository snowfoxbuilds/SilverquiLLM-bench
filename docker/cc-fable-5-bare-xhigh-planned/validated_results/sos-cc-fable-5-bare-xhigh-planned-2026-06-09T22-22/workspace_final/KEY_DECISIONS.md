# KEY_DECISIONS

Lightweight log of ambiguities, deviations, and deliberate card-local limitations.

- **E1 (SpellCastTriggeredEvent)**: Fired only from `cast_spell` (the normal
  cast path), NOT from `cast_spell_free`. The plan scopes E1 to `cast_spell`;
  copies via `copy_spell` and free casts from exile/graveyard do not re-fire it.
  Deliberate: keeps free-cast cards (sos_1/13/120) from incidentally triggering
  casualty etc. Event populated with spell=StackObject, card, controller, player.

- **sos_1 (Dawning Archaic) — attack trigger**: `AttacksTriggeredEvent` was
  defined but never fired by combat. Added firing it in
  `declare_attackers_step` (engine/combat.py), per declared attacker, setting
  both `creature` and `attacker`. Additive; engine_tests stay green. Also
  enlivens fdn_194 (Etali) whose trigger was previously dead.
- **sos_1 — "exile instead of graveyard"**: A spell's stack→graveyard move is
  not routed through the replacement system by `_resolve_spell`, so the plan's
  suggested `MoveToGraveyardReplacementEvent` redirect cannot fire. Implemented
  card-local by wrapping the free-cast spell's `on_resolve` to exile it after it
  lands in the graveyard. LIMITATION: a countered free-cast copy is not
  redirected (only the resolve path).

- **sos_257 (Great Hall) — restricted mana**: Added `_restricted` tracking to
  `ManaPool` and a `for_instant_or_sorcery` param to `can_pay`/`pay` (default
  True = backward compatible). `cast_spell` passes the spell's instant/sorcery
  flag; the {5} activation pays with the flag False so restricted mana can't
  fund a non-spell cost.
- **sos_257 — end-step pump reset**: `EndStepTriggeredEvent` was defined but
  never fired. Added firing it at (ENDING, END) in `run_turn` (also enlivens
  fdn_81's token sacrifice). The animated land registers a reset trigger on it.
- **sos_257 — animation**: Mutate the Land in place (add CREATURE type, Wizard
  subtype, plain 2/4 P/T attrs, pump bonus). Snapshot `_original_card_types` is
  rebaked to include CREATURE so cleanup's `_reset_characteristics` does not
  de-animate it (animation is permanent, not until-EOT). Card-local; no new
  permanent. Reset-test fires the genuine EndStepTriggeredEvent the same way
  turn.py does, then drains the stack.

- **sos_57 (Mana Sculpt)**: Added `card.mana_spent = effective_cost.cmc` in
  cast_spell (amount actually paid, after reductions) so the counter can refund
  it. Delayed mana uses a one-shot trigger on BeginningOfPrecombatMain (E2) with
  no turn-stamp needed — the current turn's event already fired, so the next
  firing is genuinely "your next main phase". Wizard control checked at delayed
  resolution. LIMITATION: "next main phase" approximated as next precombat main
  (postcombat-main-as-next is not modeled, since E2 only covers precombat main).

- **sos_120 (Improvisation Capstone)**: Paradigm "exile this spell" handled by
  exiling self from the stack inside on_resolve (so _resolve_spell's
  stack→graveyard move is a no-op). Recurring trigger on BeginningOfPrecombatMain
  (E2) casts a "copy" — a duplicate StackObject flagged `_is_paradigm_copy` that
  runs only the improvisation effect (no re-exile/re-register); original stays
  in exile. "first main phase" = precombat main, recurring.

- **sos_13 (Emeritus // Swords)**: Self-ETB triggers do NOT fire via
  EntersBattlefieldTriggeredEvent in this engine (move_to_zone fires ETB before
  register_triggers — verified with fdn_14). So the ETB effect runs inside
  register_triggers (invoked once on entry, with self already on the
  battlefield, so it is counted among your creatures). DEVIATION FROM PLAN: the
  prepared copy is cast paying its {W} cost (rule 722.3c: "may cast the copy" =
  normal cast), NOT via free-cast — the plan suggested cast_spell_free(free), but
  the rulebook is the source of truth. Copy is created in exile on becoming
  prepared (722.3c); casting it unprepares the permanent.

- **sos_201 (Lorehold)**: `cards_drawn_this_turn` is never reset by the engine,
  so miracle "first draw this turn" is tracked card-local via a turn-stamp
  (`_miracle_turn`), stamped on every controller draw regardless of card type so
  later draws aren't "first". Miracle cast = pay {2} then free-cast from hand.
  Loot/miracle triggers registered in register_triggers (real ETB path); loot
  test fires the genuine BeginningOfUpkeep event as turn.py does.

- **sos_97 (Ral Zarek)**: Loyalty abilities mirror fdn_81/fdn_44 (read
  pw._resolve_target/_resolve_targets, set by tests). Coin flips use a lazily
  created game.rng (random.Random) — card-local, deterministic via injectable
  rng. Skip-turns: added GameState._skip_turns dict honored in advance_phase's
  turn-wrap — a skipped player's turn passes to the other player and the
  normal-rotation pointer is NOT advanced (so the skipped player is next after).
  Applied to the normal-rotation branch only (extra_turns left intact).
