"""Card implementation for Startled Relic Sloth."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class StartledRelicSloth(Creature):
    """Startled Relic Sloth — {2}{R}{W} — Creature — Sloth Beast — 4/4.

    Trample, lifelink
    At the beginning of combat on your turn, exile up to one target card
    from a graveyard.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Startled Relic Sloth")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}{W}"))
        kwargs.setdefault("subtypes", {"Sloth", "Beast"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE | Keyword.LIFELINK)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def on_begin_combat(self, game: "GameState", target: Any = None) -> None:
        """At beginning of combat, exile up to one target card from a graveyard."""
        if target is None:
            return  # "up to one" — chose zero targets

        # Find the card in any graveyard and exile it
        for player in game.players:
            gy = game.get_graveyard(player)
            if gy.contains(target):
                gy.remove(target)
                exile = game.get_exile(player)
                exile.add(target)
                return
