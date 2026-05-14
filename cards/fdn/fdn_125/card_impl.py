"""Card implementation for Wardens of the Cycle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class WardensOfTheCycle(Creature):
    """Wardens of the Cycle — {1}{B}{G}{G} — 3/4 — Elf Warlock.

    Morbid — At the beginning of your end step, if a creature died this
    turn, choose one —
    • You gain 2 life.
    • You draw a card and you lose 1 life.

    FDN collector number 125.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wardens of the Cycle")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{G}{G}"))
        kwargs.setdefault("subtypes", {"Elf", "Warlock"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Morbid — At the beginning of your end step, if a creature "
            "died this turn, choose one —\n"
            "• You gain 2 life.\n"
            "• You draw a card and you lose 1 life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register Morbid end-step trigger."""
        from engine.game import draw_card
        from engine.triggers import EventType, TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, data: dict) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            if game.active_player is not ctrl:
                return False
            return getattr(game, "creature_died_this_turn", False)

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            # Choose mode
            try:
                mode = ctrl.choose(
                    ["gain_life", "draw_card"],
                    "Choose: gain 2 life or draw a card and lose 1 life",
                )
            except Exception:
                mode = "gain_life"

            if mode == "draw_card":
                draw_card(game, ctrl)
                ctrl.life -= 1
            else:
                ctrl.life += 2
                game.trigger_manager.fire_event(
                    game,
                    EventType.GAINS_LIFE,
                    {"player": ctrl, "amount": 2},
                )

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.END_STEP,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
