"""Card implementation for Witherbloom, the Balancer (SOS #245)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — 5/5 — Legendary Creature — Elder Dragon.

    Affinity for creatures (This spell costs {1} less to cast for each creature
    you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast have affinity for creatures.

    SOS collector number 245.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for each "
            "creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Cost-reduction: Affinity for creatures (own spell)
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Return {1} per creature the controller controls on the battlefield."""
        controller = self.controller
        if controller is None:
            return 0
        bf = game.get_battlefield(controller)
        count = sum(
            1
            for permanent in bf.get_all()
            if CardType.CREATURE in getattr(permanent, "card_types", set())
        )
        return count

    # ------------------------------------------------------------------
    # Grants affinity for creatures to instants and sorceries
    # ------------------------------------------------------------------

    def get_spell_cost_reduction(
        self,
        game: "GameState",
        card: Any,
        controller: "Player",
    ) -> int:
        """Return creature-count reduction for instants/sorceries cast by controller.

        Returns 0 for non-instant/non-sorcery spells.
        This is called by get_cost_reduction() in engine/casting.py when scanning
        the battlefield for cost-granting permanents.
        """
        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return 0

        # Count creatures the controller controls on the battlefield.
        bf = game.get_battlefield(controller)
        count = sum(
            1
            for permanent in bf.get_all()
            if CardType.CREATURE in getattr(permanent, "card_types", set())
        )
        return count

    # ------------------------------------------------------------------
    # Trigger registration (no-op — the effect is a static continuous ability
    # handled by get_cost_reduction scanning the battlefield)
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register Witherbloom's triggered abilities.

        The affinity-granting ability is a static continuous effect that
        is implemented by engine/casting.py scanning the battlefield for
        permanents with get_spell_cost_reduction().  No actual triggers are
        needed here.
        """
