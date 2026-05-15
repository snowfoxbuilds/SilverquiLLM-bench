"""Card implementation for Seismic Rupture."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class SeismicRupture(Sorcery):
    """Seismic Rupture — {2}{R} — Sorcery.

    Seismic Rupture deals 2 damage to each creature without flying.

    FDN collector number 205.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Seismic Rupture")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Seismic Rupture deals 2 damage to each creature without flying.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Deal 2 damage to each creature without flying."""
        from engine.game import deal_damage

        creatures: list = []
        for player in game.players:
            for perm in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(perm, "card_types", set()):
                    kw = getattr(perm, "keywords", Keyword(0))
                    if not (kw & Keyword.FLYING):
                        creatures.append(perm)

        for creature in creatures:
            deal_damage(game, self, creature, 2)
