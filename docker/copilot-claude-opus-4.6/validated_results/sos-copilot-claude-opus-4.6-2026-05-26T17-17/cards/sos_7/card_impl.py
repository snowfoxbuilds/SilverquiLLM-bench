"""Card implementation for Antiquities on the Loose."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class AntiquitiesOnTheLoose(Sorcery):
    """{1}{W}{W} Sorcery — Create two 2/2 Spirit tokens. Flashback {4}{W}{W}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Antiquities on the Loose")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("keywords", Keyword.FLASHBACK)
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import add_counter, create_token

        controller = self.controller
        if controller is None:
            return

        # Create two 2/2 red and white Spirit creature tokens
        for _ in range(2):
            token = Creature(
                name="Spirit",
                subtypes={"Spirit"},
                base_power=2,
                base_toughness=2,
                owner=controller,
                controller=controller,
            )
            create_token(game, controller, token)

        # If cast from anywhere other than hand, +1/+1 on each Spirit you control
        cast_from = getattr(self, "cast_from_zone", Zone.HAND)
        if cast_from != Zone.HAND:
            bf = game.get_battlefield(controller)
            for obj in bf.get_all():
                if isinstance(obj, Creature) and "Spirit" in getattr(obj, "subtypes", set()):
                    add_counter(game, obj, "+1/+1", 1)
