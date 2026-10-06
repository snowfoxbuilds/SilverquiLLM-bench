"""Casting and resolution pipeline for spells and lands.

Provides the full flow from casting a spell or playing a land through
resolution:

- :func:`cast_spell` — verify timing & legality → move hand to stack →
  choose targets → pay costs → call ``on_cast`` → push :class:`StackObject`.
- :func:`play_land` — verify land play remaining → move hand to
  battlefield → decrement ``land_plays_remaining``.
- :func:`is_sorcery_speed` / :func:`can_cast_at_instant_speed` — timing
  helpers used by the casting pipeline.

Resolution is embedded in the :class:`StackObject` ``on_resolve`` callback
created by :func:`cast_spell`:

- Call ``card.on_resolve(game)``.
- The spell then leaves the stack through the shared departure primitive
  :func:`engine.stack.move_spell_off_stack`: permanents (creature /
  enchantment / artifact / planeswalker) to the battlefield, non-permanents
  (instant / sorcery) to the owner's graveyard — unless the cast stamped a
  departure replacement (a ``CastMode.FLASHBACK`` cast is exiled any time it
  leaves the stack, rule 702.34a).
"""

from __future__ import annotations

import enum
import inspect
from typing import TYPE_CHECKING, Any

from engine.card import CardImpl
from engine.events import SpellCastTriggeredEvent
from engine.stack import (
    StackObject,
    capture_activation_context,
    move_spell_off_stack,
    stint_checked_targets,
)
from engine.types import CardType, Keyword, ManaCost, Phase, Zone
from engine.zones import move_zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


# Card types that represent permanents — these go to the battlefield on resolve.
_PERMANENT_TYPES: frozenset[CardType] = frozenset({
    CardType.CREATURE,
    CardType.ENCHANTMENT,
    CardType.ARTIFACT,
    CardType.PLANESWALKER,
})


class CastingError(Exception):
    """Raised when a spell cast or land play is illegal."""


class CastMode(enum.Enum):
    """How a spell is being cast, when the manner of casting changes its
    disposition.

    ``FLASHBACK`` (rule 702.34): the spell is being cast from its owner's
    graveyard via its flashback ability, so it is exiled instead of being put
    anywhere else any time it would leave the stack (702.34a) — the cast's
    ``StackObject.departure_zone`` is set to ``Zone.EXILE``.

    The mode is always selected **explicitly by the caller** that knows *how*
    the spell is being cast (a card effect, the replay executor attesting a
    GRE graveyard→stack cast of a flashback-capable card, a test). The generic
    casting API never infers it from card attributes: a flashback-capable card
    can legally be cast from the graveyard by other means (a future
    Underworld-Breach-style effect), and that cast must not exile.
    """

    NORMAL = "normal"
    FLASHBACK = "flashback"


# ------------------------------------------------------------------
# Targeting — Player Query construction (generalizes TargetRequirement.filter_fn)
# ------------------------------------------------------------------


def _filter_wants_chosen(filter_fn: Any) -> bool:
    """Return ``True`` if *filter_fn* requires the already-chosen targets as a
    *second* positional argument — a *dependent* target filter (rule 601.2c
    dependent requirements), e.g. "target Equipment attached to *that creature*"
    whose legality depends on the creature chosen earlier in the same cast.

    A dependent filter is exactly ``(obj, chosen)`` — **two required positional
    parameters, neither defaulted**. The common one-argument filter ``(obj)``
    returns ``False``. Crucially, the loop-binding idiom
    ``lambda obj, _c=controller: ...`` also returns ``False``: its second
    parameter has a *default*, so it is not a dependent filter and must still be
    called with the object alone (never with the chosen list bound to ``_c``).
    """
    try:
        params = list(inspect.signature(filter_fn).parameters.values())
    except (TypeError, ValueError):
        return False
    required_positional = [
        p
        for p in params
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        and p.default is p.empty
    ]
    return len(required_positional) >= 2


def _safe_filter(filter_fn: Any, obj: Any, chosen: Any = ()) -> bool:
    """Evaluate a lazy target ``filter_fn`` defensively (illegal → excluded).

    Supports both the ``(obj)`` signature and the dependent ``(obj, chosen)``
    signature, where *chosen* is the list of targets already selected for
    earlier requirements of this same cast (see :func:`_filter_wants_chosen`).
    """
    try:
        if _filter_wants_chosen(filter_fn):
            return bool(filter_fn(obj, list(chosen)))
        return bool(filter_fn(obj))
    except Exception:
        return False


def _seat_of(game: GameState, player: Any) -> int | None:
    for seat, candidate in enumerate(game.players):
        if candidate is player:
            return seat
    return None


def _candidate_decision(game: GameState, candidate: Any, zone: Any) -> Any:
    """Build the OBJECT/PLAYER decision for a legal target candidate.

    A :class:`~engine.stack.StackObject` candidate (a spell on the stack — the
    ``Zone.STACK`` enumeration offers exact cast occurrences, never source
    cards) is identified by the **occurrence**: the instance id is minted for
    the StackObject itself, so two casts/copies of the same card are distinct
    options, while the presented attrs (name/types/colors) come from its source
    card so name-routed intents still match.
    """
    if any(candidate is p for p in game.players):
        return game.refs.player_decision(candidate, seat=_seat_of(game, candidate))
    if isinstance(candidate, StackObject):
        controller = candidate.controller
        return game.refs.object_decision(
            candidate,
            zone=Zone.STACK.value,
            controller_seat=_seat_of(game, controller) if controller is not None else None,
            attrs_from=candidate.source,
        )
    controller = getattr(candidate, "controller", None)
    return game.refs.object_decision(
        candidate,
        zone=getattr(zone, "value", zone) if zone is not None else "battlefield",
        controller_seat=_seat_of(game, controller) if controller is not None else None,
    )


def _source_decision(game: GameState, card: Any) -> Any:
    """The OBJECT decision for the spell/ability raising a query (routing
    source): a permanent whose ability asks is named as it is on the
    battlefield, so naming it never starts a new stint for it; anything else
    is named as a spell on the stack."""
    from engine.stack import battlefield_stint_id

    controller = getattr(card, "controller", None)
    return game.refs.object_decision(
        card,
        zone="battlefield" if battlefield_stint_id(game, card) is not None else "stack",
        controller_seat=_seat_of(game, controller) if controller is not None else None,
    )


def _query_target(
    game: GameState,
    player: Player,
    card: CardImpl,
    spec: Any,
    exclude: Any = (),
    protect_from: Any = None,
) -> Any:
    """Raise a Player Query for one target spec; return the chosen game object.

    The engine enumerates the legal option set (objects in ``spec.zone`` across
    both players, plus the players themselves), offers only those, and maps the
    Answer back to the game object via the Game Refs registry.

    A **required** spec (``optional`` unset/``False``) keeps a mandatory
    ``min == 1`` query and raises :class:`CastingError` when no legal target
    exists. An **optional** spec ("up to one target"; ``optional == True``) is
    declinable: an empty candidate set returns ``None`` without raising, and the
    query is offered with ``min == 0`` so the player may decline (also ``None``).
    ``None`` means "no target for this spec" — the caller adds nothing to
    ``chosen_targets``.

    *exclude* holds the objects already chosen for earlier target specs of this
    same cast; they are dropped from the candidate set so a multi-target spell
    picks **distinct** objects (rule 601.2c). For an optional spec this can
    empty the option set, which then declines cleanly rather than raising.

    *protect_from*, when given, is the spell/source whose *protection* legality
    is folded into the option set: a candidate with protection from it (rule
    509.1b — the *T* in DEBT) is **absent from the offered options**, never merely
    rejected after selection. Normal casting leaves this ``None`` (its option set
    is unchanged; protection is enforced by the post-selection check in
    :func:`cast_spell`); the shared :func:`query_spell_target` path pins it so a
    spell copy re-choosing targets can never be offered a permanent protected
    from that spell.
    """
    from engine.queries import PlayerQuery, ask

    filter_fn = getattr(spec, "filter_fn", None)
    zone = getattr(spec, "zone", None)
    optional = bool(getattr(spec, "optional", False))

    _has_protection = None
    if protect_from is not None:
        from engine.protection import has_protection_from as _has_protection

    candidates: list[Any] = []
    if zone == Zone.STACK:
        # Stack targets are exact StackObject occurrences (top to bottom), not
        # source cards: two casts/copies of the same card are distinct targets,
        # a trigger sharing a spell's source card is not that spell, and a
        # chosen occurrence stays legal only while IT is on game.stack (the
        # zone-stint revalidation treats the occurrence's stack presence as its
        # stint). Recovering an occurrence from its card at resolution would be
        # ambiguous for copies/recasts, so the occurrence is the target.
        candidates.extend(game.stack.objects())
    elif zone is not None:
        for p in game.players:
            if zone in p.zones:
                candidates.extend(p.zones[zone].get_all())
    candidates.extend(game.players)

    options: list[Any] = []
    by_decision: dict[Any, Any] = {}
    for candidate in candidates:
        if any(candidate is chosen for chosen in exclude):
            continue
        # *exclude* is also the already-chosen target list for this cast, so a
        # dependent filter (rule 601.2c) sees the earlier targets it depends on.
        if filter_fn is not None and not _safe_filter(filter_fn, candidate, exclude):
            continue
        # Protection (rule 509.1b): a candidate protected from *protect_from* is
        # not a legal target and is dropped from the option set entirely.
        if _has_protection is not None and _has_protection(candidate, protect_from):
            continue
        decision = _candidate_decision(game, candidate, zone)
        if decision in by_decision:
            continue
        options.append(decision)
        by_decision[decision] = candidate

    if not options:
        if optional:
            return None
        raise CastingError(
            f"Cannot cast {card.name!r} — no legal target for "
            f"{getattr(spec, 'description', 'target')!r}"
        )

    query = PlayerQuery(
        source=(_source_decision(game, card),),
        prompt=getattr(spec, "description", "choose target"),
        options=tuple(options),
        min=0 if optional else 1,
        max=1,
    )
    answer = ask(player, query)
    if not answer.selected:
        # A declined optional target (min == 0) — no object chosen.
        return None
    return by_decision[answer.selected[0]]


def query_spell_target(
    game: GameState,
    player: Player,
    spell: CardImpl,
    spec: Any,
    exclude: Any = (),
) -> Any:
    """Choose one target for *spell* applying the **complete** target-legality
    contract normal casting uses — the single reusable spell-retargeting path.

    *spell* is the spell on the stack doing the targeting: a spell **copy**
    re-choosing its targets (Thousand-Year Storm), or the original spell being
    copied (they share every protection-relevant characteristic). The contract:

    * **Zone** — only objects in ``spec.zone`` (plus players) are candidates.
    * **Target requirement** — ``spec.filter_fn``, evaluated arity-aware so a
      *dependent* target (rule 601.2c, e.g. "Equipment attached to *that*
      creature") sees the targets already chosen for this same retarget.
    * **Distinctness** — *exclude* (also the already-chosen list) removes prior
      picks so multiple requirements select distinct objects.
    * **Protection** — a permanent with protection from *spell* is **absent from
      the offered option set**, not offered then rejected at resolution (rule
      509.1b). Protection is judged against *spell* (the copied spell), never the
      permanent that created the copy.
    * **Provenance** — the query is raised *as* *spell* (a stack-zone spell), so
      routing/records identify the copied spell rather than mislabelling a
      battlefield source (Thousand-Year Storm) as a spell on the stack.

    Returns the chosen game object, or ``None`` when the spec is optional and the
    player declines / no legal candidate exists — the caller then keeps the
    original target for that position. Reuses :func:`_query_target`; the only
    addition over normal casting is that protection is pinned to *spell*.
    """
    return _query_target(game, player, spell, spec, exclude=exclude, protect_from=spell)


# ------------------------------------------------------------------
# Timing helpers
# ------------------------------------------------------------------

def is_sorcery_speed(game: GameState, player: Player) -> bool:
    """Return ``True`` if sorcery-speed timing is met for *player*.

    Sorcery speed requires all of:

    * *player* is the active player.
    * The current phase is a main phase (``PRECOMBAT_MAIN`` or
      ``POSTCOMBAT_MAIN``).
    * The stack is empty.
    """
    if player is not game.active_player:
        return False
    if game.phase not in (Phase.PRECOMBAT_MAIN, Phase.POSTCOMBAT_MAIN):
        return False
    if not game.stack.is_empty():
        return False
    return True


def can_cast_at_instant_speed(card: CardImpl, player: Player | None = None) -> bool:
    """Return ``True`` if *card* may be cast at instant speed.

    A card has instant-speed timing if it is an instant, has the
    :attr:`~engine.types.Keyword.FLASH` keyword, or *player* may cast spells
    as though they had flash (High Fae Trickster).
    """
    if CardType.INSTANT in card.card_types:
        return True
    if player is not None and getattr(player, "can_cast_as_flash", False):
        return True
    if Keyword.FLASH & card.keywords:
        return True
    return False


# ------------------------------------------------------------------
# Cost reduction
# ------------------------------------------------------------------

def _call_self_reduction(
    card: CardImpl, game: GameState, targets: list[Any] | None
) -> int:
    """Call ``card.cost_reduction``, passing *targets* only when the hook
    accepts it (backward-compatible with the historical ``(self, game)``
    signature)."""
    fn = card.cost_reduction
    try:
        params = inspect.signature(fn).parameters
        accepts_targets = "targets" in params or any(
            p.kind == p.VAR_KEYWORD for p in params.values()
        )
    except (TypeError, ValueError):
        accepts_targets = False
    return fn(game, targets=targets) if accepts_targets else fn(game)


def _battlefield_cost_reduction(
    game: GameState, card: CardImpl, caster: Player
) -> int:
    """Sum the generic reductions every battlefield permanent grants *card*.

    Consults each permanent's ``spell_cost_reduction(game, spell, caster)``
    hook (default 0), so "your instant and sorcery spells cost {1} less"
    permanents (Archmage of Runes, Mocking Sprite) reduce other spells.
    """
    total = 0
    for player in game.players:
        for perm in game.get_battlefield(player).get_all():
            hook = getattr(perm, "spell_cost_reduction", None)
            if callable(hook):
                total += max(0, int(hook(game, card, caster)))
    return total


def _raw_cost_reduction(
    game: GameState,
    card: CardImpl,
    controller: Player,
    targets: list[Any] | None = None,
) -> int:
    """Return the total generic reduction available for *card* — the spell's
    own :meth:`~engine.card.CardImpl.cost_reduction` (target-aware) plus the
    battlefield sweep — as a non-negative amount, **unclamped**.

    The clamp against a specific cost's generic pips is applied by the caller
    against whichever base cost is selected (the normal cost or a chosen
    alternative), so the reduction never eats colored pips. :func:`cast_spell`
    needs the unclamped figure to clamp per candidate cost.
    """
    # Ensure card.controller is set so the hook can reference "you" / the
    # casting player even when the card was never explicitly assigned one.
    prev_controller = card.controller
    card.controller = controller
    raw = _call_self_reduction(card, game, targets)
    # Restore previous controller in case the caller doesn't want a
    # side-effect (get_cost_reduction is a query, not a mutation).
    card.controller = prev_controller
    raw += _battlefield_cost_reduction(game, card, controller)
    return max(0, raw)


def get_cost_reduction(
    game: GameState,
    card: CardImpl,
    controller: Player,
    targets: list[Any] | None = None,
) -> int:
    """Return the total generic mana reduction for casting *card*'s normal cost.

    Combines the spell's own :meth:`~engine.card.CardImpl.cost_reduction`
    (target-aware when *targets* is supplied) with the battlefield sweep in
    :func:`_battlefield_cost_reduction`, then clamps so the generic portion of
    the (normal) mana cost cannot go below 0 (colored pips are never reduced).
    """
    generic = card.mana_cost.generic if card.mana_cost else 0
    return max(0, min(_raw_cost_reduction(game, card, controller, targets), generic))


def _choose_cost(
    game: GameState,
    player: Player,
    card: CardImpl,
    payable: list[tuple[int, ManaCost]],
) -> ManaCost:
    """Return the (already-reduced) mana cost the caster pays.

    *payable* is a list of ``(base_index, reduced_cost)`` pairs — one per base
    cost the player can actually pay — where ``base_index`` is the candidate's
    position in ``[normal_cost, *alternatives]``. Unpayable candidates are never
    offered (rule 601.2f: a player can only choose to pay a cost they can pay).

    When only one candidate is payable it is returned without asking. Otherwise
    the caster answers a Player Query whose option indices are the base indices,
    so a recorded choice ("the alternative", index 1) still maps unambiguously
    even though unpayable candidates were filtered out.
    """
    if len(payable) == 1:
        return payable[0][1]

    from engine.decisions import Decision
    from engine.queries import PlayerQuery, ask

    # Index 0 is the normal mana cost; each alternative carries the printed
    # ability that grants it.
    alternative_printed = dict(enumerate(card.alternative_cost_printed, start=1))
    options = tuple(
        Decision.ability(index=i, printed=alternative_printed[i])
        if i in alternative_printed
        else Decision.ability(index=i)
        for i, _ in payable
    )
    query = PlayerQuery(
        source=(_source_decision(game, card),),
        prompt="Choose a cost to pay",
        options=options,
        min=1,
        max=1,
    )
    answer = ask(player, query)
    idx = dict(answer.selected[0].attrs)["index"]
    by_index = {i: cost for i, cost in payable}
    return by_index[idx]


def _apply_cost_reduction(cost: ManaCost, reduction: int) -> ManaCost:
    """Return a new :class:`ManaCost` with *reduction* subtracted from generic."""
    new_generic = max(0, cost.generic - reduction)
    return ManaCost(
        generic=new_generic,
        pips=dict(cost.pips),
        x_count=cost.x_count,
        hybrid=list(cost.hybrid),
    )


# ------------------------------------------------------------------
# Spell-cast history (per-player, per-turn) — authoritative record
# ------------------------------------------------------------------

_INSTANT_SORCERY: frozenset[CardType] = frozenset({CardType.INSTANT, CardType.SORCERY})


def _record_spell_cast(game: GameState, player: Player, card: CardImpl) -> int | None:
    """Record *card* in *player*'s per-turn instant/sorcery cast history.

    This is the single authoritative point at which a cast is counted (rule
    601.2i — the spell has become cast). It runs once per cast, for both the
    normal and free-cast paths, and only for instant and sorcery spells — so
    creatures, artifacts, enchantments, planeswalkers, and lands never affect the
    count. Recording here (not in any trigger's capture hook) is what keeps the
    count correct when several observers — e.g. two Thousand-Year Storms — watch
    the same cast: the history is incremented exactly once regardless of how many
    triggers fire. See :meth:`engine.player.Player.record_instant_or_sorcery_cast`.

    Returns the immutable prior-qualifying-cast count for this occurrence — the
    number of instant/sorcery spells *player* had already cast this turn before
    this one — or ``None`` for a non-qualifying spell (which is not recorded).
    The caller stamps this onto the cast's :class:`~engine.stack.StackObject`, so
    the count travels with this exact occurrence rather than being reconstructed
    later by excluding the triggering spell from history by object identity.
    """
    if card.card_types & _INSTANT_SORCERY:
        return player.record_instant_or_sorcery_cast(card, game.turn_number)
    return None


def _fire_spell_cast_event(
    game: GameState, player: Player, card: CardImpl
) -> None:
    """Fire :class:`~engine.events.SpellCastTriggeredEvent` for this cast.

    Called from both cast paths **once** per cast, immediately after the
    spell's :class:`~engine.stack.StackObject` is on the stack — the spell has
    become cast (rule 601.2i) and the event occurs, so "whenever a player casts
    a spell" abilities (prowess, Thousand-Year Storm, cast-count triggers) queue
    their triggered abilities on top of it (rule 603.3). Every registered
    subscriber reads ``event.spell`` as the cast *card* (its ``card_types``) and
    ``event.player``/``event.controller`` as the caster, so we populate the card
    on both ``spell`` and ``card`` and the caster on both ``player`` and
    ``controller``. Firing once here — not from any trigger's own hook — keeps
    the event count correct no matter how many abilities observe the cast.
    """
    game.trigger_manager.fire_event(
        game,
        SpellCastTriggeredEvent(
            spell=card, card=card, player=player, controller=player,
            # On the stack, X is its chosen value (rule 202.3e).
            mana_value=card.mana_cost.cmc
            + getattr(card, "x_value", 0) * card.mana_cost.x_count,
        ),
    )


# ------------------------------------------------------------------
# Cast spell
# ------------------------------------------------------------------

def _announce_x(
    game: GameState, player: Player, card: CardImpl, *, free: bool = False, reduction: int = 0
) -> None:
    """Choose the value of X while casting (rule 601.2b).

    A spell cast without paying its mana cost has X = 0 (rule 107.3b). The
    offered maximum counts the generic *reduction* the payment will get.
    """
    from engine.card_queries import choose_number

    card.x_value = 0  # type: ignore[attr-defined]
    x_count = card.mana_cost.x_count
    if x_count and not free:
        maximum = max(0, player.mana_pool.total() + reduction - card.mana_cost.cmc) // x_count
        card.x_value = choose_number(  # type: ignore[attr-defined]
            game, player, 0, maximum, "Choose X", source_card=card
        )


def _with_x(cost: ManaCost, x_value: int) -> ManaCost:
    """*cost* with each {X} replaced by *x_value* generic mana (rule 601.2f)."""
    if not cost.x_count:
        return cost
    return ManaCost(
        generic=cost.generic + x_value * cost.x_count,
        pips=dict(cost.pips),
        x_count=0,
        hybrid=list(cost.hybrid),
    )


def _place_deferred_cast_triggers(game, spell, deferred):
    if not deferred:
        return
    cast_triggers = []
    while game.stack.peek() is not spell:
        cast_triggers.append(game.stack.pop())
    triggers = [*deferred, *reversed(cast_triggers)]
    for active in (True, False):
        for trigger in triggers:
            if (trigger.controller is game.active_player) == active:
                game.stack.push(trigger)


def _mana_payment_window(game, player, spell, costs):
    """Let the caster activate mana abilities while paying (rule 601.2g)."""
    from engine.abilities import AbilityError, ActivatedAbilityInstance, activate_ability
    from engine.card_queries import choose_number, choose_object
    blocked = set()
    deferred = []
    while not any(player.mana_pool.can_pay(cost) for cost in costs):
        sources = [c for c in game.get_battlefield(player).get_all()
                   if c.object_id not in blocked and not getattr(c, 'is_tapped', False)
                   and callable(getattr(c, 'get_mana_abilities', None)) and c.get_mana_abilities()]
        if not sources:
            break
        source = choose_object(game, player, sources, 'Activate a mana ability',
                               source_card=spell, optional=True)
        if source is None:
            break
        abilities = source.get_mana_abilities()
        index = (choose_number(game, player, 0, len(abilities)-1, 'Mana ability', source_card=source)
                 if len(abilities) > 1 else 0)
        ability = abilities[index]
        before = player.mana_pool.total()
        stack_size = len(game.stack)
        try:
            activate_ability(game, player, ActivatedAbilityInstance(
                source=source, controller=player, cost=ability.cost,
                effect=ability.mana_produced, is_mana_ability=True,
                printed=getattr(ability, 'printed', None)))
        except AbilityError:
            blocked.add(source.object_id)
        added = []
        while len(game.stack) > stack_size:
            added.append(game.stack.pop())
        deferred.extend(reversed(added))
        if player.mana_pool.total() <= before:
            blocked.add(source.object_id)
    return deferred


def grant_cast_permission(game, player, card, *, from_zone=Zone.EXILE,
                          until_turn=None, life_cost=False, departure_zone=None,
                          controller_source=None, normal_face_only=False):
    """Let *player* cast (or, for a land, play) *card* from *from_zone* while it
    stays the object it is now — a later zone change ends the permission."""
    permission = dict(player=player, card=card, zone=from_zone,
                      epoch=game.refs.zone_epoch(card), until_turn=until_turn,
                      life_cost=life_cost, departure_zone=departure_zone,
                      source=controller_source,
                      normal_face_only=normal_face_only,
                      source_epoch=game.refs.zone_epoch(controller_source) if controller_source else None)
    game.cast_permissions.append(permission)


def cast_permission(game, player, card):
    """The permission that lets *player* cast *card* where it is now, if any."""
    from engine.stack import object_current_zone
    for permission in game.cast_permissions:
        source = permission['source']
        if source is not None:
            if (object_current_zone(game, source) != Zone.BATTLEFIELD.value or
                    game.refs.zone_epoch(source) != permission['source_epoch'] or
                    source.controller is not player):
                continue
        elif permission['player'] is not player:
            continue
        if (permission['card'] is card and
                permission['epoch'] == game.refs.zone_epoch(card) and
                object_current_zone(game, card) == permission['zone'].value and
                (permission['until_turn'] is None or permission['until_turn'] == game.turn_number)):
            return permission
    return None


def permitted_cards(game, player):
    """``(card, zone)`` for every card a cast permission lets *player* cast or play now."""
    found = []
    for permission in list(game.cast_permissions):
        card = permission['card']
        if any(card is other for other, _ in found):
            continue
        if cast_permission(game, player, card) is not None:
            found.append((card, permission['zone']))
    return found


def _holding_zone(game, card, zone):
    return next((p.zones[zone] for p in game.players if p.zones[zone].contains(card)), None)


def cast_spell(game: GameState, player: Player, card: CardImpl, **kwargs) -> StackObject:
    """Cast *card*, restoring where it was if casting fails part-way."""
    origin = next((owner.zones[zone] for owner in game.players for zone in Zone
                   if zone in owner.zones and owner.zones[zone].contains(card)), None)
    controller = card.controller
    try:
        return _cast_spell(game, player, card, **kwargs)
    except Exception:
        if origin is not None and not origin.contains(card):
            for owner in game.players:
                if owner.zones[Zone.STACK].contains(card):
                    owner.zones[Zone.STACK].remove(card)
                    origin.add(card)
                    break
        restore = getattr(card, 'restore_front_face', None)
        if restore is not None:
            restore()
        card.controller = controller
        raise


def _cast_spell(
    game: GameState,
    player: Player,
    card: CardImpl,
    *,
    from_zone: Zone = Zone.HAND,
    mode: CastMode = CastMode.NORMAL,
    ignore_timing: bool = False,
    departure_zone: Zone | None = None,
) -> StackObject:
    """Cast *card* from *player*'s hand, or from *from_zone* when a cast
    permission allows it.

    ``mode=CastMode.FLASHBACK`` casts the card from its owner's graveyard for
    its flashback cost (rule 702.34a) and exiles it whenever it leaves the
    stack; every flashback check runs before any mutation.

    Pipeline
    --------
    1. **Timing check** — instants (and cards with flash) can be cast
       whenever the player has priority; everything else requires
       sorcery-speed timing.
    2. **can_cast** — ask the card whether it can legally be cast.
    3. **Zone check** — the card must be in the player's *from_zone*.
    4. **Move to stack zone** — remove the card from *from_zone* and
       place it into the player's stack zone.
    5. **Choose targets** — if the card specifies targets (via
       :meth:`CardImpl.get_targets`), the player is asked to choose.
    6. **Mana check / payment** — the player's mana pool must be able to
       pay the card's mana cost.  If payment fails, the card is rolled
       back from the stack zone to *from_zone*.
    7. **Call on_cast** — invoke the card's ``on_cast`` hook.
    8. **Push StackObject** — push a :class:`StackObject` whose
       ``on_resolve`` callback handles resolution.

    Returns:
        The pushed :class:`StackObject` — the stack identity of this one cast
        occurrence, for callers (tests, the replay executor) that must later
        refer to exactly this pending spell rather than its mutable source
        card (which a copy, a recast, or the card's own triggered abilities
        can make ambiguous).

    Raises:
        CastingError: If any legality check fails.
    """
    if hasattr(card, 'choose_cast_face'):
        card.choose_cast_face(game, player)
    # 1. Timing
    if not ignore_timing and not can_cast_at_instant_speed(card, player) and not is_sorcery_speed(game, player):
        raise CastingError(
            f"Cannot cast {card.name!r} — sorcery-speed timing not met"
        )

    # 2. can_cast
    if not card.can_cast(game):
        raise CastingError(f"Cannot cast {card.name!r} — can_cast returned False")

    # 3. Zone check (the hand unless a cast permission names another zone)
    if mode is CastMode.FLASHBACK:
        if from_zone != Zone.GRAVEYARD:
            raise CastingError(
                f"Cannot flashback {card.name!r} — flashback casts from the "
                f"graveyard, not {from_zone.name}"
            )
        if getattr(card, "flashback_cost", None) is None:
            raise CastingError(
                f"Cannot flashback {card.name!r} — card has no flashback cost"
            )
        if card.owner is not None and card.owner is not player:
            raise CastingError(
                f"Cannot flashback {card.name!r} — owned by another player"
            )
    hand = player.zones[from_zone]
    permission = None
    if mode is CastMode.NORMAL and (
        not hand.contains(card) or from_zone != Zone.HAND
    ) and not getattr(card, "_castable_from_graveyard", False):
        permission = cast_permission(game, player, card)
        if permission is not None:
            hand = _holding_zone(game, card, permission['zone']) or hand
        elif from_zone != Zone.HAND:
            raise CastingError(
                f"Cannot cast {card.name!r} — no permission to cast it from {from_zone.value}"
            )
    if not hand.contains(card):
        raise CastingError(
            f"Cannot cast {card.name!r} — card not in {from_zone.value}"
        )

    from engine.stack import object_current_zone
    card.cast_from_zone = Zone(object_current_zone(game, card))
    card.controller = player
    if card.owner is None:
        card.owner = player

    # 4. Move card from its zone to the stack zone
    stack_zone = player.zones[Zone.STACK]
    hand.remove(card)
    stack_zone.add(card)

    # Clear any stale colors_spent from a prior cast before new payment.
    if hasattr(card, "colors_spent"):
        del card.colors_spent

    _announce_x(
        game, player, card,
        free=bool(permission and permission['life_cost']),
        reduction=_raw_cost_reduction(game, card, player, targets=[]),
    )

    # 4b. Announce how each additional cost will be paid (rule 601.2b). An
    #     alternative is offered only if its extra mana fits on top of some base
    #     cost the player could pay; reductions that depend on targets are not
    #     known yet, so a cost they alone make affordable is rejected at payment.
    from engine import additional_costs

    if permission and permission['life_cost']:
        announced_bases = [ManaCost()]
    else:
        announced_bases = (
            [card.flashback_cost]  # type: ignore[attr-defined]
            if mode is CastMode.FLASHBACK
            else [card.mana_cost, *card.alternative_costs(game)]
        )
    untargeted_reduction = _raw_cost_reduction(game, card, player, targets=[])

    # Mana abilities may still be activated while paying (rule 601.2g), so an
    # alternative counts as affordable when the pool plus one mana from each
    # untapped mana source could cover it; an exact shortfall is rejected at
    # payment like any other unpaid cost.
    untapped_sources = sum(
        1 for c in game.get_battlefield(player).get_all()
        if not getattr(c, 'is_tapped', False)
        and callable(getattr(c, 'get_mana_abilities', None)) and c.get_mana_abilities()
    )

    def _affordable(extra: ManaCost | None) -> bool:
        for base in announced_bases:
            total = additional_costs.plus(_with_x(base, card.x_value), extra)  # type: ignore[attr-defined]
            reduced = _apply_cost_reduction(total, min(untargeted_reduction, total.generic))
            if player.mana_pool.can_pay(reduced) or (
                untapped_sources and player.mana_pool.total() + untapped_sources >= reduced.cmc
            ):
                return True
        return False

    chosen_additional = additional_costs.announce(game, player, card, _affordable)
    if chosen_additional is None:
        stack_zone.remove(card)
        hand.add(card)
        raise CastingError(f"Cannot cast {card.name!r} — cannot pay its additional cost")
    added_mana = additional_costs.extra_mana(chosen_additional)

    # 5. Choose targets
    target_specs = card.get_targets(game)
    chosen_targets: list[Any] = []
    if target_specs:
        for spec in target_specs:
            target = _query_target(game, player, card, spec, exclude=chosen_targets)
            if target is None:
                # An optional "up to one target" that was declined or had no
                # legal candidate — it contributes no target.
                continue
            # Validate against filter_fn if the spec provides one (arity-aware,
            # so a dependent target is checked against the earlier targets).
            filter_fn = getattr(spec, "filter_fn", None)
            if filter_fn is not None and not _safe_filter(
                filter_fn, target, chosen_targets
            ):
                stack_zone.remove(card)
                hand.add(card)
                raise CastingError(
                    f"Cannot cast {card.name!r} — chosen target does not "
                    f"satisfy filter: {getattr(spec, 'description', '')}"
                )
            chosen_targets.append(target)

    # 5b. Protection check — reject targets that have protection from this
    #     spell (the T in DEBT).
    from engine.protection import has_protection_from

    for target in chosen_targets:
        if has_protection_from(target, card):
            # Rollback: move card from stack zone back to hand
            stack_zone.remove(card)
            hand.add(card)
            raise CastingError(
                f"Cannot cast {card.name!r} — target has protection from this spell"
            )

    # 5c. Capture the casting controller and each chosen target's zone-stint
    #     NOW — immediately after target selection and protection validation, and
    #     *before* any cost payment or on_cast side effect can move a target (rule
    #     601.2b/608.2b). A target that then leaves its selected zone and returns
    #     before resolution (a new object in the same Python instance) is rejected
    #     at resolution. Targets live on the StackObject, not the card.
    activation_context = capture_activation_context(
        game, card, player, chosen_targets
    )

    # 6. Mana check / payment (rollback on failure)
    # Ensure the card knows its controller so that cost_reduction() hooks
    # (e.g. Embercleave counting attacking creatures you control) see the
    # casting player, even for cards that were added to hand without an
    # explicit controller assignment.
    if card.controller is None:
        card.controller = player

    # Select the mana cost to pay (rule 601.2f):
    #   1. Enumerate the base costs — the normal mana cost and any alternative
    #      costs (rule 118.9) the card offers. An alternative *replaces* the
    #      normal cost outright (e.g. Blasphemous Edict's {B} for {3}{B}{B}); it
    #      is a separate base cost, not a reduction of the normal one.
    #   2. Apply cost reductions to each base cost afterward, clamped to that
    #      cost's own generic component so colored pips are never reduced.
    #   3. Keep only the candidates the player can actually pay, then choose
    #      among them (a Player Query fires only when more than one is payable).
    #   Flashback is itself an alternative cost (rule 702.34a), so a flashback
    #   cast pays only the flashback cost.
    raw_reduction = _raw_cost_reduction(game, card, player, targets=chosen_targets)
    candidate_costs = (
        [card.flashback_cost]  # type: ignore[attr-defined]
        if mode is CastMode.FLASHBACK
        else [card.mana_cost, *card.alternative_costs(game)]
    )
    pay_life = bool(permission and permission['life_cost'])
    life_amount = card.mana_cost.cmc if pay_life else 0
    base_costs = [additional_costs.plus(ManaCost(), added_mana)] if pay_life else [
        additional_costs.plus(_with_x(base, card.x_value), added_mana)  # type: ignore[attr-defined]
        for base in candidate_costs
    ]
    payable: list[tuple[int, ManaCost]] = []
    reduced_costs = [_apply_cost_reduction(base, raw_reduction) for base in base_costs]
    deferred = _mana_payment_window(game, player, card, reduced_costs)
    for index, base in enumerate(base_costs):
        clamped = min(raw_reduction, base.generic) if raw_reduction > 0 else 0
        reduced = _apply_cost_reduction(base, clamped) if clamped > 0 else base
        if player.mana_pool.can_pay(reduced):
            payable.append((index, reduced))

    if not payable or player.life < life_amount:
        # Rollback: move card from stack zone back to hand
        stack_zone.remove(card)
        hand.add(card)
        for trigger in deferred:
            game.stack.push(trigger)
        raise CastingError(f"Cannot cast {card.name!r} — insufficient mana")

    effective_cost = _choose_cost(game, player, card, payable)

    # TODO: Phase 3 — support player choice for generic mana payment to optimize Converge color count
    player.mana_pool.pay(effective_cost)
    if pay_life:
        from engine.game import lose_life
        lose_life(game, player, life_amount)

    # Store colors of mana spent on the card for mechanics like Converge
    # that care about the colors used to cast the spell.
    card.colors_spent = list(player.mana_pool.last_payment_colors)  # type: ignore[attr-defined]

    # 6b. The rest of the total cost — sacrifices, discards (rule 601.2h).
    additional_costs.pay_nonmana(game, player, card, chosen_additional)

    # 7. Call on_cast hook
    card.was_cast = True
    card.on_cast(game)

    # 7b. The spell has now become cast (rule 601.2i). Record it in the caster's
    #     authoritative per-turn instant/sorcery history exactly once — before the
    #     cast-triggered event fires, so a cast-triggered ability (Thousand-Year
    #     Storm) reading the history sees this spell already counted. The prior
    #     count returned here is the number of qualifying spells cast *before* this
    #     occurrence — carried onto this cast's StackObject below (``None`` for a
    #     non-qualifying spell).
    prior_qualifying_casts = _record_spell_cast(game, player, card)

    # 8. Build on_resolve callback and push StackObject with the context captured
    #    at target-selection time (step 5c). The StackObject is the stack
    #    representation of this one cast occurrence, so it carries the occurrence's
    #    immutable prior-cast count.
    stack_obj = StackObject(
        source=card,
        controller=player,
        targets=chosen_targets,
        on_resolve=lambda g: None,  # replaced below
        activation_context=activation_context,
        prior_qualifying_casts=prior_qualifying_casts,
        departure_zone=Zone.EXILE if mode is CastMode.FLASHBACK else None,
        is_spell=True,
        graveyard_departure_zone=departure_zone or (permission['departure_zone'] if permission else None),
    )

    def _on_resolve(g: GameState) -> None:
        _resolve_spell(g, card, player, stack_obj)

    stack_obj.on_resolve = _on_resolve
    game.stack.push(stack_obj)
    from engine.ward import trigger_ward
    trigger_ward(game, stack_obj)

    # 9. The spell is now on the stack (rule 601.2i complete). Fire the
    #    cast-triggered event so "whenever you cast …" abilities queue on top of
    #    it (rule 603.3) — after the StackObject exists so a subscriber (Storm)
    #    can correlate to this exact occurrence, and after the cast history is
    #    recorded so a cast-count reader sees this spell counted.
    _fire_spell_cast_event(game, player, card)
    _place_deferred_cast_triggers(game, stack_obj, deferred)
    return stack_obj


# ------------------------------------------------------------------
# Cast spell without paying mana cost (free-cast from any zone)
# ------------------------------------------------------------------


def cast_spell_free(
    game: GameState,
    player: Player,
    card: CardImpl,
    from_zone: Zone,
    *,
    mode: CastMode = CastMode.NORMAL,
    mana_value_limit: int | None = None,
) -> StackObject:
    """Cast *card* without paying its mana cost, using the stack.

    This is used by effects that allow casting from zones other than hand
    (e.g. exile) without paying mana costs — such as Etali, Primal Storm
    or cascade — and, with ``mode=CastMode.FLASHBACK``, for a flashback cast
    from the graveyard (the replay executor's attested graveyard→stack path).

    The cast *mode* is the caller's explicit statement of how the spell is
    being cast; this helper never infers it from card attributes.
    ``CastMode.FLASHBACK`` requires the card to be in **the casting player's
    own graveyard** with compatible ownership (rule 702.34a casts it from its
    owner's graveyard, so a card owned by another player is rejected) and to
    have a real ``flashback_cost``. Every FLASHBACK check runs **before any
    mutation** — a rejected mode claim leaves controller, owner, zones, cast
    history, and stack state exactly as they were. A validated flashback cast
    stamps ``departure_zone = Zone.EXILE`` on the cast's StackObject so the
    spell is exiled any time it leaves the stack (rule 702.34a) — on
    resolution and on being countered alike (see
    :func:`engine.stack.move_spell_off_stack`).

    Pipeline
    --------
    1. **can_cast** — ask the card whether it can legally be cast (same
       legality as :func:`cast_spell`, minus mana/timing constraints).
    2. Move *card* from *from_zone* to the stack zone.
    3. Choose targets (if applicable) with validation and protection check.
    4. Call ``on_cast`` hook.
    5. Push a :class:`StackObject` whose ``on_resolve`` callback handles
       resolution normally (permanents → battlefield, non-permanents →
       graveyard).

    No timing check is made and the mana cost is not paid, but additional
    costs still are (rule 118.9d).  The spell goes on the stack and can be
    responded to normally (e.g. countered).

    If targeting or other post-move checks fail, the card is rolled back
    to its source zone.

    Parameters:
        game: The current game state.
        player: The player casting the spell.
        card: The card to cast.
        from_zone: The zone the card is currently in. ``NORMAL`` mode keeps
            the historical permissiveness: the card may sit in any player's
            *from_zone* container (existing callers intentionally free-cast
            another player's card), and ownership is not constrained.
        mode: How the spell is being cast (keyword-only). Defaults to
            :attr:`CastMode.NORMAL`; pass :attr:`CastMode.FLASHBACK` for a
            flashback cast from the caster's own graveyard.

    Returns:
        The pushed :class:`StackObject` — the stack identity of this one cast
        occurrence (see :func:`cast_spell`).

    Raises:
        CastingError: If the card cannot be found in *from_zone*, legality
            checks fail, or *mode* is ``FLASHBACK`` for a card/zone/owner that
            does not support it.
    """
    # 0. Cast-mode legality — every FLASHBACK check runs before ANY mutation
    #    (including the controller/owner defaults below), so a rejected mode
    #    claim leaves all observable state untouched. The caller's mode claim
    #    is validated, never trusted blindly: flashback casts from the casting
    #    player's OWN graveyard (rule 702.34a — its owner's graveyard), needs a
    #    real flashback cost, and the caster must be able to own the cast
    #    (a card owned by someone else is not flashback-castable by *player*).
    if mode is CastMode.FLASHBACK:
        if from_zone != Zone.GRAVEYARD:
            raise CastingError(
                f"Cannot flashback {card.name!r} — flashback casts from the "
                f"graveyard, not {from_zone.name}"
            )
        if getattr(card, "flashback_cost", None) is None:
            raise CastingError(
                f"Cannot flashback {card.name!r} — card has no flashback cost"
            )
        owner = card.owner
        if owner is not None and owner is not player:
            raise CastingError(
                f"Cannot flashback {card.name!r} — owned by another player "
                f"(flashback casts from its owner's graveyard)"
            )
        if not player.zones[Zone.GRAVEYARD].contains(card):
            raise CastingError(
                f"Cannot flashback {card.name!r} — not in "
                f"{player.name!r}'s graveyard"
            )

    card.cast_from_zone = from_zone
    card.x_value = 0
    if hasattr(card, 'choose_cast_face'):
        card.choose_cast_face(game, player, mana_value_limit=mana_value_limit)
    if mana_value_limit is not None and card.mana_cost.cmc > mana_value_limit:
        raise CastingError('Spell exceeds the remaining mana-value allowance')
    # Ensure controller is set
    card.controller = player
    if card.owner is None:
        card.owner = player

    # 1. can_cast legality (same as cast_spell but skipping mana/timing)
    if not card.can_cast(game):
        raise CastingError(f"Cannot cast {card.name!r} — can_cast returned False")

    # 2. Locate card in source zone
    source_zone_container = player.zones[from_zone]
    if not source_zone_container.contains(card):
        # Try to find the card in any player's zone
        source_zone_container = None
        for p in game.players:
            z = p.zones[from_zone]
            if z.contains(card):
                source_zone_container = z
                break

    if source_zone_container is None or not source_zone_container.contains(card):
        raise CastingError(
            f"Cannot cast {card.name!r} — card not found in {from_zone.name}"
        )

    # Move card from source zone to stack zone
    stack_zone = player.zones[Zone.STACK]
    source_zone_container.remove(card)
    stack_zone.add(card)
    _announce_x(game, player, card, free=True)

    # 2b. A spell cast without paying its mana cost still owes its additional
    #     costs, mana included (rule 118.9d); announce them (rule 601.2b).
    from engine import additional_costs

    def _free_total(extra: ManaCost | None, targets: list[Any]) -> ManaCost:
        # The mana cost is replaced by zero, the additional costs are added and
        # cost reductions apply to the total, as for any cast (rule 601.2f).
        total = additional_costs.plus(ManaCost(), extra)
        reduction = _raw_cost_reduction(game, card, player, targets=targets)
        return _apply_cost_reduction(total, min(reduction, total.generic))

    chosen_additional = additional_costs.announce(
        game,
        player,
        card,
        lambda extra: player.mana_pool.can_pay(_free_total(extra, [])),
    )
    if chosen_additional is None:
        stack_zone.remove(card)
        source_zone_container.add(card)
        raise CastingError(f"Cannot cast {card.name!r} — cannot pay its additional cost")

    # 3. Choose targets (with rollback on failure)
    try:
        target_specs = card.get_targets(game)
        chosen_targets: list[Any] = []
        if target_specs:
            for spec in target_specs:
                target = _query_target(game, player, card, spec, exclude=chosen_targets)
                if target is None:
                    # An optional "up to one target" declined or with no legal
                    # candidate — it contributes no target.
                    continue
                # Validate against filter_fn if the spec provides one (arity-aware,
                # so a dependent target is checked against the earlier targets).
                filter_fn = getattr(spec, "filter_fn", None)
                if filter_fn is not None and not _safe_filter(
                    filter_fn, target, chosen_targets
                ):
                    raise CastingError(
                        f"Cannot cast {card.name!r} — chosen target does not "
                        f"satisfy filter: {getattr(spec, 'description', '')}"
                    )
                chosen_targets.append(target)

        # Protection check — reject targets that have protection from this spell
        from engine.protection import has_protection_from

        for target in chosen_targets:
            if has_protection_from(target, card):
                raise CastingError(
                    f"Cannot cast {card.name!r} — target has protection from this spell"
                )
    except Exception as exc:
        # Rollback: move card from stack zone back to source zone
        stack_zone.remove(card)
        source_zone_container.add(card)
        raise CastingError(str(exc)) from exc

    # 3b. Capture the casting controller + chosen target zone-stints NOW —
    #     immediately after target selection and protection validation, before
    #     the on_cast side effect (same discipline as cast_spell step 5c) — so a
    #     leave-and-return target is rejected at resolution on the free-cast path
    #     (cascade / Etali / exile casting).
    activation_context = capture_activation_context(
        game, card, player, chosen_targets
    )

    # 3c. Pay the additional costs (rule 601.2h), reduced now that the targets
    #     a reduction may depend on are known.
    total = _free_total(additional_costs.extra_mana(chosen_additional), chosen_targets)
    if not player.mana_pool.can_pay(total):
        stack_zone.remove(card)
        source_zone_container.add(card)
        raise CastingError(f"Cannot cast {card.name!r} — cannot pay its additional cost")
    if total.cmc:
        player.mana_pool.pay(total)
    additional_costs.pay_nonmana(game, player, card, chosen_additional)

    # 4. Call on_cast hook
    card.was_cast = True
    card.on_cast(game)

    # 4b. The free-cast spell has become cast (rule 601.2i); record it in the
    #     caster's per-turn instant/sorcery history exactly once, the same as the
    #     normal path — a spell cast without paying its cost (cascade, Etali, exile
    #     casting) still counts toward "spells you've cast this turn". Its prior
    #     count is carried onto this cast's StackObject below, exactly as on the
    #     normal path.
    prior_qualifying_casts = _record_spell_cast(game, player, card)

    # 4c. Stack-departure disposition. A FLASHBACK cast (explicitly selected
    #     by the caller and validated in step 0 — never inferred from the
    #     card's attributes) is exiled any time it leaves the stack (rule
    #     702.34a), so the override rides on this cast's StackObject (not the
    #     card) and is applied by move_spell_off_stack on resolution and on
    #     countering alike. Every other free cast — including a NORMAL-mode
    #     cast of a flashback-capable card from the graveyard, and casts from
    #     exile (cascade / Etali) — keeps the default disposition.
    departure_zone: Zone | None = (
        Zone.EXILE if mode is CastMode.FLASHBACK else None
    )

    # 5. Build on_resolve callback and push StackObject with the context captured
    #    at target-selection time (step 3b). This StackObject is the stack
    #    representation of this one cast occurrence and carries its immutable
    #    prior-cast count.
    stack_obj = StackObject(
        source=card,
        controller=player,
        targets=chosen_targets,
        on_resolve=lambda g: None,  # replaced below
        activation_context=activation_context,
        prior_qualifying_casts=prior_qualifying_casts,
        departure_zone=departure_zone,
        is_spell=True,
    )

    def _on_resolve(g: GameState) -> None:
        _resolve_spell(g, card, player, stack_obj)

    stack_obj.on_resolve = _on_resolve
    game.stack.push(stack_obj)
    from engine.ward import trigger_ward
    trigger_ward(game, stack_obj)

    # 6. The free-cast spell is on the stack (rule 601.2i complete). Fire the
    #    cast-triggered event, exactly as on the normal path — a spell cast
    #    without paying its cost still counts as cast, so cast-triggered
    #    abilities queue on top of it.
    _fire_spell_cast_event(game, player, card)
    return stack_obj


# ------------------------------------------------------------------
# Resolution (called when the stack pops)
# ------------------------------------------------------------------

def _resolve_spell(
    game: GameState,
    card: CardImpl,
    player: Player,
    stack_obj: StackObject,
) -> None:
    """Resolve *card* cast by *player*.

    1. Call ``card.on_resolve(game, targets=targets)``.
    2. Move the card off the stack through the shared departure primitive
       :func:`engine.stack.move_spell_off_stack`: a permanent type goes to the
       battlefield (via :func:`~engine.zones.move_to_zone`, which handles
       trigger/effect registration and the ETB event), an instant/sorcery to
       its owner's graveyard — unless the cast stamped a ``departure_zone``
       (a flashback cast is exiled instead, rule 702.34a). If ``on_resolve``
       already moved the card out of the stack zone, nothing moves twice.
    """

    # Read targets from the StackObject — the single source of truth.
    # Set chosen_targets on the card just before resolution so that
    # _get_chosen_target helpers (which read via getattr) work.
    #
    # First apply the shared zone-stint check (rule 608.2b): a target that left
    # its selected zone before resolution — whether it stayed gone or left and
    # returned (a new object in the same Python instance) — is nulled at its
    # position. Position is preserved so heterogeneous/dependent targets still
    # read by index; the card's own predicate re-check then handles a ``None`` (a
    # target still present but no longer satisfying its restriction is caught
    # there). A stack object with no captured context (``activation_context is
    # None``) passes through unchanged; spell copies carry their own context and
    # are revalidated the same way (see :func:`~engine.stack.copy_spell`).
    targets = stack_obj.targets
    if targets is not None:
        targets = stint_checked_targets(game, stack_obj.activation_context, targets)
        card.chosen_targets = targets  # type: ignore[attr-defined]

    card.on_resolve(game)

    # Depart the stack through the single shared primitive (the resolver has
    # already popped the StackObject): type-default destination, with the
    # cast's departure replacement (flashback → exile) applied there.
    default_zone = (
        Zone.BATTLEFIELD
        if card.card_types & _PERMANENT_TYPES
        else Zone.GRAVEYARD
    )
    move_spell_off_stack(game, stack_obj, default_zone, resolving=True)


# ------------------------------------------------------------------
# Play land (special action — does not use the stack)
# ------------------------------------------------------------------

def play_land(game: GameState, player: Player, land_card: CardImpl) -> None:
    """Play *land_card* from *player*'s hand onto the battlefield.

    Requirements (all must hold):

    * *land_card* has :attr:`CardType.LAND`.
    * *player* is the active player.
    * Current phase is a main phase.
    * The stack is empty.
    * ``player.land_plays_remaining > 0``.
    * The card is in the player's hand.

    On success the card moves from hand to battlefield and
    ``land_plays_remaining`` is decremented.

    Raises:
        CastingError: If any requirement is not met.
    """
    # Must be a land
    if CardType.LAND not in land_card.card_types:
        raise CastingError(
            f"Cannot play {land_card.name!r} as a land — not a land card"
        )

    # Sorcery-speed timing (active player, main phase, stack empty)
    if not is_sorcery_speed(game, player):
        raise CastingError(
            f"Cannot play land {land_card.name!r} — must be active player "
            "during main phase with empty stack"
        )

    # Land plays remaining
    if player.land_plays_remaining <= 0:
        raise CastingError(
            f"Cannot play land {land_card.name!r} — no land plays remaining"
        )

    # Card must be in hand
    hand = game.get_hand(player)
    origin = Zone.HAND
    if not hand.contains(land_card):
        permission = cast_permission(game, player, land_card)
        if permission:
            origin = permission['zone']
            hand = next((p.zones[origin] for p in game.players if p.zones[origin].contains(land_card)), hand)
    if not hand.contains(land_card):
        raise CastingError(
            f"Cannot play land {land_card.name!r} — card not in hand"
        )

    # Ensure owner/controller are set so move_to_zone routes correctly.
    if land_card.owner is None:
        land_card.owner = player
    land_card.controller = player

    # Lands never resolve from the stack, so on_resolve is invoked here —
    # same ordering as _resolve_spell (before the zone move) so "enters
    # tapped" / "as this enters" effects are in place when it arrives.
    land_card.on_resolve(game)

    # Move from hand to battlefield via move_to_zone, which fires
    # ENTERS_BATTLEFIELD and registers triggers/replacement effects.
    from engine.zones import move_to_zone
    move_to_zone(game, land_card, origin, Zone.BATTLEFIELD)

    # Decrement land plays
    player.land_plays_remaining -= 1


def resolve_top(game: GameState) -> None:
    """Resolve the top spell/ability on the stack (thin compatibility alias).

    Delegates to :func:`engine.stack.resolve_top_of_stack`, the single canonical
    resolution primitive, so this legacy entry point settles the game exactly
    like :func:`~engine.stack.priority_loop`: resolve one object, re-derive
    continuous effects, then run state-based actions to stability (re-deriving
    between passes). It previously ran SBAs *without* re-deriving continuous
    effects first; that divergence is gone. Retained (rather than removed)
    because it is part of the published engine import surface.
    """
    from engine.stack import resolve_top_of_stack

    resolve_top_of_stack(game)
