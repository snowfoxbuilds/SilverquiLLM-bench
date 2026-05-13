"""Card implementation for Elvish Regrower."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.triggers import EventType, TriggerRegistration
from engine.types import ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState




def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first, then falls back to the test-backdoor
    attribute ``_resolve_target``.
    """
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)

def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source

    return _condition
class ElvishRegrower(Creature):
    """Elvish Regrower — {2}{G}{G} — 4/3 — Elf Druid

    When this creature enters, return target permanent card from your
    graveyard to your hand.

    FDN collector number 104.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elvish Regrower")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}{G}"))
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, return target permanent card from your "
            "graveyard to your hand.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            controller = getattr(source, "controller", None)
            if target is None or controller is None:
                return
            gy = controller.zones[Zone.GRAVEYARD]
            if gy.contains(target):
                gy.remove(target)
                controller.zones[Zone.HAND].add(target)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))
