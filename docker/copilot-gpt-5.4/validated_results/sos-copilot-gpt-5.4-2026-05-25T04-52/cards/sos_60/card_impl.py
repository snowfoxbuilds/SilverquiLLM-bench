"""Card implementation for Muse Seeker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import discard, draw_card
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class MuseSeeker(Creature):
    """Muse Seeker."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Muse Seeker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("subtypes", {"Elf", "Wizard"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)
        self._pending_opus_discards: list[bool] = []

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:  # noqa: ARG001
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            matches = (
                current_controller is not None
                and event.player is current_controller
                and spell is not None
                and bool(getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})
            )
            if matches:
                source._pending_opus_discards.append(getattr(spell, "mana_spent", 0) < 5)
            return matches

        def _effect(game: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            must_discard = source._pending_opus_discards.pop() if source._pending_opus_discards else True
            if current_controller is None or not source.is_on_battlefield(game):
                return
            draw_card(game, current_controller)
            if not must_discard:
                return
            hand = list(game.get_hand(current_controller).get_all())
            if not hand:
                return
            try:
                chosen = current_controller.choose_card(hand, "Choose a card to discard")
            except Exception:
                chosen = hand[0]
            if chosen is not None and game.get_hand(current_controller).contains(chosen):
                discard(game, current_controller, chosen)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
