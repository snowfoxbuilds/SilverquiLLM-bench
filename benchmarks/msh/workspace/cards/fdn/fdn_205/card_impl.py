"""Card implementation for Seismic Rupture (FDN #205)."""

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
        """Deal 2 damage to each creature without flying.

        This is untargeted mass damage — every creature without flying on
        every battlefield is hit, regardless of controller. Damage goes
        through :func:`engine.game.deal_damage` so protection and any
        deals-damage triggers fire correctly.
        """
        from engine.game import deal_damage

        for player in game.players:
            for obj in list(game.get_battlefield(player).get_all()):
                if CardType.CREATURE not in getattr(obj, "card_types", set()):
                    continue
                if Keyword.FLYING in getattr(obj, "keywords", Keyword(0)):
                    continue
                deal_damage(game, self, obj, 2)
