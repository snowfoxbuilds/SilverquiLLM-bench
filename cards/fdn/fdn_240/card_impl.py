"""Card implementation for Good-Fortune Unicorn."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from collections import deque

from engine.card import Creature
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class GoodFortuneUnicorn(Creature):
    """Good-Fortune Unicorn — {1}{G}{W} — 2/2 — Unicorn.

    Whenever another creature you control enters, put a +1/+1 counter
    on that creature.

    FDN collector number 240.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Good-Fortune Unicorn")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}{W}"))
        kwargs.setdefault("subtypes", {"Unicorn"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Whenever another creature you control enters, put a +1/+1 "
            "counter on that creature.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register ETB trigger for other creatures."""
        from engine.game import add_counter
        from engine.triggers import EventType, TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player
        _queue: deque = deque()

        def _condition(game: Any, data: dict) -> bool:
            permanent = data.get("permanent")
            if permanent is None or permanent is source:
                return False
            ctrl = getattr(source, "controller", None)
            if getattr(permanent, "controller", None) is not ctrl:
                return False
            if CardType.CREATURE not in getattr(permanent, "card_types", set()):
                return False
            _queue.append(permanent)
            return True

        def _effect(game: "GameState") -> None:
            if not _queue:
                return
            target = _queue.popleft()
            add_counter(game, target, "+1/+1", 1)
            if hasattr(target, "_original_plus_one_counters"):
                target._original_plus_one_counters = target.plus_one_counters

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
