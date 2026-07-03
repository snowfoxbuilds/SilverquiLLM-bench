"""Card implementation for Ark of Hunger."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Artifact
from benchmarks.sos.workspace.engine.events import GainsLifeTriggeredEvent, GraveyardLeavesTriggeredEvent
from benchmarks.sos.workspace.engine.game import deal_damage
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ArkOfHunger(Artifact):
    """Ark of Hunger."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ark of Hunger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}{W}"))
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: GraveyardLeavesTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and bool(getattr(event, "cards", []))
                and source.is_on_battlefield(g)
            )

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            for player in g.players:
                if player is not current_controller:
                    deal_damage(g, source, player, 1)
            current_controller.life += 1
            g.trigger_manager.fire_event(
                g,
                GainsLifeTriggeredEvent(player=current_controller, amount=1),
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=GraveyardLeavesTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState, artifact: Artifact) -> bool:  # noqa: ARG001
            if artifact.is_tapped:
                return False
            artifact.is_tapped = True
            return True

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            library = game.get_library(controller)
            top_cards = library.top(1)
            if not top_cards:
                return
            milled = top_cards[0]
            move_to_zone(game, milled, Zone.LIBRARY, Zone.GRAVEYARD)
            game.grant_graveyard_play_permission_until_end_of_turn(
                controller,
                milled,
                source=source,
            )

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{T}: Mill a card. You may play that card this turn.",
            )
        ]
