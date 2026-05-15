"""Card implementation for Day of Judgment."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class DayOfJudgment(Sorcery):
    """Day of Judgment — {2}{W}{W} — Sorcery.

    Destroy all creatures.

    FDN collector number 140.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Day of Judgment")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{W}"))
        kwargs.setdefault("rules_text", "Destroy all creatures.")
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Destroy all creatures."""
        from engine.game import destroy

        creatures = []
        for player in game.players:
            bf = game.get_battlefield(player)
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    creatures.append(obj)
        for creature in creatures:
            destroy(game, creature)
