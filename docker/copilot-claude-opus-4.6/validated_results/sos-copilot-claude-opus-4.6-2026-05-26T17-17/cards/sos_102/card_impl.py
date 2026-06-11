"""Card implementation for Tragedy Feaster."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TragedyFeaster(Creature):
    """Tragedy Feaster — {2}{B}{B} — Creature — Demon.

    7/6, Trample, Ward—Discard a card.
    Infusion — At the beginning of your end step, sacrifice a permanent
    unless you gained life this turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tragedy Feaster")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}{B}"))
        kwargs.setdefault("keywords", Keyword.TRAMPLE | Keyword.WARD)
        kwargs.setdefault("subtypes", {"Demon"})
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 6)
        super().__init__(**kwargs)

    def on_end_step(self, game: "GameState") -> None:
        """Infusion: sacrifice a permanent unless you gained life this turn."""
        controller = self.controller
        life_gained = getattr(controller, "life_gained_this_turn", 0)
        if life_gained > 0:
            return

        bf = game.get_battlefield(controller)
        permanents = bf.get_all()
        if not permanents:
            return

        to_sacrifice = None
        for perm in permanents:
            if perm is not self:
                to_sacrifice = perm
                break
        if to_sacrifice is None:
            to_sacrifice = self

        bf.remove(to_sacrifice)
        graveyard = game.get_graveyard(controller)
        graveyard.add(to_sacrifice)
