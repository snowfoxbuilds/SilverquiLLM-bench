"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from random import getrandbits
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.game import discard
from engine.types import CardType, ManaCost, Supertype, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _resolved_targets(source: Any) -> list[Any]:
    """Return the card's resolution-time targets as a list."""
    targets = getattr(source, "_resolve_targets", None)
    if targets is not None:
        return list(targets)

    target = getattr(source, "_resolve_target", None)
    if target is None:
        return []
    return [target]


def _is_in_zone(game: "GameState", player: "Player", zone: Zone, card: Any) -> bool:
    """Return whether *card* is currently in *player*'s *zone*."""
    return player.zones[zone].contains(card)


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus_one(game: "GameState") -> None:
            controller = pw.controller
            if controller is None:
                return

            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]
            top_cards = library.top(2)
            for card in reversed(top_cards):
                if controller.choose_yes_no(
                    f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
                ):
                    library.remove(card)
                    graveyard.add(card)

        def _minus_one(game: "GameState") -> None:
            for player in _resolved_targets(pw):
                if player is None or not hasattr(player, "zones"):
                    continue
                hand = game.get_hand(player)
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                chosen = player.choose_card(cards_in_hand, f"Discard a card for {pw.name}")
                if chosen is not None and hand.contains(chosen):
                    discard(game, player, chosen)

        def _minus_two(game: "GameState") -> None:
            controller = pw.controller
            target = getattr(pw, "_resolve_target", None)
            if controller is None or target is None:
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if getattr(getattr(target, "mana_cost", None), "cmc", 0) > 3:
                return
            if not _is_in_zone(game, controller, Zone.GRAVEYARD, target):
                return

            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus_seven(game: "GameState") -> None:
            controller = pw.controller
            target = getattr(pw, "_resolve_target", None)
            if controller is None or target is None or target is controller:
                return

            heads = 0
            for _ in range(5):
                flip = game.flip_coin() if hasattr(game, "flip_coin") else bool(getrandbits(1))
                if flip:
                    heads += 1

            if heads > 0 and hasattr(game, "skip_next_turn"):
                game.skip_next_turn(target, heads)

        return [
            LoyaltyAbility(loyalty_cost=1, effect=_plus_one, description="+1: Surveil 2."),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus_one,
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus_two,
                description="−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus_seven,
                description="−7: Flip five coins. Target opponent skips their next X turns, where X is the number of heads.",
            ),
        ]
