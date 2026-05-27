"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.casting import CastingError, cast_spell_free, register_stack_graveyard_replacement
from engine.events import AttacksTriggeredEvent
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
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\n"
            "Reach\n"
            "Whenever The Dawning Archaic attacks, you may cast target instant "
            "or sorcery card from your graveyard without paying its mana cost. "
            "If that spell would be put into your graveyard, exile it instead.",
        )
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce this spell's generic cost for spells in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0

        count = 0
        for card in controller.zones[Zone.GRAVEYARD].get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                count += 1
        return count

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger."""
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _eligible_graveyard_spells(ctrl: Any) -> list[Any]:
            return [
                card
                for card in ctrl.zones[Zone.GRAVEYARD].get_all()
                if CardType.INSTANT in getattr(card, "card_types", set())
                or CardType.SORCERY in getattr(card, "card_types", set())
            ]

        def _condition(game: "GameState", event: AttacksTriggeredEvent) -> bool:
            return event.creature is source

        def _effect_factory(_game: "GameState", _event: AttacksTriggeredEvent):
            ctrl = source.controller
            if ctrl is None:
                return lambda __game: None

            candidates = _eligible_graveyard_spells(ctrl)
            if not candidates:
                return lambda __game: None

            target = ctrl.choose(candidates, "Choose instant or sorcery card in your graveyard")
            if target not in candidates:
                return lambda __game: None

            def _resolve(game: "GameState") -> None:
                if not ctrl.zones[Zone.GRAVEYARD].contains(target):
                    return
                card_types = getattr(target, "card_types", set())
                if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                    return
                if not ctrl.choose_yes_no(
                    f"Cast {getattr(target, 'name', 'card')} without paying its mana cost?"
                ):
                    return

                register_stack_graveyard_replacement(game, target, Zone.EXILE)
                try:
                    cast_spell_free(game, ctrl, target, Zone.GRAVEYARD)
                except CastingError:
                    return

            return _resolve

        def _effect(game: "GameState") -> None:
            return

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                effect_factory=_effect_factory,
            )
        )
