"""Card implementation for Tragedy Feaster."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.game import discard, sacrifice
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player


class TragedyFeaster(Creature):
    """Tragedy Feaster."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tragedy Feaster")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}{B}"))
        kwargs.setdefault("subtypes", {"Demon"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE | Keyword.WARD)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 6)
        kwargs.setdefault(
            "rules_text",
            "Trample\nWard—Discard a card.\nInfusion — At the beginning of your end step, "
            "sacrifice a permanent unless you gained life this turn.",
        )
        super().__init__(**kwargs)
        self.ward_cost = self._pay_discard_ward

    def _pay_discard_ward(
        self,
        game: GameState,
        player: Player,
        taxed_spell: object,  # noqa: ARG002
        taxed_stack_obj: StackObject,  # noqa: ARG002
    ) -> bool:
        hand = game.get_hand(player).get_all()
        if not hand:
            return False
        if not player.choose_yes_no("Discard a card to pay ward?"):
            return False
        try:
            chosen = player.choose_card(hand, "card to discard for ward")
        except Exception:
            chosen = hand[0]
        if chosen is None or not game.get_hand(player).contains(chosen):
            return False
        discard(game, player, chosen)
        return True

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: EndStepTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and g.get_battlefield(current_controller).contains(source)
            )

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            if getattr(current_controller, "life_gained_this_turn", 0) > 0:
                return
            permanents = g.get_battlefield(current_controller).get_all()
            if not permanents:
                return
            try:
                chosen = current_controller.choose_card(permanents, "permanent to sacrifice")
            except Exception:
                chosen = permanents[0]
            if chosen is None or not g.get_battlefield(current_controller).contains(chosen):
                return
            sacrifice(g, current_controller, chosen)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EndStepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
