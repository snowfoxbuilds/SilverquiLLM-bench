"""Card implementation for Essenceknit Scholar."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class EssenceknitScholar(Creature):
    """Essenceknit Scholar — {B}{B/G}{G} — Creature — Dryad Warlock (3/1).

    When this creature enters, create a 1/1 black and green Pest creature
    token with "Whenever this token attacks, you gain 1 life."
    At the beginning of your end step, if a creature died under your control
    this turn, draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Essenceknit Scholar")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}{B/G}{G}"))
        kwargs.setdefault("subtypes", {"Dryad", "Warlock"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)

    def on_enter_battlefield(self, game: "GameState") -> None:
        """ETB: create a 1/1 black and green Pest creature token."""
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        token = Creature(
            name="Pest",
            subtypes={"Pest"},
            base_power=1,
            base_toughness=1,
        )
        create_token(game, controller, token)

    def on_end_step(self, game: "GameState") -> None:
        """If a creature died under your control this turn, draw a card."""
        from engine.game import draw_card

        controller = self.controller
        if controller is None:
            return

        # Check if a creature died under controller's control this turn
        creatures_died = getattr(game, "creatures_died_this_turn", [])
        died_for_controller = any(
            entry[0] is controller for entry in creatures_died
        ) if creatures_died else False

        if died_for_controller:
            draw_card(game, controller)
