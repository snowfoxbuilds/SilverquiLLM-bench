"""Additional costs a spell's caster must pay (rules 118.8, 601.2b, 601.2f–h).

A card prints an additional cost as one or more alternatives — "sacrifice a
creature or pay {3}{B}". The caster announces which alternative they will pay
while casting (rule 601.2b), its mana joins the total cost (rule 601.2f), and
everything is paid together (rule 601.2h). A spell cast without paying its
mana cost still requires its additional costs (rule 118.9d).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


@dataclass(frozen=True)
class CostOption:
    """One way to pay an additional cost: extra mana, a sacrifice or discards."""

    mana: ManaCost | None = None
    sacrifice: Callable[[Any], bool] | None = None
    discard: int = 0


@dataclass(frozen=True)
class AdditionalCost:
    """An additional cost printed on a card, as the alternatives it allows."""

    printed: type
    options: tuple[CostOption, ...]


def creature(obj: Any) -> bool:
    """Sacrifice filter for "sacrifice a creature"."""
    return CardType.CREATURE in getattr(obj, "card_types", ())


def plus(cost: ManaCost, extra: ManaCost | None) -> ManaCost:
    """*cost* with *extra* added to it (rule 601.2f)."""
    if extra is None:
        return cost
    pips = dict(cost.pips)
    for mana_type, count in extra.pips.items():
        pips[mana_type] = pips.get(mana_type, 0) + count
    return ManaCost(
        generic=cost.generic + extra.generic,
        pips=pips,
        x_count=cost.x_count + extra.x_count,
        hybrid=[*cost.hybrid, *extra.hybrid],
    )


def _sacrifice_candidates(game: GameState, player: Player, option: CostOption) -> list[Any]:
    """The permanents *player* could sacrifice for *option*: those they control
    on any battlefield, since a permanent another player gained control of stays
    in its owner's zone (rule 701.21a)."""
    if option.sacrifice is None:
        return []
    return [
        obj
        for zone_owner in game.players
        for obj in game.get_battlefield(zone_owner).get_all()
        if (getattr(obj, "controller", None) or zone_owner) is player and option.sacrifice(obj)
    ]


def _feasible(
    game: GameState,
    player: Player,
    option: CostOption,
    affordable: Callable[[ManaCost | None], bool],
) -> bool:
    if option.sacrifice is not None and not _sacrifice_candidates(game, player, option):
        return False
    if option.discard and len(game.get_hand(player).get_all()) < option.discard:
        return False
    return affordable(option.mana)


def announce(
    game: GameState,
    player: Player,
    card: Any,
    affordable: Callable[[ManaCost | None], bool],
) -> list[CostOption] | None:
    """Announce how each of *card*'s additional costs will be paid (rule 601.2b).

    Only alternatives the caster can pay are offered; *affordable* says whether
    an alternative's extra mana can be paid on top of the spell's cost. Returns
    the chosen alternative per cost, or ``None`` when some cost has none payable.
    """
    from engine.decisions import Decision
    from engine.queries import PlayerQuery, ask

    chosen: list[CostOption] = []
    for cost in card.additional_costs(game):
        payable = [
            (index, option)
            for index, option in enumerate(cost.options)
            if _feasible(game, player, option, affordable)
        ]
        if not payable:
            return None
        if len(payable) == 1:
            chosen.append(payable[0][1])
            continue
        from engine.casting import _source_decision

        query = PlayerQuery(
            source=(_source_decision(game, card),),
            prompt="Choose how to pay the additional cost",
            options=tuple(
                Decision.ability(index=index, printed=cost.printed) for index, _ in payable
            ),
            min=1,
            max=1,
        )
        answer = ask(player, query)
        index = dict(answer.selected[0].attrs)["index"]
        chosen.append(dict(payable)[index])
    return chosen


def extra_mana(chosen: list[CostOption]) -> ManaCost | None:
    """The mana the chosen alternatives add to the total cost."""
    total: ManaCost | None = None
    for option in chosen:
        if option.mana is not None:
            total = plus(total or ManaCost(), option.mana)
    return total


def pay_nonmana(game: GameState, player: Player, card: Any, chosen: list[CostOption]) -> None:
    """Pay the sacrifices and discards of the chosen alternatives (rule 601.2h).

    A cost that can't be paid raises :class:`~engine.casting.CastingError`, so
    the cast is rejected and rolled back rather than going ahead unpaid.
    """
    from engine.card_queries import choose_object
    from engine.casting import CastingError
    from engine.game import discard, sacrifice

    for option in chosen:
        if option.sacrifice is not None:
            candidates = _sacrifice_candidates(game, player, option)
            if not candidates:
                raise CastingError(f"Cannot cast {card.name!r} — nothing to sacrifice")
            victim = choose_object(
                game, player, candidates, "Choose a permanent to sacrifice", source_card=card
            )
            sacrifice(game, player, victim)
            # A replacement effect may send it somewhere other than the
            # graveyard; what matters is that it left the battlefield.
            if any(game.get_battlefield(p).contains(victim) for p in game.players):
                raise CastingError(f"Cannot cast {card.name!r} — the sacrifice was not made")
        for _ in range(option.discard):
            hand = game.get_hand(player).get_all()
            if not hand:
                raise CastingError(f"Cannot cast {card.name!r} — no card to discard")
            discarded = choose_object(
                game, player, hand, "Choose a card to discard", source_card=card
            )
            discard(game, player, discarded)
