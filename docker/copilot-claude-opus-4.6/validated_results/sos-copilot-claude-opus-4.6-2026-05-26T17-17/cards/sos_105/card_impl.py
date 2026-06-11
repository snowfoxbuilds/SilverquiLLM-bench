"""Card implementation for Withering Curse."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery, Creature
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitheringCurse(Sorcery):
    """Withering Curse — {1}{B}{B} — Sorcery.

    All creatures get -2/-2 until end of turn.
    Infusion — If you gained life this turn, destroy all creatures instead.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Withering Curse")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Resolve: -2/-2 to all creatures, or destroy all if life was gained."""
        controller = self.controller
        life_gained = getattr(controller, "life_gained_this_turn", 0) if controller else 0

        all_creatures = []
        for player in game.players:
            bf = game.get_battlefield(player)
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    all_creatures.append((obj, player))

        if life_gained > 0:
            # Infusion: destroy all creatures
            for creature, player in all_creatures:
                bf = game.get_battlefield(player)
                if bf.contains(creature):
                    bf.remove(creature)
                    gy = game.get_graveyard(getattr(creature, "owner", player))
                    gy.add(creature)
        else:
            # Base mode: all creatures get -2/-2 until end of turn
            for creature, player in all_creatures:
                current_p = getattr(creature, "_temp_power_bonus", 0)
                current_t = getattr(creature, "_temp_toughness_bonus", 0)
                creature._temp_power_bonus = current_p - 2
                creature._temp_toughness_bonus = current_t - 2
