"""Card implementation for Hare Apparent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class HareApparent(Creature):
    """Hare Apparent — {1}{W} — 2/2 — Rabbit Noble.

    When this creature enters, create a number of 1/1 white Rabbit creature
    tokens equal to the number of other creatures you control named
    Hare Apparent.
    A deck can have any number of cards named Hare Apparent.

    FDN collector number 15.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hare Apparent")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Rabbit", "Noble"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, create a number of 1/1 white Rabbit "
            "creature tokens equal to the number of other creatures you "
            "control named Hare Apparent.\n"
            "A deck can have any number of cards named Hare Apparent.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: create Rabbit tokens equal to other Hare Apparents you control."""
        from benchmarks.sos.workspace.engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Count other creatures named "Hare Apparent" on our battlefield
        battlefield = game.get_battlefield(controller)
        count = 0
        for obj in battlefield.get_all():
            if obj is self:
                continue
            if getattr(obj, "name", "") == "Hare Apparent":
                count += 1

        # Create that many 1/1 Rabbit tokens
        for _ in range(count):
            token = Creature(
                name="Rabbit",
                subtypes={"Rabbit"},
                base_power=1,
                base_toughness=1,
            )
            create_token(game, controller, token)
