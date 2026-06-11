"""Card implementation for Eager Glyphmage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _create_inkling_token() -> Creature:
    token = Creature(
        name="Inkling",
        subtypes={"Inkling"},
        keywords=Keyword.FLYING,
        base_power=1,
        base_toughness=1,
    )
    token.colors = {Color.WHITE, Color.BLACK}  # type: ignore[attr-defined]
    return token


class EagerGlyphmage(Creature):
    """Eager Glyphmage."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Eager Glyphmage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, create a 1/1 white and black Inkling creature token "
            "with flying.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        create_token(game, controller, _create_inkling_token())
