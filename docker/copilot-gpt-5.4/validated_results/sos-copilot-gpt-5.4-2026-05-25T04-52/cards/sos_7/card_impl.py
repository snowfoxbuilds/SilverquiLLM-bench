"""Card implementation for Antiquities on the Loose."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, ManaCost, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class AntiquitiesOnTheLoose(Sorcery):
    """Antiquities on the Loose."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Antiquities on the Loose")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Create two 2/2 red and white Spirit creature tokens. Then if this spell was "
            "cast from anywhere other than your hand, put a +1/+1 counter on each Spirit "
            "you control.\nFlashback {4}{W}{W}",
        )
        super().__init__(**kwargs)
        self.flashback_cost = ManaCost.parse("{4}{W}{W}")

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        for _ in range(2):
            token = Creature(
                name="Spirit",
                base_power=2,
                base_toughness=2,
                subtypes={"Spirit"},
                owner=controller,
                controller=controller,
            )
            token.colors = {Color.RED, Color.WHITE}
            create_token(game, controller, token)

        if getattr(self, "cast_from_zone", Zone.HAND) == Zone.HAND:
            return

        for permanent in game.get_battlefield(controller).get_all():
            if "Spirit" not in getattr(permanent, "subtypes", set()):
                continue
            if get_colors(permanent) != {Color.RED, Color.WHITE} and "Spirit" not in getattr(permanent, "subtypes", set()):
                continue
            permanent.plus_one_counters += 1
            if hasattr(permanent, "_base_plus_one_counters"):
                permanent._base_plus_one_counters = permanent.plus_one_counters
