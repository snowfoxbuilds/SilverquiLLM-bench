# Key engine decisions

Design decisions of record for the MSH engine, kept out of code comments so
the rationale survives refactors. Card impls and engine modules reference this
file ("per KEY_DECISIONS"). Newest section first.

## replay-gap Phase F correction — zone-change epoch (issue #37 follow-up)

### `GameRefsRegistry.zone_epoch` — a side-effect-free real-transition signal
The refs registry keeps a monotonic per-object **zone-change epoch**
(`zone_epoch(obj)`), advanced by `note_zone_change` — i.e. by every real
`move_to_zone` transition, including stints no query ever observes (a
flicker's exile leg). Two equal reads bracket a window containing NO real zone
transition; an increased value proves at least one occurred **even when the
object is back in its original zone** (an atomic leave-and-return completed
between the reads). The read is pure: it never mints instance ids and never
perturbs the query-facing id sequence — unlike `instance_id`, whose call IS an
observation and mints a stint id as a side effect (measured to perturb replay
simulations when used for state inspection). The epoch is keyed by `id(obj)`;
the registry retains a reference on the first zone change so the key is never
reused by a recycled object. Consumer of record: the replay executor's counter
reconciliation, which identifies a battlefield stint as (engine-object key,
fold-time epoch) and, since correction part 3, also accumulates per-pendency
epoch evidence to prove (or refute) same-stint continuity across GRE
instance-id churn — since part 5, a deferred fold's baseline is the engine
battlefield CENSUS of epochs frozen on the pass GRE first attests the
effect's identity on the battlefield (the window start): two equal epoch
reads prove continuity only for the interval they bracket, so the first read
must date from the window start, not merely from some pass before the fold —
see root `KEY_DECISIONS.md` Phase F correction parts 2–5.

**`object_id` uniqueness caveat** (surfaced by part 3's epoch evidence): the
`GameObject.object_id` counter guarantees uniqueness only for CONSTRUCTED
objects. Copy-token impls (fdn_154, fdn_163) mint their token via
`copy.copy(<copied card>)`, which skips `__init__`, so the token copy shares
its original's `object_id` while both are live on the battlefield —
`_place_token`'s multiplication clones re-mint (`game.py`), the initially
supplied copy object does not. Consumers needing identity among LIVE objects
must therefore not key by bare `object_id` (the replay executor keys counters
by `(object_id, id(obj))` with pinned references). Re-minting inside the
impls or `_place_token` was deliberately NOT done as part of the replay
correction: `object_id` feeds per-object ability keying (`abilities.py`), so
changing it would alter shared-ability-state semantics for copies — an engine
change that deserves its own issue, not a side effect of a replay-layer fix. —
Rejected: exposing stint identity via `instance_id` (minting side effect);
storing the epoch as an attribute on game objects (collides with card-impl
attribute space and the AST guard's write rules); a battlefield-departure-only
counter in `move_to_zone` (the generic zone-change epoch is strictly more
informative and needs no zone-specific branching — any move by an object that
was on the battlefield necessarily begins with a battlefield departure).

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
4. **Stack resolution** via `engine.stack.resolve_top_of_stack` — the single,
   canonical normal-game resolution primitive (see the next section for the
   exact order). An effect the resolution just *registered* — e.g. Adventuring
   Gear's landfall adding an until-EOT +2/+2 when its trigger resolves — applies
   immediately. This is production behaviour, not a per-test `apply_all`.
5. **Active-player change** in `GameState.advance_phase` — when the turn passes
   to the other player, turn-dependent buffs ("during your turn …", e.g.
   Quick-Draw Katana) are recalculated at the actual transition, not left stale
   from the ending turn's cleanup (which still saw the old active player).

At points 2, 3, and 5 a fast-path skips the re-derive when the effect manager is
empty *and* nothing was just removed — but a removal that empties the manager
still runs one reset pass so the departed buff is stripped. **Point 4 (stack
resolution) never uses this fast-path**: it re-derives unconditionally, because a
resolution may remove the *last* active effect and a skipped reset would leave
that departed buff baked into a permanent's modified characteristics. `len()`
alone is therefore never used to decide the post-resolution recalculation.
`Equipment.equip`/`detach` always re-derive (they are infrequent and detach may
have emptied the manager). `apply_all` is idempotent (reset-then-reapply), so
re-deriving at any of these points never double-applies an effect already in the
manager.

### Canonical resolution order: resolve → re-derive → SBA
`engine.stack.resolve_top_of_stack` is the one normal-game resolution primitive,
shared by `priority_loop` (normal-game path), the test-suite stack resolver, and
`engine.casting.resolve_top` (a thin delegating alias — see below). It settles in
this order (`settle_after_resolution`):

1. Pop and resolve exactly one stack object.
2. **Re-derive continuous effects immediately** (`apply_all`) — always, with no
   `len()` fast-path, so the last-effect-removed case still resets the permanent.
3. **Run state-based actions to stability**, re-deriving *before* the first SBA
   check and *again after* every SBA pass that changes the board. SBAs therefore
   never inspect pre-recalculation characteristics, and any battlefield change an
   SBA causes leaves continuous characteristics current before priority returns.

Consequences validated by tests: a 2/2 with two marked damage *survives* a
resolving +2/+2 (re-derive → 4/4 precedes the lethal-damage check); a resolving
−2/−2 sends a 2/2 to the graveyard *before priority returns* (re-derive → 0/0
precedes the zero-toughness check); and removing the last active effect during
resolution resets the permanent instead of leaving stale modified stats. The
settle loop terminates because SBAs only remove permanents / decrement counters
and re-derivation is deterministic, so the state cannot oscillate.

**`engine.casting.resolve_top` disposition:** kept (it is part of the published
engine import surface — `tests/test_engine_import_surface.py`,
`test_oracle_workspace_bootstrap.py`) but reduced to a thin alias that delegates
to `resolve_top_of_stack`. It previously ran SBAs *without* re-deriving
continuous effects first; that second, divergent settlement implementation is
gone, so every stack-resolution entry point now settles identically.

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

### Activation-time controller authorization, ability targeting, and stint identity
An `ActivatedAbility`/`ActivatedAbilityInstance` may carry two optional hooks:
`can_activate(game, source, controller) -> bool` and
`targeting(game, source, controller) -> list | None`. `_activate_regular_ability`
runs the **authorization → legality → target-query → cost-payment** sequence
(rule 602.2):

0. **Authorization first** — the activating player (the `player` passed to
   `activate_ability`) **is** the ability's controller, and must equal the
   `ActivatedAbilityInstance.controller` declared on the instance. The engine
   does **not** silently substitute the source's current controller: a mismatch
   raises `AbilityError` before any Player Query, cost, source mutation, or
   stack push. The authorized controller — never `source.controller` — is what
   is threaded into `can_activate`, `targeting`, the cost, the
   `ActivationContext`, and the `StackObject`. (Whether that controller may
   *legally* activate this particular ability — e.g. does it actually control
   the source? — is a `can_activate` concern, below.)
1. **Legality (`can_activate`)** — verifies source-zone and timing
   restrictions with *no side effects*, **before any target query is raised or
   any cost is paid**. An illegal-timing (or source-off-battlefield) activation
   therefore raises `AbilityError` immediately: no Player Query, no target intent
   consumed, no mana spent, nothing pushed.
2. **Target selection (`targeting`)** — returns the chosen targets, or `None`
   (no legal target) which rejects the activation before the cost. A `targeting`
   hook on a mana ability is rejected explicitly (mana abilities cannot target,
   rule 605.1a) rather than mis-invoking the effect.
3. **Capture the activation context**, then **pay the cost**, then push.

**Activation context (immutable, on the stack object).** After targets are
chosen, the engine captures an `ActivationContext(controller, source_instance_id,
target_instance_ids)` and stores it on the `StackObject` — never on a mutable
field of the source permanent. `source_instance_id` / `target_instance_ids` are
the *battlefield stint ids* (`GameRefsRegistry.instance_id`) at activation; a
zone change mints a new stint id, so a leave-and-return is a *different* object
even when the same Python instance is reused. Because the context lives on the
stack object, **two activations of the same source coexist on the stack without
clobbering each other**.

**Resolution revalidation (never re-select).** The chosen targets are passed to
the effect as `effect(game, targets, context)` (untargeted abilities keep the
historical `effect(game)` signature). The effect **revalidates against the
context and never retargets** (rule 608.2b/608.2c):
* **Source stint** — the source must still be on the battlefield in the *same*
  stint captured at activation. If it left (even if the same Python object now
  sits in another zone), or left and returned (a new stint), the ability resolves
  without acting and writes no state.
* **Target stint** — likewise for each target; a target that left, or left and
  returned, is treated as gone.
* **Controller-relative legality** — "target creature you control" is evaluated
  against the *ability's* activation-time controller (`context.controller` /
  `StackObject.controller`), **not** the source's possibly-changed current
  controller. Protection is re-checked here too (a target that gained protection
  from the source after activation fails to attach).

**Protection filtering in the equip option set.** Protection filtering is *not*
a generic feature of the activation machinery — it lives in the **equip**
ability. `Equipment._legal_equip_targets` excludes creatures with protection
from the Equipment (the T in DEBT), so a protected creature is never offered as
an equip target in the first place, and the same exclusion is re-checked at
resolution. A future targeted activated ability that must exclude protected
candidates has to filter them in its own `targeting` hook (or the filtering must
first be lifted into the shared machinery).

The equip ability is the first user: `Equipment._make_equip_ability` supplies
`can_activate` (Equipment on the battlefield, **controlled by the activation-time
controller**, and sorcery speed — so another player cannot activate an Equipment
they do not control, and a control change away from the activating player makes
the equip ability unavailable to them), a `targeting` that offers the *ability
controller's* creatures without protection (`_legal_equip_targets(game,
controller)`), and an `effect(game, targets, context)` that runs the
source-stint, target-stint, controller-relative and protection revalidation
(`_on_battlefield_same_stint`, `_is_legal_equip_target_for`) before `equip`. So
no Equipment attaches while off the battlefield, a leave-and-return never lets an
old ability affect the new source or target stint, control changes are judged
against the ability's controller, and equipping with zero legal creatures spends
nothing. The replay executor's ability bridge threads both `targeting` and
`can_activate` when building the `ActivatedAbilityInstance`, so the corpus drives
the same activation-time selection and resolution-time revalidation.

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


## replay-gap Phase D — card-impl sweep (issue #32)

### Optional targets: `TargetRequirement.optional`
`TargetRequirement` gained `optional: bool = False` (`engine/types.py`). A
**required** spec is unchanged — `_query_target` (`engine/casting.py`) keeps the
mandatory `min == 1` query and raises `CastingError` on an empty candidate set
(boundary validation is byte-identical). An **optional** spec ("up to one
target") is declinable: `_query_target` offers the query with `min == 0` (the
player may decline) and, when the candidate set is empty, returns `None`
**without raising** so the spell/ability stays castable. `None` means "no target
for this spec" — the cast loop adds nothing to `chosen_targets`, so an optional
requirement contributes 0 or 1 targets.

- **"Up to N target X" = N optional requirements, targeted at cast** (real
  targeting, not resolve-time picks). The effect reads a `chosen_targets` list of
  length 0..N and must tolerate fewer than N (or zero).
- **Distinctness (rule 601.2c).** `_query_target` takes an `exclude` set — the
  objects already chosen for earlier specs of the same cast — and drops them from
  the option set, so a multi-target spell picks *distinct* objects and the intent
  model cannot re-select the same target on a later spec (an optional spec whose
  only candidate is already taken then declines cleanly). This applies to
  required multi-target specs too (they were previously free to re-offer the same
  object); no existing single-target card is affected (`exclude` is empty for the
  sole spec).
- This makes `fdn_86` Fiery Annihilation castable with zero Equipment on the
  battlefield (its "up to one target" no longer forces a `CastingError`), and
  gives fdn_12 / fdn_177 / fdn_126 / fdn_250 genuinely declinable choices per
  oracle text.

### Loyalty targeting channel
`LoyaltyAbility` (`engine/card.py`) and `LoyaltyAbilityInstance`
(`engine/abilities.py`) gained an optional `targeting` hook, mirroring the Phase
C `ActivatedAbility` contract. `_activate_loyalty_ability` now runs
**authorization → legality (sorcery-speed + once-per-turn) → target selection →
loyalty payment → push**:

- **Authorization** matches the activated-ability gate: the activating player
  must equal `LoyaltyAbilityInstance.controller`, rejected before any query or
  loyalty change.
- **Targeting before payment.** When `targeting` is set it is called with
  `(game, source, controller)` after the legality checks and *before* the loyalty
  cost is paid. `None` → a required target has no legal choice, so the ability
  cannot be activated and **no loyalty is spent**; a list (possibly empty, for
  "up to one target") → activate with those targets. The engine captures the same
  immutable `ActivationContext` (controller + source/target stints) used by
  activated abilities and stores it on the `StackObject`.
- **Resolution.** A targeted loyalty ability's effect is invoked
  `effect(game, targets, context)`; an untargeted one keeps `effect(game)`. The
  effect revalidates against the context exactly as equip does (never re-selects).
- `test_utils.activate_loyalty_ability(game, player, source_card, index)` is the
  test bridge (sibling of `activate_card_ability`), threading the `targeting`
  hook from `get_loyalty_abilities()`.
- **Delta from full mirroring:** none required — the loyalty stack pathway
  already builds a `StackObject`, so threading targets + context + the wrapped
  `on_resolve` was proportional; loyalty abilities have no `can_activate` hook
  (their legality is the fixed sorcery-speed + once-per-turn rule, checked inline).

### Centralized activation-time targeting + resolution revalidation (Phase D correction)
The original Phase D sweep left several cards still **selecting targets at
resolution** (a resolve-time `choose_object`), which violates rule 601.2b/602.2b
(targets are chosen when the spell/ability is put on the stack) and rule
608.2b/608.2c (a resolving effect revalidates, never re-selects). The correction
introduces **one shared mechanism** in `engine/stack.py` and routes every
targeted activated ability, loyalty ability, triggered ability, and converted
spell through it.

**Shared helpers (`engine/stack.py`).** Co-located with `ActivationContext`:
- `capture_activation_context(game, source, controller, targets)` — the single
  capture path (rule 602.2). `abilities.py` and `triggers.py` both call it; the
  private `_capture_activation_context`/`_battlefield_instance_id` copies in
  `abilities.py` were removed. Source stint is the battlefield stint; **target
  stints are zone-generic** (`object_stint_id` finds whichever zone the target
  occupies), so a graveyard-card target (Scavenging Ooze) is captured and
  revalidated by the same code that handles a battlefield permanent.
- `same_stint(game, obj, stint_id)` — `True` iff *obj* is still in the same
  zone-stint captured at activation. A zone change (including leave-and-return)
  mints a new stint id, so a departed-and-returned object fails. A **player** is
  never a zone resident and has stable identity, so `same_stint` short-circuits
  to `True` for players (needed by "any target" damage abilities); the caller's
  predicate still enforces any player-legality restriction.
- `surviving_targets(game, context, targets, is_legal=None)` — the **canonical
  resolution revalidation**. Returns the subset of `targets` that both (a) pass
  `same_stint` and (b) satisfy `is_legal`, a predicate expressing the *complete*
  targeting restriction relative to `context.controller`. Callers apply the
  effect only to the returned list; an empty list means every target was illegal
  and the effect does nothing (rule 608.2c). This is what replaced the ad-hoc
  per-card `if not _on_battlefield(target): return` + `source.controller` checks.

**"You control" uses `context.controller`, never `source.controller`.** Every
targeted activated/loyalty ability that carries a control restriction (fdn_114,
fdn_44, plus Zimone fdn_126) evaluates it against the immutable activation-time
controller from the context, so a control change of the *source* after activation
does not move who "you" is. Cards without a control restriction (fdn_95, fdn_134,
fdn_139, fdn_189, fdn_195, fdn_201, fdn_234) still route through
`surviving_targets` so stint validation (leave-and-return rejection) is uniform.

**Flagship corrections.**
- **Scavenging Ooze (fdn_232)** — `{G}: Exile target card from a graveyard` now
  selects the graveyard card via an `ActivatedAbility.targeting` hook at
  activation (before `{G}` is paid), captures its graveyard stint, and at
  resolution exiles it only if it is still the same graveyard card. A card that
  left the graveyard is not replaced and no other graveyard card can be picked;
  the creature-card reward (`+1/+1` counter, gain 1 life) lands only when the
  originally-captured legal card is exiled — the counter additionally requires
  the source to still be the same battlefield permanent.
- **Zimone (fdn_126)** — the `{G}{U}, {T}` ability targets **up to two distinct**
  creatures/artifacts you control at activation (genuinely optional: 0/1/2), and
  the beginning-of-combat trigger's "up to two target creatures you control" is
  fixed **when the trigger is put on the stack** via the new triggered-target
  channel. Both revalidate through `surviving_targets` with a
  `context.controller`-relative predicate. `get_activated_abilities(self)` keeps
  its fixed self-only signature.
- **Fiery Annihilation (fdn_86)** — see dependent-target casting below.

**Triggered-target channel (`engine/triggers.py`).** `TriggerRegistration`
gained an optional `targeting(game, event, controller) -> list | None` hook. When
set, `fire_event` chooses the trigger's targets **as it is put on the stack**
(rule 603.3d), captures an `ActivationContext`, stores the targets on the
`StackObject`, and invokes `effect(game, targets, context)` at resolution.
Untargeted triggers keep the historical `effect(game)` and build the same bare
`StackObject` as before, so existing triggers are unaffected. This is the
"smallest reusable triggered-target mechanism" Zimone's combat trigger needed.

Two rules refinements on this channel:

- **Controller determined at fire time, consistently across the pipeline (rule
  603.3d/3e).** Each matching trigger's controller is computed **once, before
  APNAP partitioning** — the source's *current* controller, falling back to the
  registration-time controller only if the source no longer has one (a
  leaves-the-battlefield trigger whose source is already gone). That single
  fire-time controller is then used for **everything**: APNAP grouping (so a
  source that changed hands is grouped/ordered as its new controller's), the
  `StackObject.controller` for **both targeted and untargeted** triggers, the
  `controller` passed to `targeting`, and the captured `ActivationContext`. A
  card's `targeting(game, event, controller)` receives that controller explicitly
  rather than reading `source.controller` itself. So Zimone stolen before its
  beginning-of-combat trigger fires targets, orders, and resolves relative to its
  new controller.
- **Controller threaded into untargeted effects.** An untargeted trigger effect
  is invoked `effect(game)` by default, but a *controller-sensitive* one (Thousand-
  Year Storm's "copy it for the controller") declares a second positional
  parameter — `effect(game, controller)` — and is threaded the **immutable**
  fire-time controller (arity-detected by `_effect_wants_controller`). It never
  re-reads `source.controller` at resolution, so a source that changes hands
  again between fire and resolution does not shift "you". Every pre-existing
  untargeted effect is one-argument, so this is backward-compatible.
- **Per-fire captured state (`capture` channel).** `TriggerRegistration` has an
  optional `capture(game, event, controller) -> Any` hook run **as the trigger
  goes on the stack** (rule 603.3), with the same immutable fire-time controller.
  Its result is stored on *this trigger's own* `StackObject.event_state` and
  passed to `effect(game, controller, event_state)` at resolution. This is how a
  trigger correlates itself to the firing's event-specific facts **without** a
  mutable source-level slot that a later firing would clobber — the whole point of
  the Thousand-Year Storm fix (see *Copied spells* below). Two pending triggers of
  the same source hold independent `event_state`, so LIFO resolution copies the
  right spell the right number of times.
- **Required-vs-optional target semantics.** `targeting` returning **`None`**
  means a *required* target has no legal choice, so the trigger is **not put on
  the stack at all** (rule 603.3c). Returning a **list** — possibly empty — puts
  the trigger on the stack with those targets; the empty list is the genuinely
  *optional* "up to N target" case (Zimone chooses zero, one, or two). `None` and
  `[]` are therefore distinct and documented on the hook.

**Spell target-stint revalidation (`engine/casting.py`, `engine/stack.py`).**
`cast_spell` and `cast_spell_free` capture an `ActivationContext` (casting
controller + each chosen target's **zone-generic** stint) on the spell's
`StackObject`, exactly as activated abilities do. The capture happens
**immediately after target selection and protection validation, before any cost
payment or `on_cast` side effect** — those can move a target, and the stint must
record where the target was *when it was chosen*. At resolution, `_resolve_spell`
runs `stint_checked_targets(game, context, targets)` before handing
`chosen_targets` to the card: a target no longer in the same zone-stint it was
chosen in — departed, or left-and-returned (a new object in the same Python
instance) — is replaced by `None` **at its position**, so heterogeneous/dependent
multi-target spells (Fiery Annihilation's `[creature, Equipment]`) still read by
index and each target is judged independently. This closes the gap the per-card
predicate re-checks left: a predicate ("still a creature an opponent controls",
"still Equipment attached to that creature") *passes* for a leave-and-return
object, but the captured stint rejects it.

**Copied spells (`copy_spell`, storm / Thousand-Year Storm).** A spell copy
carries its own `ActivationContext` and stint-revalidates at resolution like a
normal cast (same `stint_checked_targets` pass). A copy that **retains** the
original's targets *inherits the original's captured target stint ids* (with the
copy's controller for "you control"), so a retained target that left and returned
between the original's cast and the copy's resolution is rejected. A copy that
**chooses new targets** captures those new targets' *current* stints. A copy of an
object that carried no context (an ability copy) falls back to a fresh capture.

*Authoritative spell-cast history (`engine/player.py`, `engine/casting.py`).*
Spell-cast history belongs to the game/player/turn lifecycle, **not** to any one
triggered-ability source. Each `Player` keeps a turn-stamped record of the
instant and sorcery spells *that player* has cast this turn, written through
`record_instant_or_sorcery_cast(spell, turn_number)` and read through
`instant_or_sorcery_casts_this_turn(turn_number)` (a stale turn stamp reads as
empty, so the record resets lazily at the turn boundary — exactly once, without
depending on any cleanup step running). The record is populated at the **single
authoritative cast site**: `cast_spell` and `cast_spell_free` call
`_record_spell_cast` once per cast, right after the spell becomes cast (rule
601.2i) and only for instant/sorcery spells — so creatures, artifacts,
enchantments, planeswalkers, and lands (which never enter `cast_spell`) never
affect it, and it counts qualifying spells whether or not any Storm is present.
Because recording happens at the cast site rather than in a trigger's `capture`
hook, multiple observers of one cast (two Thousand-Year Storms, or any number of
cast-triggered abilities) increment it exactly once.

The history contains **cast occurrences, not permanent handles on cards**: the
same physical `CardImpl` object cast twice this turn (it resolved and returned to
a castable zone in between) appears as **two** entries. Accounting is therefore
occurrence-aware, never identity-based. `record_instant_or_sorcery_cast` **returns
the number of qualifying casts already made this turn *before* this one** — the
occurrence's immutable prior-cast count, fixed as its position in the per-turn
list at append time. `_record_spell_cast` returns that value (or `None` for a
non-qualifying spell), and `cast_spell` / `cast_spell_free` stamp it onto this
cast's `StackObject.prior_qualifying_casts`. Because each cast mints a fresh
`StackObject` (a recast object left and returned), that count belongs to the
*occurrence* — the stack representation of one cast — not to the mutable card, and
"the current cast" is thereby excluded exactly once (it is nowhere in its own
prior count) rather than by an object-identity filter that would wrongly drop
*every* earlier cast of a recast object. The public
`instant_or_sorcery_casts_this_turn` list is unchanged in shape (spell references
in cast order, one per occurrence), so existing consumers keep working.

*Immutable per-trigger state.* Thousand-Year Storm keeps **no** source-local
spell state — the former mutable `_pending_spell` slot and the `_storm_count` /
`_storm_turn` tally are gone. On each trigger's own `StackObject` its `capture`
hook (above) fixes an immutable record of (a) the **triggering spell's
`StackObject`** and (b) the **copy count**. The hook correlates to the triggering
spell's `StackObject` by identity (at fire time — immediately after the cast — the
spell sits in exactly one stack object, the representation of *this* occurrence)
and reads the **copy count straight off that occurrence's
`prior_qualifying_casts`** — the prior-cast count the casting pipeline stamped
there (above). It is never reconstructed from how many Storm triggers have since
resolved, nor from a scalar on the enchantment, nor by filtering the fire-time
controller's cast history for entries that "are not" the triggering spell (that
identity filter is the discarded approach — it dropped *every* earlier occurrence
of a recast object and undercounted). Sourcing the count this way makes it
occurrence-aware and independent of when this Storm entered, how long its trigger
has been registered, whether control changed, how many Storms exist, and when
pending triggers resolve: **recasting the same physical card this turn captures
0, 1, 2 …** across successive casts (each cast a distinct occurrence); A, B, then
the same A again captures two for the final A; a Storm that entered after two
spells were cast still captures two; two Storms (one late) capture the same count
for one cast, incrementing the underlying history only once; a control change
reads the *new* controller's history (zero for that player's first spell), never
the previous controller's. Casting B in response to A's Storm trigger still makes
B's trigger copy B once and A's copy A zero times, in LIFO order; a triggering
spell that has left the stack (countered) makes zero copies and never falls back
to a different pending spell.

*Protection-aware retargeting via the shared spell-retargeting path.* When the
controller chooses new targets for a copy, each target is re-chosen through
`engine.casting.query_spell_target(game, player, spell, spec, exclude)` — the
single reusable helper that applies the **complete** cast-time legality contract
*for the copied spell*: zone, the (arity-aware, so **dependent**) target filter,
distinctness via `exclude`, and **protection from the copied spell** (a protected
permanent is **absent from the offered option set**, not offered then rejected).
Its query provenance identifies the copied spell — a stack-zone spell — rather
than mislabelling the battlefield enchantment as a spell on the stack. Fiery
Annihilation's "Equipment attached to *that* creature" is offered relative to the
copy's newly-chosen creature; a required spec with no legal target, or a declined
optional one, keeps the original target at that position. Protection is judged
against the *copied* spell (equivalently the original being copied — they share
every protection-relevant characteristic), never against Thousand-Year Storm.

**Dependent-target casting (`engine/casting.py`).** A `TargetRequirement.filter_fn`
may now take a second positional argument — the list of targets already chosen
for earlier requirements of the same cast — expressing a *dependent* requirement
(rule 601.2c). `_safe_filter` inspects the filter's arity (`_filter_wants_chosen`)
and calls `filter_fn(obj, chosen)` or `filter_fn(obj)` accordingly; single-arg
filters (every pre-existing card) are unaffected. `_query_target` passes the
already-chosen `exclude` list as that `chosen` context both when building the
option set and in the post-selection validation, so no card-specific backdoor is
needed and Player-Query validation is preserved. Fiery Annihilation's "Exile up
to one target **Equipment attached to that creature**" uses this: the Equipment
requirement's filter accepts only Equipment whose `attached_to` is the creature
chosen for the first (required) target, so Equipment on any *other* creature is
never offered. At resolution each target is revalidated independently — the
Equipment is exiled only while still attached to that creature target, and the
creature target still resolves if only it remains legal.

**Spell / ETB revalidation of the complete predicate.** Converted spells and
ETB-on-resolve effects now revalidate the **entire** original target predicate at
resolution, not merely zone membership. The predicate is factored into a single
named method shared by `get_targets` and `on_resolve` (e.g.
`_is_opponent_creature`, `_is_opponent_nonland_permanent`, `_is_your_creature`/
`_is_their_creature`), so the cast-time filter and the resolution-time check can
never drift. A target that changed control, ceased to be the required card type,
or otherwise stopped satisfying its restriction before resolution is illegal and
the effect does nothing to it (rule 608.2b/2c).

- **Gap found and fixed** (predicate-share + resolution revalidation, each with a
  negative resolution test where the restriction is mutable): fdn_31 (Bigfin
  Bouncer), fdn_144 (Mischievous Pup), fdn_215 (Bushwhack — both fight targets),
  fdn_256 (Meteor Golem), fdn_38 (Faebloom Trick), fdn_75 (Vampire Soulcaller —
  creature card in your graveyard), fdn_99 (Apothecary Stomper — mode 0),
  fdn_104 (Elvish Regrower — permanent card in your graveyard), fdn_188 (Abrade —
  damage mode), spg_74 (Condemn — attacking creature), and fdn_86 (Fiery
  Annihilation, see dependent targets above).
- **Modal player-target** (fdn_69 Seeker's Folly): revalidation added for
  uniformity, but no negative test — "target opponent" has no *mutable*
  restriction (a player cannot become the caster mid-game).
- **Already revalidated fully — no change**: fdn_98 (Ambush Wolf — target is any
  graveyard card, and `on_resolve` already re-checked graveyard membership, the
  only restriction), fdn_136 (Angel of Finality — targets a player, immutable),
  fdn_231 (Reclamation Sage — `on_resolve` already re-checked battlefield +
  artifact-or-enchantment).

### AbilityError cluster attribution (task 8)
The `activate_ability … AbilityError: cost could not be paid` cluster (130 of 203
`ENGINE_ERROR`s) survived Phase C unchanged, disproving the earlier
equip-lifecycle / counter-persistence hypotheses. Per-card mechanism, with the
transcript, split into card-side fixes and executor-side Phase-E input:

- **Hungry Ghoul (fdn_62)** — *card-side, fixed here.* The `{1}, Sacrifice
  another creature` cost read a never-assigned `_sacrifice_target` backdoor and
  always failed. The sacrifice is a **cost choice**, so it now picks the creature
  via `choose_object` at cost-payment time (answered by an Intent in tests / the
  replay-derived intent / the permissive baseline in validation) — no legal
  "another creature" → the cost cannot be paid (correct). Corpus 22 → 1.
- **Heartfire Immolator (fdn_201)** — *split.* Task 3 fixed its dead-target
  **no-op** (`_current_target` → the targeted-ActivatedAbility channel), but its
  6 `AbilityError`s **persist** — they are the same executor-side cause as the
  equipment: the `{R}` in `{R}, Sacrifice this creature` is unfunded at the
  executor's activation moment (Phase E). Corpus-measured unchanged at 6.
- **Goldvein Pick (fdn_253) + Adventuring Gear (fdn_249)** — *executor-side
  (Phase E).* Both use the base `Equipment` equip ability, whose `_cost`
  re-checks `is_sorcery_speed(game, controller)` and `mana_pool.can_pay({1})`.
  The AbilityError fires when, at the executor's activation moment, either the
  equip `{1}` is unfunded (the `ManaPaid` look-ahead in `_apply_spell_mana_lookahead`
  is keyed to the ability's instance id) or the engine's sorcery-speed context
  (phase / active-player / empty-stack) is not satisfied. Not patched here per the
  issue's do-not-touch-executor scope; Phase E must reconcile ManaPaid→equip
  funding and the sorcery-speed context.
- **Drake Hatcher (fdn_35)** — *executor-side (Phase E).* Cost `remove three
  incubation counters` reads a custom `incubation_counters` int fed only by the
  engine's combat-damage trigger. The executor reconstructs **no** counter state
  from GRE (it re-derives only the P/T correction surface), so at the replay's
  activation the engine holds < 3 counters and the non-mana cost cannot be paid.
  Phase E must reconstruct counter state (or drive the combat-damage trigger).
- **Loot, Exuberant Explorer (fdn_106)** — *executor-side (Phase E).* The
  `{4}{G}{G}, {T}` activation's multi-pip mana is unfunded at the executor's
  activation moment. (Task 7 also corrected its `.tapped`→`is_tapped` tap-cost
  drift, a contributing card-side error.)

### AST-guard extension (task 9)
`engine_tests/test_card_impl_ast_guard.py` gained three banned-pattern classes
(each with revert-proving self-tests): (e) reads of the dead `_current_target` /
`_resolve_target` backdoors (attribute load **or** `getattr(x, "_current_target")`)
— nothing assigns them, so a card reading one silently no-ops; (f) `.tapped`
writes (assignment/aug-assign **or** `setattr(x, "tapped", …)`) — the engine field
is `is_tapped`, and a `.tapped` write is invisible to state comparison and wrong
for `GameRef` matching. The dead `chosen_targets or _resolve_target` fallback was
removed workspace-wide (behavior-preserving: the backdoor was never assigned, so
`getattr(x, "_resolve_target", None)` was provably `None`).

## replay-gap Phase F — own-ETB ordering + counter flow (issue #37)

### Own enters-trigger ordering (rule 603.3a)
`move_to_zone` (engine/zones.py) and `_place_token`/`create_token`
(engine/game.py) now **register an entering permanent's own triggers and
replacement effects BEFORE firing its `EntersBattlefieldTriggeredEvent`**. The
old order fired the ETB event first, so a permanent's own enters-trigger was
never registered when its own entry event dispatched — silently suppressing
every own-enters ability (Prideful Parent's Cat token, Rune-Scarred Demon's
tutor, the whole self-ETB minter class that dominated MISSING_CARD). Rule
603.3a is explicit that a permanent's own enters-ability triggers on its own
entry; an "another …" ability excludes the source in its **own condition
filter** (the card-text responsibility), never by the engine suppressing the
whole event.

**31-subscriber audit** (every `EntersBattlefieldTriggeredEvent` subscriber,
per-card verdict): no "another …"-filtered card self-fires — all correctly
reject `event.permanent is source` (fdn_9/23/100/141/149/240 exclude self;
fdn_2 Arahbo is deliberately "this OR another"; landfall/opponent-creature
watchers can never match their own source). The old ordering was **not**
papering over a filter bug; the real regression it hid was the opposite: two
cards (Arahbo fdn_2, Rune-Scarred Demon fdn_184) carried an `on_resolve`
self-mint **workaround** for the old order AND a self-matching ETB trigger, so
the flip would double-fire them — the redundant `on_resolve` was removed; the
registered trigger now handles their own entry exactly once. — Rejected:
keeping the ETB-before-register order and the per-card `on_resolve` workarounds
(suppresses every own-enters ability; the workaround does not scale to the
whole minter class and Phase E's correlation cannot keep tokens that never
mint).

### Counters are an engine primitive — no card-private stashes
Every card-private counter attribute was moved onto the engine counter system
(`engine.game.add_counter` / `remove_counter`, read via `.counters` /
`_generic_counters`): Drake Hatcher `incubation` (fdn_35), Nine-Lives Familiar
`revival` (fdn_66), Ravenous Amulet `soul` (fdn_131), and the unused
fellowship/bait stubs (fdn_127/fdn_128). A bespoke `self.incubation_counters`
int is invisible to `.counters`, to state comparison, and to the replay
executor's `CounterAdded` sync (see root `KEY_DECISIONS.md` Phase F), so a cost
reading it can never be funded from GRE-attested counter state. Generic
counters persist across zone changes and characteristic resets exactly as the
old int did, so the conversion is behavior-preserving. The AST guard gains rule
**(g)**: any `*_counter(s)` attribute assignment (plain / augmented / annotated
/ `setattr`) other than the engine's own fields (`plus_one_counters` /
`minus_one_counters` + `_base_*` shadows, `_generic_counters`) is flagged as a
private stash, with revert-proving self-tests. — Rejected: leaving card-private
counter ints (unreadable by the engine and the CounterAdded sync; the exact gap
that left Drake Hatcher's cost unpayable in replay).

## replay-gap Phase G — gain-life tapland ETB trigger (issue #42)

Format: date — decision — why — rejected alternative.

- 2026-08-12 — The FDN gain-life tapland cycle (`cards/fdn/gainlife_taplands.py`) registers "when this enters, you gain 1 life" as a real `EntersBattlefieldTriggeredEvent` trigger (a self-ETB `condition = event.permanent is source`, `effect(game, controller)` gaining 1 life for the fire-time controller, `source = self`), instead of gaining the life inside `on_resolve`. `on_resolve` keeps only "enters tapped" (a genuine as-enters effect). — "You gain 1 life" is a triggered ability by the rules (603.2), so it belongs on the stack, and putting it there lets its resolution cadence be driven — the replay executor resolves it at GRE's observed `ability_resolution`, and normal-game play resolves it via the stack in `priority_loop`. The Phase F own-ETB ordering (603.3a: register own triggers before firing the ETB event) is what makes a self-ETB trigger fire at all. — Rejected: keeping the life in `on_resolve` (applies at land-play drive time, a snapshot or two before GRE's trigger resolution — the run-length-1 life transient Phase G's replay layer aligns; a card-fidelity bug, not just a replay artifact).
- 2026-08-12 — (flashback exile disposition — REWORKED; this entry supersedes its own earlier inference-based wording in place) A spell cast via flashback is exiled instead of being put anywhere else any time it would leave the stack (rule 702.34a) — when it resolves AND when it is countered. Design: (1) flashback is an **explicit cast mode** — `cast_spell_free(game, player, card, from_zone, *, mode=CastMode.FLASHBACK)` — validated before any mutation (must be a graveyard cast of a card with a real `flashback_cost`, else `CastingError`); the helper never infers the mode from `from_zone`+`flashback_cost`, so a flashback-capable card free-cast from the graveyard WITHOUT the mode (an Underworld-Breach-style cast) keeps the graveyard default, and a free cast from exile (cascade/Etali) is unchanged. (2) The override is stamped as `StackObject.departure_zone = Zone.EXILE` (field RENAMED from `resolution_zone`: it is a stack-departure replacement, not a resolution detail) — per cast occurrence, on the StackObject, never the card; `copy_spell` copies carry `None` (a copy is not a flashback cast and its card object occupies no stack zone). (3) `engine.stack.move_spell_off_stack(game, stack_obj, to_zone, resolving=)` is the single primitive through which every spell leaves the stack: it removes exactly the given StackObject once, sends the card to `departure_zone or to_zone` via `move_to_zone` (owner's destination zone; controller's for battlefield entry), moves the card at most once (an `on_resolve` that already moved its card leaves nothing to move), and on the countering path fizzles without moving anything when the StackObject already departed — a re-cast card is never moved by a stale counter. `_resolve_spell` routes both the permanent and non-permanent paths through it, and the FDN 48/153/160 counterspell `_counter_spell` helpers are thin shims over it. — How a spell was cast is the caster's statement, made where the knowledge lives (a card effect, the replay executor holding the GRE graveyard→stack attestation + card capability, a test) and validated by the engine; the disposition then belongs to that one cast occurrence and must be honoured at every stack exit by one shared mechanism. — Rejected/RETRACTED: inferring flashback inside `cast_spell_free` from graveyard source + printed `flashback_cost` (the first Phase G cut, retracted: a generic casting API must not guess intent — the inference would silently exile legitimate non-flashback graveyard free-casts) and that cut's rejection of an explicit parameter; per-card `on_resolve` exile (unchanged rejection: runs before the zone move and misses countering).
- 2026-08-12 — (amendment: FLASHBACK validation made atomic + owner-scoped; occurrence identity for stack targeting) CORRECTS the claim above ("validated before any mutation"): as first shipped, `cast_spell_free` set `card.controller = player` and the `card.owner` default BEFORE the FLASHBACK block, so a rejected claim mutated a controllerless card's controller. Now the whole FLASHBACK block runs strictly before the controller/owner defaults and every other mutation; it also requires the card to be in the **casting player's own graveyard** with compatible ownership (702.34a casts from its owner's graveyard), rejecting another player's card or another player's graveyard. NORMAL free-casts keep the historical permissiveness (any player's zone, no ownership constraint — existing callers deliberately free-cast another player's card). Companion engine change: `Zone.STACK` target requirements now enumerate exact `StackObject` occurrences (`StackObject.is_spell` marks cast spells and copies; abilities/triggers stay `False`), each minting its own instance id (`object_decision(attrs_from=source)` presents the source card's printed identity), and `object_current_zone` treats an occurrence's `game.stack` presence as its zone-stint so a departed occurrence is nulled at resolution (608.2b) even after the card is re-cast. `cast_spell`/`cast_spell_free` return the pushed StackObject so callers can hold the occurrence. The FDN 48/153/160 counterspells select targets by `is_spell` — never by inspecting a shared source card. — A source card is not a unique occurrence (a shared trigger, a copy, a recast); counterspell targeting and stint revalidation must key on the occurrence or they mis-handle exactly those cases. — Rejected: keeping the pre-mutation ordering "close enough" (a rejected claim must be byte-for-byte inert, pinned by state-snapshot tests); recovering a target occurrence from its source card at resolution (ambiguous for copies/recasts).

## replay-gap Phase H — token minters + token-identity completion (issue #43)

Format: date — decision — why — rejected alternative.

- 2026-08-12 — Every FDN card that mints a common token routes through one shared factory, `cards/fdn/tokens.py`: `make_food_token()`/`make_treasure_token()` and `make_creature_token(name, subtypes, colors, power, toughness, *, keywords=None)`. A token is given the EXACT characteristics `data/replays/token_id_map.json` records for its grpId — card types, subtypes, base power/toughness, and an explicit `colors` attribute (a token has no mana cost to derive colour from, and `engine.protection.get_colors` — which the replay executor's colour read mirrors — consults an explicit `colors` first). — The replay executor correlates an engine-minted token to its GRE grpId by matching `(card types, subtypes, base P/T)`, and for a signature several identities share (the white 1/1 Human 94158 vs the red 1/1 Human copy 93797) by the token's explicit colour; a token minted with the right characteristics is stamped with its grpId and becomes producible (so its MISSING_CARD and battlefield-shadow divergences clear), while one built ad hoc with a wrong/absent subtype or colour stays anonymous. A single factory keeps every minter's token in sync with the map. Real signature bugs this surfaced and fixed: Bake into a Pie (fdn_169) minted a Food with card_types but NO `Food` subtype; Stroke of Midnight (fdn_148) minted a Human with no subtype and the name "Human Token"; Resolute Reinforcements (fdn_145) minted a Soldier as `{Human, Soldier}` (map is `{Soldier}`) — each never correlated until fixed. — Rejected: per-card ad-hoc `Creature(...)`/`Artifact(...)` construction with no colour and inconsistent subtypes (the status quo — three latent signature bugs, and no token colour for the colliding Human identity); adding a `colors` kwarg to `CardImpl.__init__` (broader engine change than needed — an explicit attribute on the token instance is enough and matches how `get_colors` already reads colour).
- 2026-08-12 — Food and Treasure tokens carry their REAL abilities as engine primitives, not per-card no-ops: `FoodToken` exposes `get_activated_abilities` for "{2}, {T}, Sacrifice this token: You gain 3 life" (an `ActivatedAbility` whose cost pays {2}, taps, and sacrifices the token, remembering the paying controller on the token so the deferred life-gain effect credits them after the token has left the battlefield), and `TreasureToken` exposes `get_mana_abilities` for "{T}, Sacrifice this token: Add one mana of any color" (a `ManaAbility` whose cost taps + sacrifices and whose production asks the controller for a colour via `choose_color`, adding one mana of the chosen `ManaType`). — Rule 111: a token is a real permanent with the abilities its creator grants; the prior "ENGINE LIMITATION: not fully functional" no-op tokens were the honesty gap this phase closes, and Treasure's sac-for-mana is a primitive the funding phase (#46) can consume. — Rejected: leaving the abilities as documentation-only stubs (the token would not gain life or produce mana under real play or a future replay driver); producing a fixed colour for Treasure instead of a real choice ("any color" is a genuine choice — model it as a query the DeterministicPlayer answers from GRE intent).
- 2026-08-12 — Liliana, Dreadhorde General (fdn_176) +1 now creates a 2/2 black Zombie token (grpId 94170); its impl previously carried a different Liliana's abilities entirely ("+1: each opponent sacrifices a creature"). Only the +1 (the token minter, the Phase H concern) is corrected; the passive dies-trigger draw and the -4/-9 abilities remain simplified stubs, documented as out of scope (review follow-up: the -4 stub previously still executed the OTHER Liliana's mass-draw — an actively wrong effect, not an inert stub — and now no-ops like the -9). — The +1 is the Zombie minter named by the corpus. CORRECTION (review follow-up): loyalty abilities are NOT driven by the replay executor — its only ability bridge enumerates `get_activated_abilities()` and builds `ActivatedAbilityInstance` only (root KEY_DECISIONS, Phase E task 4), so a planeswalker's loyalty activation falls through and the Zombie stays MISSING (verified empirically on a Liliana corpus game). The +1 belongs with the dormant set below: characteristic-correct now, correlating only once loyalty driving lands. — Rejected: rewriting the whole card (the -4/-9 involve player-choice sacrifice and per-type sacrifice, unrelated to token minting and out of this phase's scope).
- 2026-08-12 — Which token minters clear a MISSING_CARD in replay is gated by whether their trigger FIRES in the executor, independent of this phase's characteristic fixes. Minters on spell `on_resolve`, ETB/landfall triggers, dies triggers, and driven activated abilities fire (Bake into a Pie, Cat Collector, Involuntary Employment, Gleaming Barrier, Brass's Bounty, An Offer You Can't Refuse, Heroic/Resolute Reinforcements, Stroke of Midnight, Goblin Negotiation/Surprise, Krenko, Dwynen's Elite, Elfsworn Giant, Infestation Sage, Dragon Trainer, Faebloom Trick, Hare Apparent; also Fake Your Own Death — review correction: its Treasure hangs off a `CreatureDiesTriggeredEvent` trigger granted by the driven instant's `on_resolve`, and dies events DO fire from `move_to_zone`, so it is not a dormant-event case). Minters on combat-damage, cast (`SpellCastTriggeredEvent`), attack, upkeep/end-step, and draw triggers stay dormant because the engine never fires those events (Tier 0 finding, issue #40): Eager Trufflesnout, Midnight Snack, Goldvein Pick, Kykar (Spirit), Rite of the Dragoncaller (Dragon 94172), Searslicer, Lathril, Sylvan Scavenging, Koma, Kiora, Mischievous Mystic, Fishing Pole (Fish, and its bait-counter/untap mechanic is unimplemented); loyalty minters (Liliana) are dormant too — the executor drives `ActivatedAbilityInstance` only, never `get_loyalty_abilities` (see the corrected entry above). Their token characteristics are made correct anyway so they correlate the moment the dormant-event work (#44) lands. — Implement the mint EFFECT wherever it lives, honestly, and let the dormant-event limitation stay attributed rather than faking a fire. — Rejected: forcing dormant triggers to fire from card code (a whole-engine event-plumbing change belongs to #44, not per-card workarounds).
- 2026-08-12 — Two token identities stay MISSING by design, not for lack of a minter: the generic black Rat 94169 (Revenge of the Rats) shares its `(Creature, {Rat}, 1/1, black)` signature with the black Burglar Rat copy token 93883, and correlation refuses to guess between a generic and a same-colour copy (KEY_DECISIONS root, identity rules), so a minted Rat stays id-less and unproducible; the 1/1 white Human 94158's residual MISSING games contain no Stroke of Midnight (grpId 93861) at all — that token comes from an out-of-registry source. — Producibility is attested by an actual stamped correlation, never inferred; an ambiguous or out-of-registry token must surface honestly. — Rejected: stamping the Rat by snapshot-exclusivity or naming it to force a match (both violate the locked identity rules).
