"""The Priority Query — what a player does with priority (see ADR-017).

Before a player receives priority the game is settled: continuous effects are
re-derived and state-based actions performed (CR 117.5). The engine then asks
the player, through one Player Query, for the action to take — the set of
choices a user interface would offer a real player at that moment:

* an OBJECT option for every spell they may begin casting (from their hand, or
  from their graveyard under flashback or a cast permission) and every land they
  may play;
* an ABILITY option for every ability they may begin activating, mana and
  loyalty abilities included;
* declining (``min=0``) passes priority.

Options follow timing, zone and cast-permission rules; costs, targets and
``can_cast`` conditions are not pre-checked, so an action they forbid is
offered and then rejected. The engine picks the zone and cast permission and
each card's :meth:`~engine.card.CardImpl.cast_offers` decides which of its
faces may begin casting at this moment, so a multi-face card judges timing by
the face being cast (CR 715.3a). Every option carries the predefined class it
stands for in its ``printed`` attr. The engine, not the player, turns the
chosen option into its own cast, land play or activation, so the casting call
is not part of any test contract.

Offering an illegal option is allowed; letting it take effect is not. When the
chosen action fails, the game is rolled back to the beginning of the Priority
Query (:mod:`engine.attempts`, :mod:`engine.rollback`), the player who owns the
rejection hears the :class:`~engine.decisions.InvalidPlayerChoiceError`, and
the same query is asked again (CR 733.2).
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable

from engine.abilities import (
    AbilityError,
    ActivatedAbilityInstance,
    LoyaltyAbilityInstance,
    _has_activated_loyalty_this_turn,
    activate_ability,
)
from engine.card import LoyaltyAbility, ManaAbility
from engine.casting import (
    CastingError,
    CastMode,
    is_sorcery_speed,
    permitted_cards,
    play_land,
)
from engine.decisions import Decision, GameRef, InvalidPlayerChoiceError, PlayerDecision
from engine import attempts
from engine.attempts import AttemptContext
from engine.queries import PRIORITY_WINDOW, PlayerQuery, ask
from engine.refs_registry import card_ref_pairs
from engine.stack import settle_after_resolution
from engine.types import CardType, Zone
from engine.zones import IllegalMoveError

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player

Action = Callable[[], Any]

# The failures that make a chosen action illegal under the rules.
REJECTED_ACTION_ERRORS = (CastingError, AbilityError, IllegalMoveError, InvalidPlayerChoiceError)


def take_priority(game: GameState, player: Player) -> bool:
    """Ask *player* for an action and take it; return ``True`` if they passed.

    The action is an attempt (:mod:`engine.attempts`) whose rejection boundary
    is the beginning of the Priority Query: a rejected action is rolled back
    there, the player who owns the rejection hears it through
    :meth:`~engine.player.Player.on_attempt_rejected`, and the same query is
    asked again — the player may take the action another way, take another,
    or pass. Declining is a pass, the player's own answer.
    """
    context = AttemptContext(game, "priority", actor=player)
    try:
        with attempts.active(context):
            return _attempt_action(game, player, context)
    finally:
        # Taken, passed or ended by an error: the action is over.
        player.on_action_ended(context)


def _attempt_action(game: GameState, player: Player, context: AttemptContext) -> bool:
    while True:
        # CR 117.5: the game settles before a player receives priority, also
        # when an action leaves the stack empty or pays a cost that kills.
        settle_after_resolution(game)
        if game.is_game_over:
            # CR 104.1: nobody receives priority in a game that has ended.
            return True
        context.begin_try()
        query, actions = priority_query(game, player)
        answer = ask(player, query)
        context.query, context.answer = query, answer
        if not answer.selected:
            return True
        context.action = answer.selected[0]
        try:
            result = actions[answer.selected[0]]()
        except REJECTED_ACTION_ERRORS as exc:
            context.boundary.restore()
            context.reject(as_choice_error(exc))
            # What the hook changed outside its rollback-exempt state is not
            # part of the next try (see Player.on_attempt_rejected).
            context.boundary.restore()
            continue
        context.taken, context.result = True, result
        return False


def as_choice_error(exc: Exception) -> InvalidPlayerChoiceError:
    """``exc`` as the ``InvalidPlayerChoiceError`` a player hears, caused by it."""
    if isinstance(exc, InvalidPlayerChoiceError):
        return exc
    error = InvalidPlayerChoiceError(str(exc))
    error.__cause__ = exc
    return error


def priority_query(
    game: GameState, player: Player
) -> tuple[PlayerQuery, dict[PlayerDecision, Action]]:
    """The Priority Query for *player* and the action behind each option."""
    seat = _seat(game, player)
    actions: dict[PlayerDecision, Action] = {}
    for obj, zone, action in _cast_and_play_offers(game, player):
        actions[game.refs.object_decision(obj, zone=zone.value, controller_seat=seat)] = action
    for source in _controlled_permanents(game, player):
        for index, ability in enumerate(activatable_abilities(source, game)):
            if _functions_from(ability) is Zone.BATTLEFIELD and _may_begin_activating(
                game, player, source, ability
            ):
                actions[_ability_decision(game, seat, source, index, ability)] = (
                    _activation(game, player, source, ability)
                )
    for source in game.get_hand(player).get_all():
        for index, ability in enumerate(activatable_abilities(source, game)):
            if _functions_from(ability) is Zone.HAND and _may_begin_activating(
                game, player, source, ability
            ):
                decision = _ability_decision(game, seat, source, index, ability, in_zone=Zone.HAND)
                actions[decision] = _activation(game, player, source, ability)
    source = Decision.player(
        ref=GameRef(player=frozenset({("seat", seat)}), ability=frozenset({PRIORITY_WINDOW})),
        seat=seat,
        name=player.name,
    )
    options = tuple(actions)
    query = PlayerQuery(
        source=(source,),
        prompt="Priority: choose an action, or decline to pass",
        options=options,
        min=0,
        max=min(1, len(options)),
    )
    return query, actions


def activatable_abilities(card: Any, game: GameState) -> list[Any]:
    """*card*'s activated abilities, then the mana abilities it lists only in
    ``get_mana_abilities()``, then its loyalty abilities — the order behind an
    ABILITY option's ``index``."""
    abilities = list(_call(card.get_activated_abilities, game))
    get_mana = getattr(card, "get_mana_abilities", None)
    if get_mana is not None:
        abilities += [a for a in _call(get_mana, game) if not any(a is b for b in abilities)]
    get_loyalty = getattr(card, "get_loyalty_abilities", None)
    if get_loyalty is not None:
        abilities += list(_call(get_loyalty, game))
    return abilities


def _call(getter: Callable[..., Any], game: GameState) -> Any:
    """Call an ability getter, passing ``game`` to the ones that take it."""
    return getter(game) if inspect.signature(getter).parameters else getter()


def _seat(game: GameState, player: Player) -> int:
    return next(seat for seat, p in enumerate(game.players) if p is player)


def _cast_and_play_offers(game: GameState, player: Player):
    """``(presented object, zone, action)`` for each spell and land on offer."""
    for card in game.get_hand(player).get_all():
        if CardType.LAND in card.card_types:
            if is_sorcery_speed(game, player) and player.land_plays_remaining > 0:
                yield card, Zone.HAND, (lambda c=card: play_land(game, player, c))
        else:
            for obj, action in card.cast_offers(game, player, Zone.HAND, CastMode.NORMAL):
                yield obj, Zone.HAND, action
    offered = []
    for card in game.get_graveyard(player).get_all():
        mode = _graveyard_cast_mode(player, card)
        if mode is not None:
            offered.append(card)
            for obj, action in card.cast_offers(game, player, Zone.GRAVEYARD, mode):
                yield obj, Zone.GRAVEYARD, action
    # Cards a cast permission lets the player cast or play from another zone.
    for card, zone in permitted_cards(game, player):
        if zone is Zone.HAND or any(card is other for other in offered):
            continue
        if CardType.LAND in card.card_types:
            if is_sorcery_speed(game, player) and player.land_plays_remaining > 0:
                yield card, zone, (lambda c=card: play_land(game, player, c))
        else:
            for obj, action in card.cast_offers(game, player, zone, CastMode.NORMAL):
                yield obj, zone, action


def _graveyard_cast_mode(player: Player, card: Any) -> CastMode | None:
    """How *card* may be cast from *player*'s graveyard, if at all."""
    # Set by an effect that grants "you may cast it from your graveyard" (Zul Ashur).
    if getattr(card, "_castable_from_graveyard", False):
        return CastMode.NORMAL
    owner = getattr(card, "owner", None)
    if getattr(card, "flashback_cost", None) is not None and owner in (None, player):
        return CastMode.FLASHBACK
    return None


def _controlled_permanents(game: GameState, player: Player) -> list[Any]:
    permanents = []
    for holder in game.players:
        for card in game.get_battlefield(holder).get_all():
            controller = getattr(card, "controller", None) or holder
            if controller is player:
                permanents.append(card)
    return permanents


def _may_begin_activating(game: GameState, player: Player, source: Any, ability: Any) -> bool:
    if isinstance(ability, LoyaltyAbility):
        return is_sorcery_speed(game, player) and not _has_activated_loyalty_this_turn(
            source, getattr(game, "turn_number", 0)
        )
    if getattr(source, "_cant_activate", False):
        return False
    can_activate = getattr(ability, "can_activate", None)
    return can_activate is None or bool(can_activate(game, source, player))


def _functions_from(ability: Any) -> Zone:
    return getattr(ability, "zone", None) or Zone.BATTLEFIELD


def _ability_decision(
    game: GameState, seat: int, source: Any, index: int, ability: Any,
    *, in_zone: Zone = Zone.BATTLEFIELD,
) -> PlayerDecision:
    zone = in_zone.value
    instance = game.refs.instance_id(source, zone)
    attrs: dict[str, Any] = {"source": instance, "index": index}
    printed = getattr(ability, "printed", None)
    if printed is not None:
        attrs["printed"] = printed
    ref = GameRef(
        player=frozenset({("seat", seat)}),
        zone=frozenset({("name", zone)}),
        card=card_ref_pairs(source),
        object=frozenset({("instance", instance)}),
        ability=frozenset({("index", index)}),
    )
    return Decision.ability(ref=ref, **attrs)


def _activation(game: GameState, player: Player, source: Any, ability: Any) -> Action:
    if isinstance(ability, LoyaltyAbility):
        instance: Any = LoyaltyAbilityInstance(
            source=source,
            controller=player,
            loyalty_cost=ability.loyalty_cost,
            effect=ability.effect,
            description=ability.description,
            targeting=ability.targeting,
            printed=getattr(ability, "printed", None),
        )
    else:
        is_mana = isinstance(ability, ManaAbility)
        instance = ActivatedAbilityInstance(
            source=source,
            controller=player,
            cost=ability.cost,
            effect=ability.mana_produced if is_mana else ability.effect,
            is_mana_ability=is_mana,
            description=ability.description,
            targeting=getattr(ability, "targeting", None),
            can_activate=getattr(ability, "can_activate", None),
            printed=getattr(ability, "printed", None),
        )
    return lambda: activate_ability(game, player, instance)
