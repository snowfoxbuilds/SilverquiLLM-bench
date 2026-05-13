"""Card implementation for Meteor Golem."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ArtifactCreature
from engine.game import destroy
from engine.triggers import EventType, TriggerRegistration
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState




def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

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
class MeteorGolem(ArtifactCreature):
    """Meteor Golem — {7} — 3/3 — Golem

    When this creature enters, destroy target nonland permanent an opponent controls.

    FDN collector number 256.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Meteor Golem")
        kwargs.setdefault("mana_cost", ManaCost.parse("{7}"))
        kwargs.setdefault("subtypes", {"Golem"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, destroy target nonland permanent an opponent controls.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import destroy

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is not None and _is_on_battlefield(game, target):
                destroy(game, target)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))
