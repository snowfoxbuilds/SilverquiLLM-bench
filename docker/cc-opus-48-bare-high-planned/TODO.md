# TODO — Implement SOS cards 1, 4, 13, 57, 97, 120, 201, 226, 245, 257

This is a prepared execution plan. It tells you **what to build first**, gives
**rough guidance on how** (which existing engine seam to reuse, which FDN card
to mirror), and lists the **pitfalls** to avoid. It is a *guide, not a spec* —
`card_spec.json` + `RULEBOOK.txt` are the source of truth. When the real engine
disagrees with a claim here, trust the engine and the spec, fix the code, and jot
a one-line note next to the item. See `CONTEXT.md` for the vocabulary used below.

## Prime directive

One mind builds all ten cards. The goal is **surgical, additive reuse**: build
or learn each shared seam once, then reuse it. The trap on cards like these is
building a **separate general engine subsystem for each single-card mechanic** —
do that six times and you get sprawling, speculative machinery where a handful of
small, focused edits would do, and that machinery tends to drift from what the
cards actually do. Keep changes small and local. Read `## Pitfalls` before you
write any engine code.

## The engine already supports most of this — reuse, don't rebuild

Read the source for exact signatures and docstrings; do **not** trust any spec
doc over the actual `engine/*.py`. These shared seams already exist and cover the
bulk of the ten cards:

| Capability | Existing seam (read the source) | Mirror this FDN card | Reused by |
| --- | --- | --- | --- |
| Cost reduction (generic only) | `CardImpl.cost_reduction(self, game)` hook in `engine/card.py`; called by `get_cost_reduction` in `engine/casting.py` | fdn_57 | sos_1, sos_245 |
| Cast without paying, from any zone | `cast_spell_free(game, player, card, from_zone)` in `engine/casting.py` | fdn_194 (Etali), fdn_161 (Omniscience) | sos_1 (graveyard), sos_13 + sos_120 (exile) |
| Copy a spell on the stack | `copy_spell(game, original, controller, new_targets)` in `engine/stack.py` (resolves via `on_resolve`, fires no cast event — copies are not "cast") | fdn_248 | sos_120, sos_226 |
| Colors / amount of mana spent | `card.colors_spent` set at cast time in `engine/casting.py` (~line 229); deterministic in tests via `mana_pool.pay(cost, choices=...)` | — | sos_4 (colors), sos_57 (amount) |
| Triggered abilities | `register_triggers(self, game)` hook + `TriggerRegistration` / `game.trigger_manager.register(...)` in `engine/triggers.py`; event classes in `engine/events.py` | fdn_235, fdn_81 | most cards |
| Replacement effects (zone redirect) | `register_replacement_effects(self, game)` hook + `ReplacementEffect`; set `MoveToGraveyardReplacementEvent.destination = "exile"` | fdn_244, fdn_137 | sos_1 ("exile instead") |
| Loyalty abilities | `Planeswalker` + `get_loyalty_abilities()` → `LoyaltyAbility(loyalty_cost, effect, description)`; targeting via `self._resolve_target` / `_resolve_targets` (see fdn_81) | fdn_44, fdn_81 | sos_97 |
| Mana abilities | `Land` + `get_mana_abilities()` → `ManaAbility(cost, mana_produced, description)` | (grep fdn lands) | sos_257 |
| Counter target spell | card-local: mirror an FDN counterspell's local `_counter_spell` (pop from stack → graveyard) + `can_cast` guard + `zone=Zone.STACK` targeting | fdn_48 (Refute) | sos_57 |
| Tokens | `create_token(game, player, token)` in `engine/game.py` | fdn_44, fdn_81 | sos_13 |
| Reanimate (graveyard → battlefield) | `move_to_zone(game, card, Zone.GRAVEYARD, Zone.BATTLEFIELD)` (fires ETB automatically) | — | sos_97 (−2) |
| Helpers | `engine/game.py`: `draw_card`, `discard`, `deal_damage`, `exile`, `sacrifice`, `add_counter`, `tap`/`untap` | — | many |

Before adding anything to `engine/`, confirm the seam above doesn't already do
the job. The first question for every clause is **"which FDN card and which
existing hook already does this?"** — not "what new system do I need?".

## Build these three shared engine changes FIRST (small, additive)

Each is reused by more than one card. Build and verify them up front so the cards
that depend on them just register ordinary triggers/hooks. Keep each tiny; run
`python3 -m pytest engine_tests/ -q` after each.

- **E1 — Fire `SpellCastTriggeredEvent`.** It is defined in `engine/events.py`
  (fields: `spell`, `card`, `controller`) but **never fired**. Fire it inside
  `cast_spell` (`engine/casting.py`) right after the spell is pushed to the stack,
  populating `spell=<the StackObject>`, `card`, and `controller`. Copies made by
  `copy_spell` do **not** go through `cast_spell`, so they correctly do not
  re-fire it. *Reused by:* sos_226 (Casualty), sos_257 (animated pump).
- **E2 — Add `BeginningOfPrecombatMainTriggeredEvent`.** No event fires at any
  main phase today. Add the event class to `engine/events.py` (model it on the
  fieldless `BeginningOfUpkeepTriggeredEvent`) and fire it from
  `GameState.advance_phase` (`engine/game_state.py`) — the single chokepoint every
  phase transition passes through — when the new phase becomes `PRECOMBAT_MAIN`,
  right **after** `empty_mana_pools()` so anything a handler adds to the pool
  survives into the main phase. Firing it here (not in `engine/turn.py`) makes it
  behave identically whether a turn is run normally or the state is advanced
  directly; a handler fired only from the turn loop would be skipped on a direct
  advance. Handlers identify "your main phase" by checking the active player.
  (Contrast E1, which belongs in `cast_spell` because casting always flows through
  that path.) *Reused by:* sos_57 (next main phase, once), sos_120 (each of your
  first main phases, recurring).
- **E3 — Aggregate cost reduction from the battlefield.** `get_cost_reduction`
  (`engine/casting.py`) only calls the spell's own `cost_reduction` hook. Extend
  it to also add reductions contributed by the caster's battlefield permanents:
  for each permanent exposing `spell_cost_reduction(self, game, spell) -> int`,
  add it when the spell being cast is an instant/sorcery. Clamp as today
  (generic-only, ≥ 0). *Reused by:* sos_245 (grants affinity to your spells); any
  future "your spells cost less" card. (sos_1 / sos_245 self-reduction still use
  the normal `cost_reduction` hook.)

## Per-card gaps — keep them CARD-LOCAL

The remaining mechanics each serve **exactly one card**. Implement each as the
smallest local change in that card's `card_impl.py` (plus the tiny additive
engine edit noted), and add a one-line comment on any deliberate limitation. Do
**not** generalize these into engine subsystems. Specifics live in the per-card
items below: Miracle (sos_201), the split/back-face (sos_13), the restricted-mana
tag + land animation (sos_257), and coin-flips / skip-turns / surveil (sos_97).

## Build order

Work the items **in order, one at a time**. Items E1–E3 are the shared engine
changes above; the card items follow in dependency order (shared seams first,
then the cards that reuse them; simplest → hardest). For every card: read its
`card_spec.json`, enumerate each oracle clause and its edges, mirror the nearest
FDN card, reuse the named seam, write 2–5 real-engine tests through `test_utils`,
then run `python3 -m pytest engine_tests/ -q` before moving on.

- [ ] **E1 — Fire `SpellCastTriggeredEvent` in `cast_spell`** (see above). Verify
  with a probe trigger that casting an instant fires it once with the right
  `controller` and `spell`.
- [ ] **E2 — Add + fire `BeginningOfPrecombatMainTriggeredEvent`** from
  `GameState.advance_phase`, after `empty_mana_pools()` (see above). Verify a
  registered trigger fires — and any mana it adds persists — when the state is
  advanced directly to the active player's precombat main.
- [ ] **E3 — Battlefield cost-reduction aggregation in `get_cost_reduction`**
  (see above). Verify a permanent exposing `spell_cost_reduction` reduces an
  instant's generic cost, clamped at 0.

- [ ] **sos_4 — Together as One** *(warm-up: mana-spent, pure resolve)*
  - Clauses: Converge — X = number of colors of mana spent; target player draws
    X, deal X damage to any target, you gain X life.
  - Reuse: read `card.colors_spent` in `on_resolve`; `X = len(set(colors_spent))`.
    `draw_card`, `deal_damage`; set life directly. Targets via
    `get_targets`/`self.chosen_targets`.
  - Edges: X = 0 (colorless cast) → draws/deals/gains 0; "any target" is a player
    or creature. Tests set colors deterministically via `mana_pool.pay(choices=)`.

- [ ] **sos_1 — The Dawning Archaic** *(cost reduction + free cast + trigger + replacement)*
  - Clauses: costs {1} less per instant/sorcery in your graveyard; Reach; on
    attack, may cast target instant/sorcery from graveyard for free; if that
    spell would go to the graveyard, exile it instead.
  - Reuse: `cost_reduction` hook (count instant/sorcery in your graveyard);
    `Keyword` for Reach; `register_triggers` on `AttacksTriggeredEvent`;
    `cast_spell_free(game, controller, spell, Zone.GRAVEYARD)`; for exile-instead,
    register a `ReplacementEffect` that sets the spell's
    `MoveToGraveyardReplacementEvent.destination = "exile"`.
  - Edges: empty graveyard (no reduction; "may" trigger with no legal target);
    reduction is generic-only and clamps at 0.

- [ ] **sos_245 — Witherbloom, the Balancer** *(uses E3; affinity self + grant)*
  - Clauses: Affinity for creatures (costs {1} less per creature you control);
    Flying, Deathtouch; your instant/sorcery spells also have affinity for creatures.
  - Reuse: `cost_reduction` hook for its OWN affinity (count creatures you
    control); `Keyword.FLYING | DEATHTOUCH`. For the grant, expose
    `spell_cost_reduction(self, game, spell)` returning your creature count — E3
    aggregates it into other spells' costs. No per-spell edits.
  - Edges: 0 creatures (no reduction); generic-only.

- [ ] **sos_226 — Silverquill, the Disputant** *(uses E1; spell copy + casualty)*
  - Clauses: Flying, Vigilance; your instant/sorcery spells have Casualty 1.
  - Reuse: `register_triggers` on `SpellCastTriggeredEvent` (now fired by E1),
    gated to instant/sorcery spells you cast while Silverquill is on the
    battlefield. On trigger, you **may** sacrifice a creature with power ≥ 1
    (`sacrifice`); if you do, `copy_spell(game, event.spell, controller)` (the
    copy goes on the stack above the original and may choose new targets).
  - Edges: no creature with power ≥ 1 → casualty simply not taken; the copy is
    not itself "cast" (E1 won't re-fire for it — correct).

- [ ] **sos_257 — Great Hall of the Biblioplex** *(uses E1; land: mana + restriction + animation)*
  - Clauses: {T}: add {C}; {T}, pay 1 life: add one mana of any color usable only
    to cast an instant/sorcery; {5}: if not already a creature, becomes a 2/4
    Wizard (still a land) with "whenever you cast an instant/sorcery, +1/+0 until EOT".
  - Reuse: `Land` + `get_mana_abilities()` for the two mana abilities. The `{5}`
    animation is an **activated** ability — expose it via
    `get_activated_abilities(self)` (the engine calls this hook with no arguments
    and addresses abilities by printed index; do not add parameters to it). Read
    any state it needs from `self` — gate the animation on
    `CardType.CREATURE not in self.card_types` — not from a hook argument.
    `SpellCastTriggeredEvent` (E1) drives the animated pump.
    **Restricted mana (gap):** add a lightweight restriction marker
    to mana in the pool and honor it at payment time so that mana can only pay for
    instant/sorcery spells (small additive change in `engine/mana.py`).
    **Animation (gap):** mutate in place — add the Creature type, base P/T 2/4, the
    Wizard subtype, and register the pump trigger; it stays a land. Do not make a
    new permanent.
  - Edges: animate only if not already a creature; the land has been on the
    battlefield, so no summoning sickness concern for the {5} clause; pump stacks
    per spell and resets end of turn; restricted mana cannot pay for a creature.

- [ ] **sos_57 — Mana Sculpt** *(counter via fdn_48; uses E2)*
  - Clauses: counter target spell; if you control a Wizard, at the beginning of
    your next main phase add {C} equal to the mana spent to cast that spell.
  - Reuse: mirror **fdn_48 (Refute)** for the counter (local `_counter_spell`,
    `can_cast` guard, `zone=Zone.STACK` target). Record the countered spell's
    mana **spent** (amount, not mana value). Delayed mana: register a trigger on
    `BeginningOfPrecombatMainTriggeredEvent` (E2) stamped with the cast turn;
    when it next fires for you, if you control a Wizard add that much {C}, then
    unregister (one-shot).
  - Edges: no Wizard → no delayed mana; "mana spent" is the amount actually paid.

- [ ] **sos_120 — Improvisation Capstone** *(cast-from-exile + copy; uses E2 for Paradigm)*
  - Clauses: exile from top of library until total mana value ≥ 4; may cast any
    number of them for free; Paradigm (after it first resolves, exile it; then at
    the beginning of each of your first main phases, may cast a copy from exile
    for free).
  - Reuse: library top access to peel cards (`library.top(n)`; top = last index);
    `cast_spell_free(..., Zone.EXILE)`; `copy_spell` for the Paradigm copy.
    Paradigm: on resolve exile the Capstone, then register a recurring trigger on
    `BeginningOfPrecombatMainTriggeredEvent` (E2) for your first main phase.
  - Edges: library runs out before MV 4; non-castable exiled cards (lands) stay
    exiled; "first main phase" = precombat main, recurring.

- [ ] **sos_13 — Emeritus of Truce // Swords to Plowshares** *(uses cast-from-exile; token + prepared)*
  - Clauses: ETB — target player creates a 1/1 white-black Inkling with flying;
    then if an opponent controls more creatures than you, this becomes prepared;
    while prepared you may cast a copy of its spell (Swords to Plowshares),
    which unprepares it.
  - Reuse: one Creature class `EmeritusOfTruceSwordsToPlowshares` (3/3 Cat Cleric)
    + a `SwordsToPlowshares(Instant)` **helper class in the same file** (exile
    target creature; its controller gains life = its power). `register_triggers`
    on `EntersBattlefieldTriggeredEvent`; `create_token`. When prepared and the
    player elects: create an **actual copy** of the Swords instant, put it in
    exile, and **cast it from exile** via `cast_spell_free(..., Zone.EXILE)`, then
    unprepare. (Per the rulebook the prepared spell is a real Swords copy castable
    from exile — confirm cost semantics in `RULEBOOK.txt`.)
  - Edges: opponent does NOT control more creatures → not prepared; Swords on an
    empty board (no legal target).

- [ ] **sos_201 — Lorehold, the Historian** *(miracle card-local via draw event; upkeep loot)*
  - Clauses: Flying, Haste; instant/sorcery cards in your hand have miracle {2};
    at the beginning of each opponent's upkeep, you may discard a card to draw one.
  - Reuse: `Keyword.FLYING | HASTE`; `register_triggers` on
    `BeginningOfUpkeepTriggeredEvent` gated to an opponent's upkeep; `discard` +
    `draw_card`. **Miracle (gap, card-local):** register on
    `DrawsCardTriggeredEvent` (already fired by `draw_card`), gated to your
    **first draw this turn** (track with a turn-stamped flag) AND drawn card is
    instant/sorcery; then you may cast it for the miracle cost by deducting {2}
    and using the free-cast stack path. Continuous effects do not reach the hand,
    so do not try to tag hand cards.
  - Edges: not the first card drawn this turn → no miracle; loot is optional;
    empty hand.

- [ ] **sos_97 — Ral Zarek, Guest Lecturer** *(planeswalker; surveil / reanimate / coin-flip / skip-turns)*
  - Clauses: starting loyalty 3; +1 Surveil 2; −1 any number of target players
    each discard a card; −2 return a creature card with mana value ≤ 3 from your
    graveyard to the battlefield; −7 flip five coins, target opponent skips their
    next X turns (X = heads).
  - Reuse: `Planeswalker` + `get_loyalty_abilities()` (mirror **fdn_81 / fdn_44**;
    targeting via `self._resolve_target` / `_resolve_targets`). −2 reanimate via
    `move_to_zone(game, card, Zone.GRAVEYARD, Zone.BATTLEFIELD)` (fires ETB). +1
    Surveil 2: look at `library.top(2)`, bin to graveyard or keep on top (small
    local helper; player choice in tests). **Coin flip (gap):** flip each coin
    with `random.Random.randint(0, 1)` via a seeded RNG — add a `game.rng`
    (`random.Random`) if absent so tests are deterministic. **Skip turns
    (gap):** add a small skip-turn counter on game state checked by the turn loop
    (`engine/game_state.py` advance logic); X heads → skip that player's next X
    turns.
  - Edges: −2 with no valid creature in graveyard; −1 with zero target players;
    ultimate only at loyalty ≥ 7; X = 0 heads skips nothing.

## Pitfalls (read before writing engine code)

1. **A new subsystem for a one-card mechanic is the trap.** It is tempting to
   build generic miracle/casualty/affinity/paradigm/animation/preparation systems
   — but each here serves exactly one card, and that path balloons into sprawling,
   speculative machinery that drifts from the cards' real behavior. The only
   shared engine changes worth making are E1–E3 above (each reused by ≥ 2 cards).
   If you're adding a manager, framework, or registry for something only one card
   uses, stop and make it card-local instead.
2. **Your own green tests are not proof.** Tests you write can encode the same
   misreading as your code — passing them only proves the code matches your
   reading, not the card. After each card, re-derive the behavior from
   `card_spec.json` + `RULEBOOK.txt` and run a short **throwaway** smoke check
   through `test_utils` that you did *not* write a test for — assert the
   spec-observable result (zones, life, P/T, counters, exile vs graveyard).
3. **Test through the real engine, never a stand-in.** Drive behavior via
   `test_utils` (`create_game`, `set_board_state`, `cast_spell`, `advance_to_phase`,
   `declare_attackers`, `declare_blockers`; for abilities, `ActivateAbility(card, index)`
   resolved through `priority_loop` and scripted with `DeterministicPlayer`).
   Abilities are addressed by printed index, the same way the engine activates them.
   Do not hand-build internal events, call a card's `get_*_abilities()` or
   `on_resolve` directly, pop the stack, or script a player's internal queue —
   those pass while the real path is broken.
4. **Reuse before you add.** For every clause, name the FDN card and existing hook
   that already does it before writing anything new. The seam table is the
   starting point; the FDN library is the rest.
5. **Additive-only, and keep `engine_tests/` green.** Add/extend in `engine/`; never
   rename/move/delete existing symbols — other modules import them by name, so a
   rename or move breaks those imports. Run `python3 -m pytest engine_tests/ -q`
   after every card and every engine change; never ship a regression.
6. **Stay in the assigned file.** Each card's class lives in its own
   `cards/sos/sos_<N>/card_impl.py`; do not move or rename card directories. Do not
   edit `engine_tests/` or any `cards/fdn/*/tests.py`.
