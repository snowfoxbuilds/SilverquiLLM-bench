"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.casting import cast_spell_free
from engine.events import AttacksTriggeredEvent, MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic."""

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

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce the generic cost by your instant/sorcery cards in graveyard."""
        controller = self.controller
        if controller is None:
            return 0

        graveyard = game.get_graveyard(controller)
        return sum(
            1
            for card in graveyard.get_all()
            if CardType.INSTANT in getattr(card, "card_types", set())
            or CardType.SORCERY in getattr(card, "card_types", set())
        )

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger."""
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _register_exile_replacement(target_spell: Any, ctrl: Any) -> None:
            def _condition(_game: "GameState", event: MoveToGraveyardReplacementEvent) -> bool:
                return event.card is target_spell and event.from_zone == Zone.STACK

            def _replacement(
                _game: "GameState",
                event: MoveToGraveyardReplacementEvent,
            ) -> MoveToGraveyardReplacementEvent:
                event.destination = "exile"
                return event

            game.replacement_manager.register(
                ReplacementEffect(
                    event_type=MoveToGraveyardReplacementEvent,
                    source=target_spell,
                    condition=_condition,
                    replacement=_replacement,
                    controller=ctrl,
                )
            )

        def _condition(_game: "GameState", event: AttacksTriggeredEvent) -> bool:
            return event.creature is source or event.attacker is source

        def _effect(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return

            graveyard = ctrl.zones[Zone.GRAVEYARD]
            candidates = [
                card
                for card in graveyard.get_all()
                if CardType.INSTANT in getattr(card, "card_types", set())
                or CardType.SORCERY in getattr(card, "card_types", set())
            ]
            if not candidates:
                return

            if not ctrl.choose_yes_no(
                "Cast an instant or sorcery card from your graveyard without paying its mana cost?"
            ):
                return

            chosen = ctrl.choose_card(candidates, "instant or sorcery card to cast from graveyard")
            if chosen is None:
                return

            cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)

            stack_obj = game.stack.peek()
            if stack_obj is None or stack_obj.source is not chosen:
                return

            _register_exile_replacement(chosen, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
