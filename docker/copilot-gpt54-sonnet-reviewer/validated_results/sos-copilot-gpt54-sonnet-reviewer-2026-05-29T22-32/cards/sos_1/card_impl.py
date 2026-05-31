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


def _is_instant_or_sorcery(card: Any) -> bool:
    card_types = getattr(card, "card_types", set())
    return CardType.INSTANT in card_types or CardType.SORCERY in card_types


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
            "This spell costs {1} less to cast for each instant and sorcery card "
            "in your graveyard.\n"
            "Reach\n"
            "Whenever The Dawning Archaic attacks, you may cast target instant or "
            "sorcery card from your graveyard without paying its mana cost. If "
            "that spell would be put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        return sum(1 for card in graveyard.get_all() if _is_instant_or_sorcery(card))

    def register_triggers(self, game: "GameState") -> None:
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: "GameState", event: AttacksTriggeredEvent) -> bool:
            return event.creature is source or event.attacker is source

        def _get_targets(
            game: "GameState",
            event: AttacksTriggeredEvent,
        ) -> list[Any]:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return []
            graveyard = game.get_graveyard(current_controller)
            return [card for card in graveyard.get_all() if _is_instant_or_sorcery(card)]

        def _effect(
            game: "GameState",
            *,
            targets: list[Any] | None = None,
            **_: Any,
        ) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return

            target = targets[0] if targets else None
            if target is None:
                return

            graveyard = game.get_graveyard(current_controller)
            if not graveyard.contains(target) or not _is_instant_or_sorcery(target):
                return

            if not current_controller.choose_yes_no(
                f"Cast {target.name} from your graveyard without paying its mana cost?"
            ):
                return

            marker = object()
            target._dawning_archaic_exile_marker = marker

            def _replacement_condition(game: "GameState", event: Any) -> bool:
                return (
                    isinstance(event, MoveToGraveyardReplacementEvent)
                    and event.card is target
                    and getattr(target, "_dawning_archaic_exile_marker", None) is marker
                )

            def _replacement(game: "GameState", event: Any) -> Any:
                if getattr(target, "_dawning_archaic_exile_marker", None) is marker:
                    delattr(target, "_dawning_archaic_exile_marker")
                game.replacement_manager.unregister(marker)
                event.destination = "exile"
                return event

            game.replacement_manager.register(
                ReplacementEffect(
                    event_type=MoveToGraveyardReplacementEvent,
                    source=marker,
                    condition=_replacement_condition,
                    replacement=_replacement,
                    controller=current_controller,
                )
            )

            try:
                cast_spell_free(game, current_controller, target, Zone.GRAVEYARD)
            except Exception:
                if getattr(target, "_dawning_archaic_exile_marker", None) is marker:
                    delattr(target, "_dawning_archaic_exile_marker")
                game.replacement_manager.unregister(marker)
                raise

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                get_targets=_get_targets,
                target_description="target instant or sorcery card from your graveyard",
            )
        )
