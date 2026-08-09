# Key engine decisions

Design decisions of record for the MSH engine, kept out of code comments so
the rationale survives refactors. Card impls and engine modules reference this
file ("per KEY_DECISIONS"). Newest section first.

## replay-gap Phase C — engine primitives (issue #30)

### Generic-counter storage
Non-P/T, non-loyalty counters (e.g. `charge`, `stash`, `oil`) live in a real
backing dict `CardImpl._generic_counters`, **not** in the read-only `counters`
property. The `counters` property is a merged read view (generic dict + the
dedicated `plus_one_counters`/`minus_one_counters` on `Creature`); writing to it
has no effect. All counter mutation goes through `engine.game.add_counter` /
`remove_counter`. Rationale: the old generic branch wrote into
`permanent.counters`, which is a computed property on `Creature`, so
`hasattr(...)` was `True`, the init was skipped, and the write hit a throwaway
dict. A dedicated dict is unambiguous and persists across the `apply_all`
reset cycle (it is not touched by `_reset_characteristics`).

`+1/+1` / `-1/-1` counters persist their `_base_plus_one_counters` /
`_base_minus_one_counters` shadow fields inside `add_counter`/`remove_counter`
themselves, so `apply_all`'s reset-then-reapply no longer erases them. Card
impls must **not** hand-roll `x._base_plus_one_counters = x.plus_one_counters`
(the AST guard does not forbid it, but the grep gate in the phase PR does). The
counter-annihilation SBA also writes the base fields so annihilation survives a
reset.

### Life-payment routing
Life moves only through two sanctioned paths: `game.gain_life` and the new
`game.lose_life`, both of which fire their triggered events
(`GainsLifeTriggeredEvent` / `LosesLifeTriggeredEvent`). Combat/spell damage
keeps firing `LosesLifeTriggeredEvent` from `deal_damage` (damage is not
routed through `lose_life`). Life *payments* as a cost also route through
`lose_life` (paying life is a loss of life and triggers "whenever you lose
life") — though the current card pool has no life-payment cost, so nothing was
converted for that case. Direct `.life` mutation in `cards/` is now rejected by
the AST guard (`test_card_impl_ast_guard.py`, rule (d)).

### Continuous-effect invalidation points and Phase A interplay
`EffectManager.apply_all` re-derives continuous effects at these points:

1. The turn-boundary `cleanup_mechanical` (as before — expires until-EOT
   effects and reapplies the rest).
2. Any battlefield enter/leave via `move_to_zone`. On battlefield *leave*,
   `move_to_zone` first removes every continuous effect the departing card
   sources, so a lord/anthem's buff vanishes immediately (not at next cleanup).
3. Token creation via `create_token` (so anthems buff a new token at once).
4. **Stack resolution** via `engine.stack.resolve_top_of_stack` — the single
   resolution primitive shared by `priority_loop` (normal-game path) and the
   test-suite stack resolver. After a spell/ability resolves it runs SBAs and
   re-derives, so an effect the resolution just *registered* — e.g. Adventuring
   Gear's landfall adding an until-EOT +2/+2 when its trigger resolves — applies
   immediately. This is production behaviour, not a per-test `apply_all`.
5. **Active-player change** in `GameState.advance_phase` — when the turn passes
   to the other player, turn-dependent buffs ("during your turn …", e.g.
   Quick-Draw Katana) are recalculated at the actual transition, not left stale
   from the ending turn's cleanup (which still saw the old active player).

A fast-path skips the re-derive when the effect manager is empty *and* nothing
was just removed — but a removal that empties the manager still runs one reset
pass so the departed buff is stripped. `Equipment.equip`/`detach` always
re-derive (they are infrequent and detach may have emptied the manager).
`apply_all` is idempotent (reset-then-reapply), so re-deriving at any of these
points never double-applies an effect already in the manager.

The replay executor drives the corpus through its own resync (`_safe_apply_all`)
and turn-transition handling, **not** `priority_loop`/`advance_phase`, so points
4–5 are isolated to the normal-game path (and the golden fingerprint, which runs
through the executor, is unchanged).

Phase A interplay: the replay executor's oracle P/T corrections are
`ContinuousEffect`s keyed to the `_ORACLE_PT_SOURCE` sentinel, cleared and
re-derived at each resync; they are sourced by the sentinel, not by any card,
so engine-side `move_to_zone` removal never touches them, and its extra
`apply_all` calls only compose with the executor's reset-then-apply discipline.
`_safe_apply_all` / `_effects_broken` latching is unchanged. All Phase A replay
mechanism tests and the golden-game fingerprint stay green. The executor's
`_remove_synced_card` still does its own per-card effect cleanup on GRE-driven
zone sync (that path bypasses `move_to_zone`), now mirrored by the engine for
the normal game path.

### Activation-time ability targeting
An `ActivatedAbility`/`ActivatedAbilityInstance` may carry an optional
`targeting(game, source, controller) -> list | None` hook. When present,
`activate_ability` runs it **at activation, before the cost is paid** (rule
602.2b/2c) and:
* returns a list of chosen targets → stored on the `StackObject.targets`;
* returns `None` (no legal target) → activation is rejected with `AbilityError`
  and **no cost is spent** (no mana leaves the pool, nothing goes on the stack).

The chosen targets live on the stack object and are passed to the effect at
resolution as `effect(game, targets)` (untargeted abilities keep the historical
`effect(game)` signature). The target is **never re-selected at resolution** —
the effect revalidates the stored target and, if it is no longer legal, resolves
without acting and does not retarget (rule 608.2b/608.2c).

The equip ability is the first user: `Equipment._make_equip_ability` supplies a
`targeting` that offers the controller's creatures (`_legal_equip_targets`) and
an `effect(game, targets)` that revalidates via `_is_legal_equip_target` before
attaching. So a new creature that appears after activation can never become the
target, a target that leaves before resolution yields no attach, and equipping
with zero legal creatures spends nothing. The replay executor's ability bridge
threads `targeting` through when building the `ActivatedAbilityInstance`, so the
corpus drives the same activation-time selection.

### Equipment departure cleanup and SBA integration
`Equipment(Artifact)` sets a class attribute `is_equipment = True`. Two distinct
departures are handled by two distinct paths:

* **The equipped creature leaves** — the attachment SBA
  (`_sba_aura_unattached`) detaches the Equipment while it stays on the
  battlefield (rule 704.5q). It keeps its `getattr(obj, "is_equipment", False)`
  duck-type (backward-compatible: base `Artifact` doesn't set it) and routes
  through `obj.detach(game)` when available so the buff effects are removed
  (falling back to a bare `attached_to = None` for duck-typed objects).
* **The Equipment itself leaves** (bounce/destroy/exile/blink/replay) —
  `move_to_zone`'s leaving-battlefield block calls `card.detach(game)` for an
  attached Equipment. `detach` removes the buff continuous effects, clears
  `attached_to`, clears the internal `_equip_effect_refs`, and runs the
  `on_detach` hook — **exactly once** (a second detach is a no-op because
  `attached_to` is already `None`). This leaves no stale attachment state in the
  graveyard/hand/exile/stack copy, so the Equipment can be equipped normally
  again after it returns to the battlefield. `move_to_zone` runs `detach` before
  its generic source-effect sweep, which then finds nothing more to remove.

### Cost-hook contract
Two cost hooks on `CardImpl`:
* `cost_reduction(self, game, targets=None)` — the spell's own generic-mana
  self-reduction, now target-aware. `get_cost_reduction` passes the
  already-chosen `chosen_targets` (targets are selected before cost is computed
  in `cast_spell`) via a signature-introspecting shim, so historical
  `cost_reduction(self, game)` overrides keep working untouched.
* `spell_cost_reduction(self, game, spell, caster)` — the reduction a
  *battlefield permanent* grants another spell. `get_cost_reduction` sweeps every
  battlefield permanent's hook and sums the results. Each contribution is
  clamped `>= 0` and the total is clamped to the spell's generic pips (colored
  pips are never reduced — existing clamp semantics preserved).

### Alternative-cost mechanism and selected-cost composition order
`CardImpl.alternative_costs(self, game) -> list[ManaCost]` returns fully
replacing mana costs (rule 118.9). An alternative is a **separate base cost**,
not a reduction of the normal one — the old mis-model squeezed Blasphemous
Edict's `{B}` into the generic-only reduction hook and produced `{B}{B}`.

`cast_spell` composes the cost in this order (rule 601.2f):

1. **Enumerate base costs** — `[card.mana_cost, *card.alternative_costs(game)]`.
2. **Apply reductions to each base cost afterward**, clamped to *that* cost's
   own generic component (`min(raw_reduction, base.generic)`) so colored pips
   are never touched. `_raw_cost_reduction` returns the unclamped self +
   battlefield total; `get_cost_reduction` keeps its public contract (clamped to
   the *normal* cost's generic) for the reduction-query tests.
3. **Keep only payable candidates** — a candidate whose reduced form the player
   cannot pay is never offered (`_choose_cost`). If none is payable, `cast_spell`
   rolls the card back to hand and raises `CastingError: insufficient mana`.
4. **Choose** among the payable candidates: a Player Query fires only when more
   than one is payable; the option indices are the *base* indices (0 = normal,
   1+ = alternatives) so a recorded choice ("the alternative", index 1) maps
   unambiguously even after unpayable candidates are filtered out. The chosen,
   already-reduced cost is paid.

So the choice is made among legal payable costs first and reductions are applied
to the selected cost afterward — never offering an unpayable cost, and never
reducing a colored pip. Ordinary spells (no alternatives, one payable cost)
raise no extra query.

### Token-identity hook shape
`create_token(game, player, token=None, *, factory=None, count=1, grp_id=None)`
consults `CreateTokenReplacementEvent` (token doublers are now live), then mints
`count` tokens. Each token gets `is_token`, owner/controller, and a stable
`_grp_id` attachment point (default `None`) that the upcoming token-correlation
phase will stamp with the GRE grpId — no name reverse-lookup. Callers may pass a
pre-built `token` (extra copies are cloned with fresh identity via
`_clone_token`) or a `factory` that mints fresh tokens (preferred when the count
may be multiplied, since every token needs a distinct object). `create_token`
returns the list of placed tokens. The token-correlation itself is out of scope
for this phase.
