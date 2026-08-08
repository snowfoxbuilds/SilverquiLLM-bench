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

### `apply_all` trigger points and Phase A interplay
`EffectManager.apply_all` re-derives continuous effects at three points now:
the turn-boundary `cleanup_mechanical` (as before), **and** on any
battlefield enter/leave via `move_to_zone`, **and** at token creation via
`create_token`. On battlefield *leave*, `move_to_zone` first removes every
continuous effect the departing card sources, so a lord/anthem's buff vanishes
immediately (not at next cleanup). A fast-path skips the re-derive when the
effect manager is empty *and* nothing was just removed — but a removal that
empties the manager still runs one reset pass so the departed buff is stripped.
`Equipment.equip`/`detach` always re-derive (they are infrequent and detach may
have emptied the manager).

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

### Equipment SBA integration
`Equipment(Artifact)` sets a class attribute `is_equipment = True`. The
attachment SBA keeps its `getattr(obj, "is_equipment", False)` duck-type
(backward-compatible: base `Artifact` doesn't set it, the new class does) rather
than an `isinstance` check. The equipment branch now unattaches when the
equipped creature has left the battlefield (rule 704.5q) or the attachment is
illegal by protection, and it routes through `obj.detach(game)` when available
so the buff continuous effects are removed (falling back to a bare
`attached_to = None` for duck-typed objects).

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

### Alternative-cost mechanism
`CardImpl.alternative_costs(self, game) -> list[ManaCost]` returns fully
replacing mana costs (rule 118.9). When non-empty, `cast_spell` offers the
caster a Player Query (`_choose_cost`) between the normal (reduced) cost and the
alternatives; the chosen cost replaces the mana cost outright. This keeps
alternative costs (Blasphemous Edict's `{B}`) separate from reductions, which
can only touch generic mana — the old mis-model squeezed `{B}` into the
generic-only reduction hook and produced `{B}{B}`. The query fires only when an
alternative is actually available, so ordinary spells raise no extra query.

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
