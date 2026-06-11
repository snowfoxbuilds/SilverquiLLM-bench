"""Card implementation for Rabid Attack."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class RabidAttack(Instant):
    """{1}{B} Instant — Until end of turn, any number of target creatures you
    control each get +1/+0 and gain "When this creature dies, draw a card."
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rabid Attack")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        targets = getattr(self, "chosen_targets", []) or []
        for creature in targets:
            # Grant +1/+0
            creature.modified_power = getattr(creature, "modified_power", creature.base_power) + 1
            # Grant dies trigger (draw a card)
            if not hasattr(creature, "dies_triggers"):
                creature.dies_triggers = []
            creature.dies_triggers.append(self._make_dies_draw_trigger(creature))

    def _make_dies_draw_trigger(self, creature: Any) -> Any:
        """Create a death trigger that draws a card for the creature's controller."""
        controller = creature.controller

        def _draw_on_death(game: "GameState") -> None:
            from engine.game import draw_card
            draw_card(game, controller)

        return _draw_on_death
