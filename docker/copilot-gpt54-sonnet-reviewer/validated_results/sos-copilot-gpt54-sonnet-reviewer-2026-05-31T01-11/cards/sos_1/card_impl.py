"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.casting import CastingError, cast_spell_free
from engine.events import AttacksTriggeredEvent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.card import CardImpl
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery card in your graveyard.\n"
            "Reach\n"
            "Whenever The Dawning Archaic attacks, you may cast target instant or sorcery card from your "
            "graveyard without paying its mana cost. If that spell would be put into your graveyard, exile "
            "it instead.",
        )
        super().__init__(**kwargs)

    def _is_spell_card(self, card: CardImpl) -> bool:
        return bool(getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})

    def cost_reduction(self, game: GameState) -> int:
        controller = self.controller
        if controller is None:
            return 0
        return sum(1 for card in game.get_graveyard(controller).get_all() if self._is_spell_card(card))

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: GameState, event: AttacksTriggeredEvent) -> bool:
            return event.creature is source

        def _build_stack_object(
            game: GameState,
            event: AttacksTriggeredEvent,
        ) -> StackObject | None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.creature is not source:
                return None

            candidates = [card for card in game.get_graveyard(ctrl).get_all() if source._is_spell_card(card)]
            if not candidates:
                return None

            try:
                chosen = ctrl.choose_card(candidates, "instant or sorcery card in your graveyard")
            except Exception:
                chosen = candidates[0]

            if chosen not in candidates:
                return None

            def _resolve_trigger(game: GameState) -> None:
                current_controller = getattr(source, "controller", None)
                if current_controller is None:
                    return
                graveyard = game.get_graveyard(current_controller)
                if not graveyard.contains(chosen):
                    return
                if not source._is_spell_card(chosen):
                    return
                if not current_controller.choose_yes_no(
                    f"Cast {getattr(chosen, 'name', 'that card')} without paying its mana cost?"
                ):
                    return

                try:
                    cast_spell_free(game, current_controller, chosen, Zone.GRAVEYARD)
                    spell_obj = game.stack.peek()
                    if spell_obj is not None and spell_obj.source is chosen:
                        spell_obj.destination_override = Zone.EXILE
                except CastingError:
                    return

            return StackObject(
                source=source,
                controller=ctrl,
                targets=[chosen],
                on_resolve=_resolve_trigger,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=lambda game: None,
                source=self,
                controller=controller,
                stack_builder=_build_stack_object,
            )
        )
