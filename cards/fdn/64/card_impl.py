"""Card implementation for InfestationSage."""

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


class InfestationSage(Creature):
    """Infestation Sage — {B} — 1/1 — Elf Warlock

    When this creature dies, create a 1/1 black and green Insect creature
    token with flying.

    FDN collector number 64.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Infestation Sage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault("subtypes", {"Elf", "Warlock"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature dies, create a 1/1 black and green Insect "
            "creature token with flying.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import create_token

        source = self

        def _effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is None:
                return
            token = Creature(
                name="Insect",
                subtypes={"Insect"},
                base_power=1,
                base_toughness=1,
                keywords=Keyword.FLYING,
            )
            create_token(game, controller, token)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_self_dies_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


__all__ = ["InfestationSage"]
