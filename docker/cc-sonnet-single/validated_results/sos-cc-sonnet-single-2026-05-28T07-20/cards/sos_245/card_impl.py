"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — Legendary Creature — Elder Dragon 5/5.

    Flying, deathtouch
    Affinity for creatures (this spell costs {1} less to cast for each
    creature you control).
    Instant and sorcery spells you cast have affinity for creatures.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, deathtouch\n"
            "Affinity for creatures\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def _count_controller_creatures(self, game: "GameState") -> int:
        """Return the number of creatures controlled by self.controller on the battlefield."""
        ctrl = getattr(self, "controller", None)
        if ctrl is None:
            return 0
        bf = game.get_battlefield(ctrl)
        return sum(
            1
            for card in bf.get_all()
            if CardType.CREATURE in getattr(card, "card_types", set())
        )

    def cost_reduction(self, game: "GameState") -> int:
        """Return the number of creatures the controller controls (affinity for creatures)."""
        return self._count_controller_creatures(game)

    def get_affinity_cost_reduction(self, spell: Any, game: "GameState") -> int:
        """Return the creature-count cost reduction for instant/sorcery spells.

        If *spell* is an instant or sorcery controlled by the same controller
        as this permanent, returns the number of creatures that controller
        controls. Otherwise returns 0.

        Parameters:
            spell: The spell card to evaluate.
            game: The current game state.
        """
        # Guard: uncontrolled Witherbloom grants nothing.
        ctrl = getattr(self, "controller", None)
        if ctrl is None:
            return 0

        # Only grant to spells controlled by the same controller.
        spell_ctrl = getattr(spell, "controller", None)
        if spell_ctrl is not ctrl:
            return 0

        # Only instants and sorceries qualify.
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return 0

        return self._count_controller_creatures(game)
