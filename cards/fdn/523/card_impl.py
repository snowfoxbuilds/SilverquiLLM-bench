"""Card implementation for MaalfeldTwins."""

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


class MaalfeldTwins(Creature):
    """Maalfeld Twins — {5}{B} — 4/4 — Zombie

    When this creature dies, create two 2/2 black Zombie creature tokens.

    FDN collector number 523.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Maalfeld Twins")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{B}"))
        kwargs.setdefault("subtypes", {"Zombie"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "When this creature dies, create two 2/2 black Zombie creature tokens.",
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
            for _ in range(2):
                token = Creature(
                    name="Zombie",
                    subtypes={"Zombie"},
                    base_power=2,
                    base_toughness=2,
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


__all__ = ["MaalfeldTwins"]
