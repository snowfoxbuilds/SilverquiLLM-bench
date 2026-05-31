"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
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
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\nReach\nWhenever The Dawning Archaic "
            "attacks, you may cast target instant or sorcery card from your "
            "graveyard without paying its mana cost. If that spell would be "
            "put into your graveyard, exile it instead.",
        )
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Count instant and sorcery cards in this spell's controller's graveyard."""
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
        """Register the attack trigger that free-casts from your graveyard."""
        from engine.casting import cast_spell_free

        source = self
        controller = self.controller or self.owner or game.active_player

        def _condition(game: Any, event: AttacksTriggeredEvent) -> bool:
            return event.creature is source or event.attacker is source

        def _target_requirements(game: Any, event: AttacksTriggeredEvent) -> list[TargetRequirement]:
            ctrl = source.controller

            def _filter(obj: Any) -> bool:
                return (
                    getattr(obj, "owner", None) is ctrl
                    and (
                        CardType.INSTANT in getattr(obj, "card_types", set())
                        or CardType.SORCERY in getattr(obj, "card_types", set())
                    )
                )

            return [
                TargetRequirement(
                    filter_fn=_filter,
                    description="target instant or sorcery card in your graveyard",
                    zone=Zone.GRAVEYARD,
                )
            ]

        def _effect(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return

            chosen_targets = getattr(source, "chosen_targets", [])
            target = chosen_targets[0] if chosen_targets else None
            if target is None:
                return

            graveyard = game.get_graveyard(ctrl)
            card_types = getattr(target, "card_types", set())
            if not graveyard.contains(target):
                return
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return
            if not ctrl.choose_yes_no(
                f"Cast {getattr(target, 'name', 'that card')} without paying its mana cost?"
            ):
                return

            try:
                cast_spell_free(game, ctrl, target, Zone.GRAVEYARD)
            except Exception:
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
