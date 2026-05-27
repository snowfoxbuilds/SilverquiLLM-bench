"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Loyalty 3.

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any, source: Any = None, **kwargs: Any) -> None:
            """Surveil 2."""
            pw.loyalty += 1
            controller = pw.controller
            if controller is None:
                return
            choices = kwargs.get("choices", {})
            put_to_gy = choices.get("put_to_graveyard", [])
            library = game.get_library(controller)
            graveyard = game.get_graveyard(controller)
            for card in put_to_gy:
                if library.contains(card):
                    library.remove(card)
                    graveyard.add(card)

        def _minus1(game: Any, source: Any = None, **kwargs: Any) -> None:
            """Any number of target players each discard a card."""
            pw.loyalty -= 1
            targets = kwargs.get("targets", [])
            for player in targets:
                hand = game.get_hand(player)
                cards = hand.get_all()
                if cards:
                    # Discard the first card (or let the player choose)
                    card = cards[0]
                    hand.remove(card)
                    graveyard = game.get_graveyard(player)
                    graveyard.add(card)

        def _minus2(game: Any, source: Any = None, **kwargs: Any) -> None:
            """Return target creature card with mana value 3 or less from graveyard to battlefield."""
            pw.loyalty -= 2
            targets = kwargs.get("targets", [])
            controller = pw.controller
            if not targets or controller is None:
                return
            target = targets[0]
            graveyard = game.get_graveyard(controller)
            if graveyard.contains(target):
                graveyard.remove(target)
                battlefield = game.get_battlefield(controller)
                battlefield.add(target)

        def _minus7(game: Any, source: Any = None, **kwargs: Any) -> None:
            """Flip five coins. Target opponent skips X turns."""
            pw.loyalty -= 7
            targets = kwargs.get("targets", [])
            coin_results = kwargs.get("coin_results", [False] * 5)
            if not targets:
                return
            opponent = targets[0]
            heads_count = sum(1 for r in coin_results if r)
            if heads_count > 0:
                current = getattr(opponent, "turns_to_skip", 0)
                opponent.turns_to_skip = current + heads_count

        return [
            LoyaltyAbility(loyalty_cost=1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1, description="−1: Any number of target players each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2, description="−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7, description="−7: Flip five coins. Target opponent skips their next X turns."),
        ]

    def get_valid_targets_for_ability(self, game: Any, ability_index: int) -> list[Any]:
        """Return valid targets for the given ability index."""
        if ability_index == 2:
            # −2: creature cards with mana value 3 or less in controller's graveyard
            controller = self.controller
            if controller is None:
                return []
            graveyard = game.get_graveyard(controller)
            valid = []
            for card in graveyard.get_all():
                if CardType.CREATURE in getattr(card, "card_types", set()):
                    mana_cost = getattr(card, "mana_cost", None)
                    if mana_cost is not None and mana_cost.cmc <= 3:
                        valid.append(card)
            return valid
        return []
