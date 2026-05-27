"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone

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
            "This spell costs {1} less to cast for each instant and sorcery card in your graveyard.\n"
            "Reach\n"
            "Whenever The Dawning Archaic attacks, you may cast target instant or sorcery "
            "card from your graveyard without paying its mana cost. If that spell would be "
            "put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        controller = self.controller or self.owner
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        return sum(1 for card in graveyard.get_all() if _is_instant_or_sorcery(card))

    def register_triggers(self, game: "GameState") -> None:
        source = self
        controller = self.controller or game.active_player

        def _condition(game: "GameState", event: AttacksTriggeredEvent) -> bool:
            return event.creature is source or event.attacker is source

        def _get_targets(game: "GameState", event: AttacksTriggeredEvent) -> list[Any]:
            ctrl = source.controller
            if ctrl is None:
                return []
            return [
                TargetRequirement(
                    filter_fn=lambda obj, ctrl=ctrl: (
                        _is_instant_or_sorcery(obj)
                        and any(card is obj for card in ctrl.zones[Zone.GRAVEYARD].get_all())
                    ),
                    description="target instant or sorcery card from your graveyard",
                    zone=Zone.GRAVEYARD,
                )
            ]

        def _effect(game: "GameState") -> None:
            from engine.casting import CastingError, cast_spell_free

            ctrl = source.controller
            if ctrl is None:
                return

            chosen = getattr(source, "chosen_targets", [])
            target = chosen[0] if chosen else None
            if target is None:
                return

            if not ctrl.choose_yes_no(
                f"Cast {getattr(target, 'name', 'target spell')} without paying its mana cost?"
            ):
                return

            try:
                cast_spell_free(game, ctrl, target, Zone.GRAVEYARD)
            except CastingError:
                return

            target.exile_instead_of_graveyard_from_stack = True

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
                get_targets=_get_targets,
            )
        )
