"""Card implementation for Vicious Rivalry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ViciousRivalry(Sorcery):
    """Vicious Rivalry — {2}{B}{G} — Sorcery.

    As an additional cost to cast this spell, pay X life.
    Destroy all artifacts and creatures with mana value X or less.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vicious Rivalry")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}{G}"))
        super().__init__(**kwargs)
        self.x_value: int = 0

    def on_resolve(self, game: "GameState") -> None:
        """Destroy all artifacts and creatures with mana value X or less."""
        from engine.game import destroy

        x = self.x_value
        to_destroy = []

        for player in game.players:
            bf = game.get_battlefield(player)
            for obj in bf.get_all():
                card_types = getattr(obj, "card_types", set())
                if CardType.CREATURE in card_types or CardType.ARTIFACT in card_types:
                    mc = getattr(obj, "mana_cost", None)
                    mv = mc.cmc if mc is not None else 0
                    if mv <= x:
                        to_destroy.append(obj)

        for obj in to_destroy:
            destroy(game, obj)
