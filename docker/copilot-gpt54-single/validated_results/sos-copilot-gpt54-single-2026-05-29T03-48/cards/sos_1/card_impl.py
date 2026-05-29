"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.casting import cast_spell_free
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _is_instant_or_sorcery(card: Any) -> bool:
    """Return True if *card* is an instant or sorcery card."""
    card_types = getattr(card, "card_types", set())
    return CardType.INSTANT in card_types or CardType.SORCERY in card_types


class TheDawningArchaic(Creature):
    """The Dawning Archaic."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery card "
            "in your graveyard.\nReach\nWhenever The Dawning Archaic attacks, "
            "you may cast target instant or sorcery card from your graveyard "
            "without paying its mana cost. If that spell would be put into "
            "your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce cost by the number of instant and sorcery cards in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        return sum(
            1
            for card in controller.zones[Zone.GRAVEYARD].get_all()
            if _is_instant_or_sorcery(card)
        )

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger."""
        controller = self.controller
        if controller is None:
            return

        def _condition(_game: "GameState", event: AttacksTriggeredEvent) -> bool:
            return event.attacker is self or event.creature is self

        def _target_requirements(
            _game: "GameState",
            _event: AttacksTriggeredEvent,
        ) -> list[TargetRequirement]:
            return [
                TargetRequirement(
                    filter_fn=lambda obj, ctrl=controller: (
                        ctrl.zones[Zone.GRAVEYARD].contains(obj)
                        and _is_instant_or_sorcery(obj)
                    ),
                    description="target instant or sorcery card from your graveyard",
                    zone=Zone.GRAVEYARD,
                )
            ]

        def _effect(_game: "GameState") -> None:
            chosen_targets = getattr(self, "chosen_targets", [])
            target = chosen_targets[0] if chosen_targets else None
            if target is None:
                return
            active_controller = self.controller
            if active_controller is None:
                return
            if not active_controller.choose_yes_no(
                f"Cast {getattr(target, 'name', 'that spell')} from your graveyard "
                "without paying its mana cost?"
            ):
                return
            cast_spell_free(_game, active_controller, target, Zone.GRAVEYARD)
            target.exile_if_resolved_from_stack = True

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                target_requirements=_target_requirements,
            )
        )
