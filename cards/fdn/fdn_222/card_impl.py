"""Card implementation for Ghalta, Primal Hunger."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class GhaltaPrimalHunger(Creature):
    """Ghalta, Primal Hunger — {10}{G}{G} — 12/12 — Legendary Elder Dinosaur.

    This spell costs {X} less to cast, where X is the total power of
    creatures you control.
    Trample.

    FDN collector number 222.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ghalta, Primal Hunger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}{G}{G}"))
        kwargs.setdefault("subtypes", {"Elder", "Dinosaur"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 12)
        kwargs.setdefault("base_toughness", 12)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {X} less to cast, where X is the total "
            "power of creatures you control.\nTrample",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce cost by total power of creatures you control."""
        controller = self.controller
        if controller is None:
            return 0
        bf = game.get_battlefield(controller)
        total_power = 0
        for obj in bf.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                total_power += getattr(obj, "power", getattr(obj, "base_power", 0))
        return total_power
