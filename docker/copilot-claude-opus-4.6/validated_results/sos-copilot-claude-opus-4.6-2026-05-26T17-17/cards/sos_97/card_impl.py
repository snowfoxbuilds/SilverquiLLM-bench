"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Loyalty 3.
    +1: Surveil 2.
    -1: Any number of target players each discard a card.
    -2: Return target creature card with MV 3 or less from graveyard to battlefield.
    -7: Flip five coins. Target opponent skips next X turns (X = heads).
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", {"Ral"})
        super().__init__(**kwargs)

    @property
    def is_legendary(self) -> bool:
        return Supertype.LEGENDARY in self.supertypes

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Surveil 2."""
            controller = pw.controller
            if controller is None:
                return
            library = game.get_library(controller)
            graveyard = game.get_graveyard(controller)
            # Surveil 2: look at top 2, put each into graveyard or back on top/bottom
            # Simplified: put top 2 into graveyard (default surveil choice)
            cards_to_surveil = library.top(2)
            for card in cards_to_surveil:
                library.remove(card)
                graveyard.add(card)

        def _minus1(game: Any) -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard
            targets = getattr(pw, "chosen_targets", []) or []
            for player in targets:
                hand = game.get_hand(player)
                cards = hand.get_all()
                if cards:
                    discard(game, player, cards[0])

        def _minus2(game: Any) -> None:
            """Return target creature with MV<=3 from graveyard to battlefield."""
            from engine.game import move_to_zone
            from engine.types import Zone
            targets = getattr(pw, "chosen_targets", []) or []
            controller = pw.controller
            for target in targets:
                graveyard = game.get_graveyard(controller)
                if graveyard.contains(target):
                    graveyard.remove(target)
                    bf = game.get_battlefield(controller)
                    bf.add(target)
                    target.controller = controller

        def _minus7(game: Any) -> None:
            """Flip five coins. Target opponent skips X turns."""
            import random
            targets = getattr(pw, "chosen_targets", []) or []
            heads = sum(random.choice([0, 1]) for _ in range(5))
            # Skip turns not fully implemented in engine
            for target in targets:
                if hasattr(target, 'skip_turns'):
                    target.skip_turns = getattr(target, 'skip_turns', 0) + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1, description="-1: Each target player discards."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2, description="-2: Return creature MV<=3 from graveyard."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7, description="-7: Flip coins, skip turns."),
        ]

    def activate_loyalty_ability(self, game: "GameState", ability_index: int) -> None:
        """Activate the loyalty ability at the given index."""
        abilities = self.get_loyalty_abilities()
        if ability_index < 0 or ability_index >= len(abilities):
            return
        ability = abilities[ability_index]
        # Pay loyalty cost
        new_loyalty = self.loyalty + ability.loyalty_cost
        if new_loyalty < 0:
            return
        self.loyalty = new_loyalty
        # Execute effect
        ability.effect(game)
