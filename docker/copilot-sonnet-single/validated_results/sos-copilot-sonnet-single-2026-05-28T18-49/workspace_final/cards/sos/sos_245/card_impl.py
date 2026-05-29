"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — 5/5 — Legendary Creature — Elder Dragon.

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
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for each "
            "creature you control.)\nFlying, deathtouch\nInstant and sorcery spells "
            "you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures: reduce cost by 1 per creature you control."""
        controller = self.controller
        if controller is None:
            return 0
        bf = game.get_battlefield(controller)
        return sum(
            1 for obj in bf.get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        )

    def register_triggers(self, game: "GameState") -> None:
        """Register the global cost reducer for instants/sorceries when on battlefield."""
        source = self

        def _global_reducer(game: Any, card: Any, controller: Any) -> int:
            """Grant affinity-for-creatures to instants/sorceries cast by controller."""
            # Only applies while Witherbloom is on the battlefield
            on_bf = any(
                game.get_battlefield(p).contains(source)
                for p in game.players
            )
            if not on_bf:
                return 0
            # Only for instants/sorceries controlled by Witherbloom's controller
            wb_controller = getattr(source, "controller", None)
            if controller is not wb_controller:
                return 0
            # Only for instants and sorceries (not Witherbloom itself)
            ctypes = getattr(card, "card_types", set())
            if CardType.INSTANT not in ctypes and CardType.SORCERY not in ctypes:
                return 0
            # Count creatures the controller controls
            bf = game.get_battlefield(controller)
            return sum(
                1 for obj in bf.get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )

        # Register on the game's global cost reducer list
        if not hasattr(game, "_global_cost_reducers"):
            game._global_cost_reducers = []

        # Only register if not already present
        for existing in game._global_cost_reducers:
            if getattr(existing, "__closure__", None) and any(
                c.cell_contents is source
                for c in existing.__closure__
                if hasattr(c, "cell_contents")
            ):
                return  # Already registered

        game._global_cost_reducers.append(_global_reducer)
        # Store reference to remove on unregistration
        if not hasattr(self, "_global_reducer_fn"):
            self._global_reducer_fn = _global_reducer

    def register_replacement_effects(self, game: "GameState") -> None:
        """Unregister global reducer on leave-battlefield."""
        # No standard replacement effect needed; cleanup via triggers.
        pass

