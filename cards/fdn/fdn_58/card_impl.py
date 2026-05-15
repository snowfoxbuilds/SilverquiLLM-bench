"""Card implementation for Bloodthirsty Conqueror."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class BloodthirstyConqueror(Creature):
    """Bloodthirsty Conqueror — {3}{B}{B} — 5/5 — Vampire Knight.

    Flying, deathtouch
    Whenever an opponent loses life, you gain that much life.

    FDN collector number 58.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bloodthirsty Conqueror")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Knight"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, deathtouch\n"
            "Whenever an opponent loses life, you gain that much life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register life-loss trigger."""
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(game: Any, data: dict) -> bool:
            player = data.get("player")
            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            # Opponent lost life
            return player is not controller

        def _effect(game: "GameState") -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            amount = data.get("amount", 0)
            if amount > 0:
                controller.life += amount

        # ENGINE LIMITATION: LOSES_LIFE event may not carry 'amount' in data.
        # Using a closure to capture data from condition check.
        _last_amount = [0]

        def _cond(game: Any, data: dict) -> bool:
            player = data.get("player")
            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            if player is controller:
                return False
            _last_amount[0] = data.get("amount", 0)
            return _last_amount[0] > 0

        def _eff(game: "GameState") -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            controller.life += _last_amount[0]

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.LOSES_LIFE,
            condition=_cond,
            effect=_eff,
            source=self,
            controller=controller,
        ))
