"""Card implementation for Artistic Process."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Mode, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
)
from benchmarks.sos.workspace.engine.game import create_token, deal_damage
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ArtisticProcess(Sorcery):
    """Artistic Process."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Artistic Process")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Artistic Process deals 6 damage to target creature.\n"
            "• Artistic Process deals 2 damage to each creature you don't control.\n"
            "• Create a 3/3 blue and red Elemental creature token with flying. It gains haste until end of turn.",
        )
        super().__init__(**kwargs)
        self.selected_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Damage target creature", description="Artistic Process deals 6 damage to target creature."),
            Mode(
                name="Sweep opponents",
                description="Artistic Process deals 2 damage to each creature you don't control.",
            ),
            Mode(
                name="Create token",
                description="Create a 3/3 blue and red Elemental creature token with flying. It gains haste until end of turn.",
            ),
        ]

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        if self.selected_mode != 0:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        if self.selected_mode == 0:
            target = getattr(self, "chosen_targets", [None])[0]
            if isinstance(target, Creature) and target.is_on_battlefield(game):
                deal_damage(game, self, target, 6)
            return

        if self.selected_mode == 1:
            for player in game.players:
                if player is controller:
                    continue
                for permanent in game.get_battlefield(player).get_all():
                    if isinstance(permanent, Creature):
                        deal_damage(game, self, permanent, 2)
            return

        if self.selected_mode != 2:
            return

        token = Creature(
            name="Elemental",
            owner=controller,
            controller=controller,
            subtypes={"Elemental"},
            keywords=Keyword.FLYING,
            base_power=3,
            base_toughness=3,
        )
        token.colors = {Color.BLUE, Color.RED}  # type: ignore[attr-defined]
        token.snapshot_current_characteristics()
        create_token(game, controller, token)

        def _apply_haste(_game: GameState, *, creature: Creature = token) -> None:
            creature.keywords |= Keyword.HASTE

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                apply=_apply_haste,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.apply_all(game)
