"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.casting import cast_spell_free
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
            "This spell costs {1} less to cast for each instant and sorcery card "
            "in your graveyard.\nReach\nWhenever The Dawning Archaic attacks, "
            "you may cast target instant or sorcery card from your graveyard "
            "without paying its mana cost. If that spell would be put into your "
            "graveyard, exile it instead.",
        )
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce generic cost by the number of instant/sorcery cards in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        return sum(
            1
            for card in controller.zones[Zone.GRAVEYARD].get_all()
            if CardType.INSTANT in getattr(card, "card_types", set())
            or CardType.SORCERY in getattr(card, "card_types", set())
        )

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger."""
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: AttacksTriggeredEvent) -> bool:
            return event.creature is source or event.attacker is source

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            if not ctrl.choose_yes_no(
                "Cast an instant or sorcery card from your graveyard without paying its mana cost?"
            ):
                return

            graveyard = ctrl.zones[Zone.GRAVEYARD]
            eligible = [
                card for card in graveyard.get_all()
                if CardType.INSTANT in getattr(card, "card_types", set())
                or CardType.SORCERY in getattr(card, "card_types", set())
            ]
            if not eligible:
                return

            chosen = ctrl.choose_card(eligible, "instant or sorcery card to cast from graveyard")
            if chosen not in eligible:
                return

            chosen._exile_on_resolution = True
            cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
