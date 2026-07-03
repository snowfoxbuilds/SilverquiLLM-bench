"""Card implementation for Cost of Brilliance."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import LosesLifeTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter, draw_card
from benchmarks.sos.workspace.engine.player import Player
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class CostOfBrilliance(Sorcery):
    """Cost of Brilliance."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cost of Brilliance")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Target player draws two cards and loses 2 life. Put a +1/+1 counter on "
            "up to one target creature.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Player),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="up to one target creature",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: GameState) -> None:
        chosen = getattr(self, "chosen_targets", [])
        target_player = chosen[0] if len(chosen) > 0 else None
        target_creature = chosen[1] if len(chosen) > 1 else None

        if isinstance(target_player, Player):
            draw_card(game, target_player)
            draw_card(game, target_player)
            target_player.life -= 2
            game.trigger_manager.fire_event(
                game,
                LosesLifeTriggeredEvent(player=target_player, amount=2),
            )

        if isinstance(target_creature, Creature) and target_creature.is_on_battlefield(game):
            add_counter(game, target_creature, "+1/+1")
