"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_REANIMATE_MAX_MV = 3
_COINS_FLIPPED = 5


def _is_creature_card(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


def _mana_value(obj: Any) -> int:
    cost = getattr(obj, "mana_cost", None)
    return cost.cmc if cost is not None else 0


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X
        is the number of coins that came up heads.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "-1: Any number of target players each discard a card.\n"
            "-2: Return target creature card with mana value 3 or less from "
            "your graveyard to the battlefield.\n"
            "-7: Flip five coins. Target opponent skips their next X turns, "
            "where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)
        self.colors = {"B"}

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: "GameState") -> None:
            from engine.game import surveil

            controller = pw.controller
            if controller is not None:
                surveil(game, controller, 2)

        def _minus1(game: "GameState") -> None:
            from engine.game import discard

            for player in _target_players(pw):
                hand = player.zones[Zone.HAND].get_all()
                if not hand:
                    continue
                card = player.choose_card(hand, "discard a card")
                if card is None or not player.zones[Zone.HAND].contains(card):
                    card = hand[-1]
                discard(game, player, card)

        def _minus2(game: "GameState") -> None:
            from engine.zones import move_to_zone

            controller = pw.controller
            target = getattr(pw, "_resolve_target", None)
            if controller is None or target is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(target):
                return
            if not _is_creature_card(target) or _mana_value(target) > _REANIMATE_MAX_MV:
                return
            target.controller = controller
            target.owner = getattr(target, "owner", None) or controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            from engine.game import flip_coins

            controller = pw.controller
            target = getattr(pw, "_resolve_target", None)
            if controller is None or target is None:
                return
            heads = flip_coins(game, controller, _COINS_FLIPPED)
            if heads <= 0:
                return
            try:
                seat = game.players.index(target)
            except ValueError:
                return
            game.skip_turns[seat] = game.skip_turns.get(seat, 0) + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1,
                description="-1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description=(
                    "-2: Return target creature card with mana value 3 or less "
                    "from your graveyard to the battlefield."
                ),
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description=(
                    "-7: Flip five coins. Target opponent skips their next X "
                    "turns, where X is the number of coins that came up heads."
                ),
            ),
        ]


def _target_players(pw: Any) -> list[Any]:
    """Normalize the chosen target player(s) for the −1 ability."""
    chosen = getattr(pw, "_resolve_target", None)
    if chosen is None:
        return []
    if isinstance(chosen, (list, tuple, set)):
        return [p for p in chosen if p is not None]
    return [chosen]
