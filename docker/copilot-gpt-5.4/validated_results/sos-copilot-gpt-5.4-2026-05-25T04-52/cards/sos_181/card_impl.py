"""Card implementation for Colossus of the Blood Age."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ArtifactCreature
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent, CreatureDiesTriggeredEvent
from benchmarks.sos.workspace.engine.game import deal_damage, discard, draw_card
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ColossusOfTheBloodAge(ArtifactCreature):
    """Colossus of the Blood Age."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Colossus of the Blood Age")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}{W}"))
        kwargs.setdefault("subtypes", {"Construct"})
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _enters_condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            return event.permanent is source and source.is_on_battlefield(g)

        def _enters_effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            for player in g.players:
                if player is not current_controller:
                    deal_damage(g, source, player, 3)
            current_controller.life += 3

        def _dies_condition(_g: GameState, event: CreatureDiesTriggeredEvent) -> bool:
            return event.creature is source

        def _dies_effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            discarded = 0
            while True:
                hand_cards = g.get_hand(current_controller).get_all()
                if not hand_cards:
                    break
                try:
                    should_discard = current_controller.choose_yes_no(
                        f"Discard a card for {source.name}?"
                    )
                except Exception:
                    should_discard = False
                if not should_discard:
                    break
                try:
                    chosen = current_controller.choose_card(hand_cards, "Choose a card to discard")
                except Exception:
                    chosen = hand_cards[0]
                if chosen not in hand_cards:
                    chosen = hand_cards[0]
                discard(g, current_controller, chosen)
                discarded += 1
            for _ in range(discarded + 1):
                draw_card(g, current_controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_enters_condition,
                effect=_enters_effect,
                source=self,
                controller=controller,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=CreatureDiesTriggeredEvent,
                condition=_dies_condition,
                effect=_dies_effect,
                source=self,
                controller=controller,
            )
        )
