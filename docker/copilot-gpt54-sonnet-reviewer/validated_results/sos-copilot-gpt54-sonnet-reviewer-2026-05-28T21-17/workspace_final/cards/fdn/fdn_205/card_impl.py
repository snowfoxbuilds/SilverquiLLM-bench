"""Card implementation for Wardens of the Cycle (FDN #205 slot).

Demonstrates converge / mana-color tracking.  Wardens of the Cycle is a
multicolor creature whose enter-the-battlefield ability creates a number
of 1/1 Saproling tokens equal to the number of distinct colors of mana
spent to cast it (converge mechanic).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class WardensOfTheCycle(Creature):
    """Wardens of the Cycle — {3}{B}{G} — 4/4 — Treefolk.

    Converge — When this creature enters, create a 1/1 green Saproling
    creature token for each color of mana spent to cast it.

    FDN collector number 205 (reference slot for converge/mana-color tracking).
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wardens of the Cycle")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{G}"))
        kwargs.setdefault("subtypes", {"Treefolk"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Converge — When this creature enters, create a 1/1 green "
            "Saproling creature token for each color of mana spent to cast it.",
        )
        super().__init__(**kwargs)
        # Tracks the number of distinct colors spent when cast.
        self.colors_spent: int = 0

    def on_resolve(self, game: "GameState") -> None:
        """ETB: create Saproling tokens equal to distinct colors of mana spent."""
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Use colors_spent attribute (set during casting or by test setup).
        colors_spent = getattr(self, "colors_spent", 0)
        count = len(colors_spent) if isinstance(colors_spent, (list, tuple, set, frozenset)) else int(colors_spent)

        for _ in range(count):
            token = Creature(
                name="Saproling",
                subtypes={"Saproling"},
                base_power=1,
                base_toughness=1,
            )
            create_token(game, controller, token)
