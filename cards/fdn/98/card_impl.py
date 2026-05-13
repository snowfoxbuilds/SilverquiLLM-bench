"""Card implementation for Ambush Wolf."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.game import exile
from engine.triggers import EventType, TriggerRegistration
from engine.types import Keyword, ManaCost, Zone

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
class AmbushWolf(Creature):
    """Ambush Wolf — {2}{G} — 4/2 — Wolf — Flash

    When this creature enters, exile up to one target card from a graveyard.

    FDN collector number 98.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ambush Wolf")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", {"Wolf"})
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Flash\nWhen this creature enters, exile up to one target card from a graveyard.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is None:
                return
            # Find and remove target from any graveyard, then exile
            for player in game.players:
                gy = player.zones[Zone.GRAVEYARD]
                if gy.contains(target):
                    gy.remove(target)
                    owner = getattr(target, "owner", player)
                    owner.zones[Zone.EXILE].add(target)
                    return

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))
