"""Card implementation for Burrog Banemaker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class BurrogBanemaker(Creature):
    """Burrog Banemaker."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Burrog Banemaker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault("subtypes", {"Frog", "Warlock"})
        kwargs.setdefault("keywords", Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Deathtouch\n{1}{B}: This creature gets +1/+1 until end of turn.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self
        activation_cost = ManaCost.parse("{1}{B}")

        def _cost(game: GameState, permanent: Creature) -> bool:  # noqa: ARG001
            controller = getattr(permanent, "controller", None)
            if controller is None or not controller.mana_pool.can_pay(activation_cost):
                return False
            controller.mana_pool.pay(activation_cost)
            return True

        def _effect(game: GameState) -> None:
            def _apply(game: GameState) -> None:  # noqa: ARG001
                source.modified_power += 1
                source.modified_toughness += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply,
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.apply_all(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{1}{B}: This creature gets +1/+1 until end of turn.",
            )
        ]
