"""Card implementation for DriverOfTheDead."""

from __future__ import annotations


from engine.card import ArtifactCreature, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _self_dies_condition(source: Any):
    """Return a condition callable that matches only when *source* dies."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("creature") is source

    return _condition


class DriverOfTheDead(Creature):
    """Driver of the Dead — {3}{B} — 3/2 — Vampire

    When this creature dies, return target creature card with mana value
    2 or less from your graveyard to the battlefield.

    FDN collector number 605.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Driver of the Dead")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("subtypes", {"Vampire"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature dies, return target creature card with "
            "mana value 2 or less from your graveyard to the battlefield.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.zones import move_to_zone

        source = self

        def _effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            # Find a creature card with mana value 2 or less
            candidates = []
            for obj in graveyard.get_all():
                if obj is source:
                    continue
                card_types = getattr(obj, "card_types", set())
                if CardType.CREATURE not in card_types:
                    continue
                mana_cost = getattr(obj, "mana_cost", None)
                if mana_cost is not None and mana_cost.cmc <= 2:
                    candidates.append(obj)
            if candidates:
                # Return the first valid target
                target = candidates[0]
                target.controller = controller
                move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_self_dies_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


__all__ = ["DriverOfTheDead"]
