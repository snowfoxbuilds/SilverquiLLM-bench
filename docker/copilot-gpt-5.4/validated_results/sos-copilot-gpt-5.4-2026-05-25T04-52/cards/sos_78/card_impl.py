"""Card implementation for Decorum Dissertation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.events import LosesLifeTriggeredEvent
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.player import Player
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class DecorumDissertation(Sorcery):
    """Decorum Dissertation."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Decorum Dissertation")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{B}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Target player draws two cards and loses 2 life.\nParadigm",
        )
        super().__init__(**kwargs)
        self.paradigm_enabled = True

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Player),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        chosen = getattr(self, "chosen_targets", [])
        target_player = chosen[0] if chosen else None
        if not isinstance(target_player, Player):
            return
        draw_card(game, target_player)
        draw_card(game, target_player)
        target_player.life -= 2
        game.trigger_manager.fire_event(
            game,
            LosesLifeTriggeredEvent(player=target_player, amount=2),
        )
