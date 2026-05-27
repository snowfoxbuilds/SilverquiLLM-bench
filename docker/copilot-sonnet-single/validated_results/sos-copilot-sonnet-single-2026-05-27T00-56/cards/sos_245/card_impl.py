"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Color, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.card import CardImpl
    from engine.game_state import GameState
    from engine.player import Player


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — Legendary Creature — Elder Dragon — 5/5.

    Affinity for creatures (This spell costs {1} less to cast for each
    creature you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast have affinity for creatures.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("colors", {Color.BLACK, Color.GREEN})
        kwargs.setdefault(
            "rules_text",
            (
                "Affinity for creatures (This spell costs {1} less to cast for each "
                "creature you control.)\n"
                "Flying, deathtouch\n"
                "Instant and sorcery spells you cast have affinity for creatures."
            ),
        )
        super().__init__(**kwargs)
        self._ambient_reducer: Any = None

    def _count_controlled_creatures(self, game: "GameState") -> int:
        """Return the number of creatures the controller controls."""
        controller = getattr(self, "controller", None)
        if controller is None:
            return 0
        bf = game.get_battlefield(controller)
        return sum(
            1 for obj in bf.get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        )

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures — return number of creatures controller controls."""
        return self._count_controlled_creatures(game)

    def register_triggers(self, game: "GameState") -> None:
        """Register the static ability granting instant/sorcery spells affinity
        for creatures."""
        source = self

        def _affinity_reducer(
            game: "GameState",
            card: "CardImpl",
            controller: "Player",
        ) -> int:
            """Return creature count if card is an instant/sorcery cast by
            Witherbloom's controller, else 0."""
            # Guard: only apply reduction when Witherbloom is on the battlefield.
            witherbloom_controller = getattr(source, "controller", None)
            if witherbloom_controller is None:
                return 0
            bf = game.get_battlefield(witherbloom_controller)
            if source not in bf.get_all():
                return 0
            if controller is not witherbloom_controller:
                return 0
            # Only applies to instants and sorceries
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return 0
            # Count creatures controlled by the same player
            bf = game.get_battlefield(controller)
            return sum(
                1 for obj in bf.get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )

        self._ambient_reducer = _affinity_reducer
        ambient_reducers = getattr(game, "ambient_cost_reducers", None)
        if ambient_reducers is not None:
            ambient_reducers.append(_affinity_reducer)
