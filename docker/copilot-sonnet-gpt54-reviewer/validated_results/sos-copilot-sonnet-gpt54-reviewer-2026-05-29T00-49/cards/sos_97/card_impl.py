"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    +1: Surveil 2.
    -1: Any number of target players each discard a card.
    -2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.
    -7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.

    SOS collector number 97.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault(
            "supertypes",
            frozenset({Supertype.LEGENDARY}),
        )
        kwargs.setdefault("subtypes", frozenset({"Ral"}))
        super().__init__(**kwargs)

        # Override hooks for deterministic testing
        # _surveil_to_graveyard: list of cards to put in graveyard during surveil
        self._surveil_to_graveyard: list[Any] | None = None
        # _resolve_targets: list of players for -1 ability
        self._resolve_targets: list[Any] | None = None
        # _resolve_target: single target (creature or opponent) for -2 / -7
        self._resolve_target: Any = None
        # _coin_flip_results: list of bool for deterministic coin flips
        self._coin_flip_results: list[bool] | None = None

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=self._plus_one,
                description="Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=self._minus_one,
                description="Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=self._minus_two,
                description=(
                    "Return target creature card with mana value 3 or less "
                    "from your graveyard to the battlefield."
                ),
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=self._minus_seven,
                description=(
                    "Flip five coins. Target opponent skips their next X turns, "
                    "where X is the number of coins that came up heads."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # Ability implementations
    # ------------------------------------------------------------------

    def _plus_one(self, game: "GameState") -> None:
        """Surveil 2: look at top 2 cards, put any into graveyard, rest on top."""
        controller = self.controller
        if controller is None:
            return

        library = controller.zones[Zone.LIBRARY]

        # Look at top 2 cards of library
        top_cards = library.top(2)

        # Determine which cards to put in graveyard
        # Test hook: if _surveil_to_graveyard is set, use that list
        # Real path: keep all on top (default — no graveyard decisions without player input)
        if self._surveil_to_graveyard is not None:
            to_graveyard = list(self._surveil_to_graveyard)
        else:
            # Default real path: player keeps all cards on top (no graveyard)
            to_graveyard = []

        # Move specified cards from library top to graveyard using proper zone move
        for card in to_graveyard:
            if library.contains(card):
                move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

    def _minus_one(self, game: "GameState") -> None:
        """Any number of target players each discard a card."""
        from engine.game import discard as _discard

        targets = self._resolve_targets if self._resolve_targets is not None else []
        for player in targets:
            hand = player.zones[Zone.HAND]
            hand_cards = hand.get_all()
            if hand_cards:
                # Discard the first card via proper discard path (fires zone-change hooks)
                card_to_discard = hand_cards[0]
                _discard(game, player, card_to_discard)

    def _minus_two(self, game: "GameState") -> None:
        """Return target creature card with CMC <= 3 from graveyard to battlefield."""
        controller = self.controller
        if controller is None:
            return

        target = self._resolve_target
        if target is None:
            return

        # Validate: must be a creature with CMC <= 3
        mana_cost = getattr(target, "mana_cost", None)
        cmc = mana_cost.cmc if mana_cost is not None else 0
        if cmc > 3:
            return

        # Check it's a creature
        card_types = getattr(target, "card_types", set())
        if CardType.CREATURE not in card_types:
            return

        # Move from graveyard to battlefield using proper zone-move path (fires ETB triggers)
        graveyard = controller.zones[Zone.GRAVEYARD]
        if graveyard.contains(target):
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

    def _minus_seven(self, game: "GameState") -> None:
        """Flip 5 coins; target opponent skips next X turns (X = heads)."""
        # Perform coin flips
        if self._coin_flip_results is not None:
            flips = list(self._coin_flip_results[:5])
            # Pad with random if fewer than 5 provided
            while len(flips) < 5:
                flips.append(random.random() < 0.5)
        else:
            flips = [random.random() < 0.5 for _ in range(5)]

        heads = sum(1 for f in flips if f)

        # Target opponent skips next X turns
        target = self._resolve_target
        if target is None:
            # Default: use first opponent
            controller = self.controller
            if controller is not None:
                opponents = [p for p in game.players if p is not controller]
                if opponents:
                    target = opponents[0]

        if target is not None and heads > 0:
            current_skips = getattr(target, "turns_to_skip", 0)
            target.turns_to_skip = current_skips + heads
