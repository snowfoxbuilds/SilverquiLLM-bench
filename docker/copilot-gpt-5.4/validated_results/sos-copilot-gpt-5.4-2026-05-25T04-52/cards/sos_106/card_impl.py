"""Card implementation for Ancestral Anger."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class AncestralAnger(Sorcery):
    """Ancestral Anger."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ancestral Anger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        kwargs.setdefault(
            "rules_text",
            "Target creature gains trample and gets +X/+0 until end of turn, where X is 1 plus "
            "the number of cards named Ancestral Anger in your graveyard.\nDraw a card.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        target = getattr(self, "chosen_targets", [None])[0]
        if controller is None:
            return

        graveyard = game.get_graveyard(controller).get_all()
        bonus = 1 + sum(1 for card in graveyard if getattr(card, "name", "") == "Ancestral Anger")

        if isinstance(target, Creature) and target.is_on_battlefield(game):
            def _apply_power(_game: GameState, *, creature: Creature = target, amount: int = bonus) -> None:
                creature.modified_power += amount

            def _apply_trample(_game: GameState, *, creature: Creature = target) -> None:
                creature.keywords |= Keyword.TRAMPLE

            game.effect_manager.add(
                ContinuousEffect(
                    source=self,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply_power,
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.add(
                ContinuousEffect(
                    source=self,
                    layer=Layer.ABILITY,
                    apply=_apply_trample,
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.apply_all(game)

        draw_card(game, controller)
