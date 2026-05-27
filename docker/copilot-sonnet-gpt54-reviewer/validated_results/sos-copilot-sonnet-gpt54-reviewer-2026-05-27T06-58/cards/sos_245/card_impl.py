"""Card implementation for Witherbloom, the Balancer."""

# UNVERIFIED: full cast integration at reduced cost not tested end-to-end

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — Legendary Creature — Elder Dragon — 5/5.

    Affinity for creatures (This spell costs {1} less to cast for each
    creature you control.)
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
            "Affinity for creatures (This spell costs {1} less to cast for "
            "each creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Return the number of creatures the controller controls.

        Affinity for creatures: this spell costs {1} less for each creature
        you control.
        """
        controller = self.controller
        if controller is None:
            return 0
        bf = game.get_battlefield(controller)
        return sum(
            1
            for obj in bf.get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        )

    def register_triggers(self, game: "GameState") -> None:
        """Register the continuous effect that grants affinity for creatures
        to instant and sorcery spells cast by the controller."""
        source = self

        def _witherbloom_reducer(
            g: "GameState", card: Any, controller: Any
        ) -> int:
            """Grants affinity for creatures to instant/sorcery spells."""
            # Only applies when Witherbloom is on the battlefield
            bf = g.get_battlefield(controller)
            if not bf.contains(source):
                return 0
            # Only applies to the controller of Witherbloom
            if source.controller is not controller:
                return 0
            # Only for instants and sorceries
            card_types = getattr(card, "card_types", set())
            if (
                CardType.INSTANT not in card_types
                and CardType.SORCERY not in card_types
            ):
                return 0
            # Count creatures controller controls
            return sum(
                1
                for obj in bf.get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )

        # Tag the closure with this card's id so we can deduplicate.
        _witherbloom_reducer._source_id = id(source)  # type: ignore[attr-defined]

        # Register in the game's global cost reducers list, removing any
        # previously registered reducer from *this* Witherbloom first so that
        # blink / re-entry does not stack duplicate closures.
        if not hasattr(game, "_global_cost_reducers"):
            game._global_cost_reducers = []
        game._global_cost_reducers = [
            r
            for r in game._global_cost_reducers
            if getattr(r, "_source_id", None) != id(source)
        ]
        game._global_cost_reducers.append(_witherbloom_reducer)
