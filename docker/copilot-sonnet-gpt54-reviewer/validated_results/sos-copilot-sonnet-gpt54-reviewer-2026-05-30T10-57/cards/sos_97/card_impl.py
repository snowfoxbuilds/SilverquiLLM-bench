"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral [3].

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
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from "
            "your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, "
            "where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def activate_plus_one(self, game: "GameState") -> None:
        """[+1]: Surveil 2 — look at top 2 cards; put any into graveyard, rest back on top."""
        self.loyalty += 1
        controller = self.controller
        if controller is None:
            return
        library = controller.zones[Zone.LIBRARY]
        top_cards = library.top(2)
        # Simplified surveil: cards are "seen" but put back on top by default.
        # Full implementation would allow the controller to choose which to graveyard.
        # The engine's DeterministicPlayer does not support free-form surveil choices.
        # ENGINE_NOTE: surveil_cards stored for UI/scripted-player extension.
        self._surveil_pending = top_cards  # available for inspection in tests

    def activate_minus_one(self, game: "GameState", targets: list[Any] | None = None) -> None:
        """[-1]: Any number of target players each discard a card."""
        self.loyalty -= 1
        from engine.game import discard
        if not targets:
            return
        for player in targets:
            hand = player.zones[Zone.HAND].get_all()
            if hand:
                # Discard the first card in hand (deterministic; full impl uses player choice).
                discard(game, player, hand[0])

    def activate_minus_two(self, game: "GameState", target: Any = None) -> None:
        """[-2]: Return creature with MV ≤ 3 from graveyard to battlefield."""
        self.loyalty -= 2
        if target is None:
            return
        controller = self.controller
        if controller is None:
            controller = getattr(target, "owner", None)
        owner = getattr(target, "owner", controller)
        # Move from graveyard to battlefield.
        if owner is not None and target in owner.zones[Zone.GRAVEYARD].get_all():
            owner.zones[Zone.GRAVEYARD].remove(target)
            target.controller = controller
            game.get_battlefield(controller).add(target)

    def activate_minus_seven(
        self, game: "GameState", opponent: Any = None, forced_heads: int | None = None
    ) -> None:
        """[-7]: Flip 5 coins; opponent skips X turns (X = heads)."""
        self.loyalty -= 7
        if opponent is None:
            return
        if forced_heads is not None:
            heads = forced_heads
        else:
            heads = sum(random.randint(0, 1) for _ in range(5))
        opponent.turns_to_skip = getattr(opponent, "turns_to_skip", 0) + heads
