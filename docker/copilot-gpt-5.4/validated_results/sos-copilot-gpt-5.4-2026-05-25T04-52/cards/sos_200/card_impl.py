"""Card implementation for Lorehold Charm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant, Mode
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.game import sacrifice
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class LoreholdCharm(Instant):
    """Lorehold Charm."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold Charm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        super().__init__(**kwargs)
        self.selected_mode: int = 0

    def get_modes(self) -> list[Mode]:
        return [
            Mode(
                name="Artifact sacrifice",
                description="Each opponent sacrifices a nontoken artifact of their choice.",
            ),
            Mode(
                name="Return small permanent",
                description="Return target artifact or creature card with mana value 2 or less from your graveyard to the battlefield.",
            ),
            Mode(
                name="Team pump",
                description="Creatures you control get +1/+1 and gain trample until end of turn.",
            ),
        ]

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        if self.selected_mode != 1:
            return []
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj, current_controller=controller: (
                    getattr(obj, "owner", None) is current_controller
                    and (
                        CardType.ARTIFACT in getattr(obj, "card_types", set())
                        or CardType.CREATURE in getattr(obj, "card_types", set())
                    )
                    and getattr(getattr(obj, "mana_cost", None), "cmc", 0) <= 2
                ),
                description="target artifact or creature card with mana value 2 or less in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        if self.selected_mode == 0:
            for player in game.players:
                if player is controller:
                    continue
                choices = [
                    permanent
                    for permanent in game.get_battlefield(player).get_all()
                    if (
                        CardType.ARTIFACT in getattr(permanent, "card_types", set())
                        and not getattr(permanent, "is_token", False)
                    )
                ]
                if not choices:
                    continue
                try:
                    chosen = player.choose_card(choices, "Choose a nontoken artifact to sacrifice")
                except Exception:
                    chosen = choices[0]
                if chosen not in choices:
                    chosen = choices[0]
                sacrifice(game, player, chosen)
            return

        if self.selected_mode == 1:
            target = self.chosen_targets[0] if getattr(self, "chosen_targets", []) else None
            if target is None or target not in game.get_graveyard(controller).get_all():
                return
            if (
                CardType.ARTIFACT not in getattr(target, "card_types", set())
                and CardType.CREATURE not in getattr(target, "card_types", set())
            ):
                return
            if getattr(getattr(target, "mana_cost", None), "cmc", 0) > 2:
                return
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)
            return

        if self.selected_mode != 2:
            return

        def _pump_team(g: GameState, *, current_controller: Any = controller) -> None:
            for permanent in g.get_battlefield(current_controller).get_all():
                if isinstance(permanent, Creature):
                    permanent.modified_power += 1
                    permanent.modified_toughness += 1

        def _grant_trample(g: GameState, *, current_controller: Any = controller) -> None:
            for permanent in g.get_battlefield(current_controller).get_all():
                if isinstance(permanent, Creature):
                    permanent.keywords |= Keyword.TRAMPLE

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_pump_team,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                apply=_grant_trample,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.apply_all(game)
