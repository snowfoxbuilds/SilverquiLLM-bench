"""Card implementation for Orysa, Tide Choreographer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class OrysaTideChoreographer(Creature):
    """Orysa, Tide Choreographer — {4}{U} — Legendary Creature — Merfolk Bard.

    Costs {3} less if creatures you control have total toughness 10 or greater.
    When Orysa enters, draw two cards.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Orysa, Tide Choreographer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Merfolk", "Bard"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        super().__init__(**kwargs)
        self.legendary = True

    def get_effective_cost(self, game: "GameState") -> ManaCost:
        """Return effective cost, reduced by {3} if total toughness >= 10."""
        controller = self.controller or self.owner
        battlefield = game.get_battlefield(controller)
        total_toughness = 0
        for obj in battlefield.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                t = getattr(obj, "toughness", None)
                if t is None:
                    t = getattr(obj, "base_toughness", 0)
                total_toughness += t

        base = self.mana_cost
        if total_toughness >= 10:
            new_generic = max(0, base.generic - 3)
            return ManaCost(generic=new_generic, pips=dict(base.pips), x_count=base.x_count, hybrid=list(base.hybrid))
        return base

    def on_enter_battlefield(self, game: "GameState") -> None:
        """When Orysa enters, draw two cards."""
        from engine.game import draw_card
        controller = self.controller or self.owner
        draw_card(game, controller)
        draw_card(game, controller)
