"""Card implementation for CrowOfDarkTidings."""

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

def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source

    return _condition


class CrowOfDarkTidings(Creature):
    """Crow of Dark Tidings — {2}{B} — 2/1 — Zombie Bird — Flying

    When this creature enters or dies, mill two cards.

    FDN collector number 519.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Crow of Dark Tidings")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", {"Zombie", "Bird"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this creature enters or dies, mill two cards.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _mill_effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]
            for _ in range(2):
                if len(library) > 0:
                    card = library.top(1)[0]
                    library.remove(card)
                    graveyard.add(card)

        controller = getattr(self, "controller", None) or game.active_player
        # ETB trigger
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_mill_effect,
            source=self,
            controller=controller,
        ))
        # Death trigger
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_self_dies_condition(self),
            effect=_mill_effect,
            source=self,
            controller=controller,
        ))


__all__ = ["CrowOfDarkTidings"]
