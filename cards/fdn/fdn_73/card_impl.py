"""Card implementation for Tragic Banshee."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class TragicBanshee(Creature):
    """Tragic Banshee — {4}{B} — 5/3 — Spirit.

    Morbid — When this creature enters, target creature an opponent controls
    gets -1/-1 until end of turn. If a creature died this turn, that creature
    gets -13/-13 until end of turn instead.

    FDN collector number 73.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tragic Banshee")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}"))
        kwargs.setdefault("subtypes", {"Spirit"})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Morbid — When this creature enters, target creature an opponent "
            "controls gets -1/-1 until end of turn. If a creature died this "
            "turn, that creature gets -13/-13 until end of turn instead.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        """Requires target creature an opponent controls."""
        controller = self.controller
        return [TargetRequirement(
            filter_fn=lambda obj, g=game, ctrl=controller: (
                CardType.CREATURE in getattr(obj, "card_types", set())
                and getattr(obj, "controller", None) is not ctrl
            ),
            description="target creature an opponent controls",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game: "GameState") -> None:
        """ETB: -1/-1 or -13/-13 depending on morbid."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen or chosen[0] is None:
            return
        target = chosen[0]

        # Verify target still on battlefield
        found = False
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(target):
                found = True
                break
        if not found:
            return

        # Check morbid: did a creature die this turn?
        # Use game-level tracking attribute. Set by CREATURE_DIES event
        # handler or state-based actions. Falls back to False if not present.
        morbid = getattr(game, "creature_died_this_turn", False)
        modifier = -13 if morbid else -1

        def _apply(game: Any) -> None:
            target.modified_power = target.modified_power + modifier
            target.modified_toughness = target.modified_toughness + modifier

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_END_OF_TURN,
        ))
