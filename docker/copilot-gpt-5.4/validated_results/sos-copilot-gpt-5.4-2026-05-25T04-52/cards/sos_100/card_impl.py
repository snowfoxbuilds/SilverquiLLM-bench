"""Card implementation for Send in the Pest."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent, GainsLifeTriggeredEvent
from benchmarks.sos.workspace.engine.game import create_token, discard
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Color, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class _PestToken(Creature):
    """1/1 black and green Pest token with an attack trigger."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pest")
        kwargs.setdefault("subtypes", {"Pest"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)
        self.colors = {Color.BLACK, Color.GREEN}
        self.snapshot_current_characteristics()

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(_game: GameState, event: AttacksTriggeredEvent) -> bool:
            return event.creature is source or event.attacker is source

        def _effect(_g: GameState) -> None:
            return

        def _create_stack_object(
            _game: GameState,
            event: AttacksTriggeredEvent,  # noqa: ARG001
        ) -> StackObject | None:
            locked_controller = getattr(source, "controller", None)
            if locked_controller is None:
                return

            def _resolve(g: GameState, *, player=locked_controller) -> None:
                player.life += 1
                player.life_gained_this_turn = getattr(player, "life_gained_this_turn", 0) + 1
                g.trigger_manager.fire_event(
                    g,
                    GainsLifeTriggeredEvent(player=player, amount=1),
                )

            return StackObject(
                source=source,
                controller=locked_controller,
                on_resolve=_resolve,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                create_stack_object=_create_stack_object,
            )
        )


class SendInThePest(Sorcery):
    """Send in the Pest."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Send in the Pest")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            'Each opponent discards a card. You create a 1/1 black and green Pest creature token with '
            '"Whenever this token attacks, you gain 1 life."',
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        for player in game.players:
            if player is controller:
                continue
            cards_in_hand = game.get_hand(player).get_all()
            if not cards_in_hand:
                continue
            try:
                chosen = player.choose_card(cards_in_hand, "card to discard")
            except Exception:
                chosen = cards_in_hand[0]
            if chosen not in cards_in_hand:
                chosen = cards_in_hand[0]
            discard(game, player, chosen)
        create_token(game, controller, _PestToken())
