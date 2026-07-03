"""Card implementation for Fix What's Broken."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Artifact, Creature, Sorcery
from benchmarks.sos.workspace.engine.casting import CastingError
from benchmarks.sos.workspace.engine.types import ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player


class FixWhatsBroken(Sorcery):
    """Fix What's Broken."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fix What's Broken")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        super().__init__(**kwargs)
        self.x_value = 0

    def can_cast(self, game: GameState) -> bool:  # noqa: ARG002
        controller = self.controller
        if controller is None:
            return True
        return controller.life >= max(0, int(getattr(self, "x_value", 0)))

    def pay_additional_cast_costs(
        self,
        game: GameState,  # noqa: ARG002
        player: Player,
        from_zone: Zone,  # noqa: ARG002
    ) -> None:
        x_value = max(0, int(getattr(self, "x_value", 0)))
        if player.life < x_value:
            raise CastingError(f"Cannot cast {self.name!r} — insufficient life for X")
        player.life -= x_value

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        x_value = max(0, int(getattr(self, "x_value", 0)))
        for card in list(game.get_graveyard(controller).get_all()):
            mana_cost = getattr(card, "mana_cost", None)
            if mana_cost is None or mana_cost.cmc != x_value:
                continue
            if not isinstance(card, (Artifact, Creature)):
                continue
            card.controller = controller
            move_to_zone(game, card, Zone.GRAVEYARD, Zone.BATTLEFIELD)
