"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.casting import cast_spell_free
from engine.events import AttacksTriggeredEvent, MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone

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
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery card in your graveyard.\n"
            "Reach\n"
            "Whenever The Dawning Archaic attacks, you may cast target instant or sorcery card from "
            "your graveyard without paying its mana cost. If that spell would be put into your "
            "graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce generic cost by instants and sorceries in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        return sum(
            1
            for card in graveyard.get_all()
            if (
                CardType.INSTANT in getattr(card, "card_types", set())
                or CardType.SORCERY in getattr(card, "card_types", set())
            )
        )

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger."""
        source = self
        controller = getattr(self, "controller", None) or getattr(self, "owner", None) or game.active_player

        def _condition(game: Any, event: AttacksTriggeredEvent) -> bool:
            return event.creature is source

        def _targets(game: Any, event: AttacksTriggeredEvent) -> list[Any]:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return []

            graveyard = game.get_graveyard(ctrl)

            def _filter(card: Any) -> bool:
                if not graveyard.contains(card):
                    return False
                return (
                    CardType.INSTANT in getattr(card, "card_types", set())
                    or CardType.SORCERY in getattr(card, "card_types", set())
                )

            return [
                TargetRequirement(
                    filter_fn=_filter,
                    description="target instant or sorcery card from your graveyard",
                    zone=Zone.GRAVEYARD,
                )
            ]

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            chosen = getattr(source, "chosen_targets", None) or []
            target = chosen[0] if chosen else None
            if target is None:
                return

            graveyard = game.get_graveyard(ctrl)
            if not graveyard.contains(target):
                return
            if not (
                CardType.INSTANT in getattr(target, "card_types", set())
                or CardType.SORCERY in getattr(target, "card_types", set())
            ):
                return

            if not ctrl.choose_yes_no(
                "Cast target instant or sorcery card from your graveyard without paying its mana cost?"
            ):
                return

            def _replacement_condition(game: Any, event: MoveToGraveyardReplacementEvent) -> bool:
                return event.card is target

            def _replacement(game: Any, event: MoveToGraveyardReplacementEvent) -> MoveToGraveyardReplacementEvent:
                event.destination = "exile"
                return event

            game.replacement_manager.register(
                ReplacementEffect(
                    event_type=MoveToGraveyardReplacementEvent,
                    source=target,
                    condition=_replacement_condition,
                    replacement=_replacement,
                    controller=ctrl,
                )
            )

            try:
                cast_spell_free(game, ctrl, target, Zone.GRAVEYARD)
            except Exception:
                game.replacement_manager.unregister(target)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                target_requirements=_targets,
            )
        )
