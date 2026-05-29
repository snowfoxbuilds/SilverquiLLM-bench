"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.stack import StackObject
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic."""

    @staticmethod
    def _is_instant_or_sorcery(card: Any) -> bool:
        card_types = getattr(card, "card_types", set())
        return CardType.INSTANT in card_types or CardType.SORCERY in card_types

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery card in your graveyard.\n"
            "Reach\n"
            "Whenever The Dawning Archaic attacks, you may cast target instant or sorcery card "
            "from your graveyard without paying its mana cost. If that spell would be put into "
            "your graveyard, exile it instead.",
        )
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        super().__init__(**kwargs)

    def cost_reduction(self, game: GameState) -> int:
        controller = self.controller
        if controller is None:
            return 0
        graveyard = controller.zones[Zone.GRAVEYARD]
        return sum(1 for card in graveyard.get_all() if self._is_instant_or_sorcery(card))

    def register_triggers(self, game: GameState) -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: GameState, event: AttacksTriggeredEvent) -> bool:
            attacker = event.attacker or event.creature
            return attacker is source

        def _create_stack_object(
            game: GameState,
            event: AttacksTriggeredEvent,
            trigger: Any,
        ) -> StackObject | None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return None

            graveyard = ctrl.zones[Zone.GRAVEYARD]
            eligible = [card for card in graveyard.get_all() if source._is_instant_or_sorcery(card)]
            if not eligible:
                return None

            try:
                chosen = ctrl.choose_card(
                    eligible,
                    "Choose target instant or sorcery card in your graveyard",
                )
            except Exception:
                chosen = eligible[0]

            if chosen is None or chosen not in eligible:
                return None

            def _resolve(game: GameState) -> None:
                current_controller = getattr(source, "controller", None)
                if current_controller is None:
                    return
                current_graveyard = current_controller.zones[Zone.GRAVEYARD]
                if not current_graveyard.contains(chosen) or not source._is_instant_or_sorcery(chosen):
                    return
                if not current_controller.choose_yes_no(
                    f"Cast {getattr(chosen, 'name', 'that card')} without paying its mana cost?"
                ):
                    return

                chosen._graveyard_destination_override = Zone.EXILE  # type: ignore[attr-defined]
                try:
                    cast_spell_free(game, current_controller, chosen, Zone.GRAVEYARD)
                except CastingError:
                    if hasattr(chosen, "_graveyard_destination_override"):
                        delattr(chosen, "_graveyard_destination_override")

            return StackObject(
                source=source,
                controller=trigger.controller,
                targets=[chosen],
                on_resolve=_resolve,
            )

        def _effect(game: GameState) -> None:
            return None

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                stack_object_factory=_create_stack_object,
            )
        )
