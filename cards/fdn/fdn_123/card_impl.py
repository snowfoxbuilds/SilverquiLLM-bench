"""Card implementation for Niv-Mizzet, Visionary."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class NivMizzetVisionary(Creature):
    """Niv-Mizzet, Visionary — {4}{U}{R} — 5/5 — Legendary Dragon Wizard.

    Flying
    You have no maximum hand size.
    Whenever a source you control deals noncombat damage to an opponent,
    you draw that many cards.

    FDN collector number 123.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Niv-Mizzet, Visionary")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{R}"))
        kwargs.setdefault("subtypes", {"Dragon", "Wizard"})
        kwargs.setdefault("supertypes", {"Legendary"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying\n"
            "You have no maximum hand size.\n"
            "Whenever a source you control deals noncombat damage to an "
            "opponent, you draw that many cards.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register noncombat damage trigger and no-max-hand-size."""
        from collections import deque

        from engine.game import draw_card
        from engine.triggers import EventType, TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # Set no maximum hand size on controller
        controller.no_maximum_hand_size = True

        # Use a queue so multiple events before resolution don't overwrite
        _amount_queue: deque[int] = deque()

        def _condition(game: Any, data: dict) -> bool:
            # Noncombat damage to an opponent
            if data.get("is_combat", False):
                return False
            dmg_source = data.get("source")
            if dmg_source is None:
                return False
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            src_ctrl = getattr(dmg_source, "controller", None)
            if src_ctrl is not ctrl:
                return False
            target = data.get("target")
            if target is None or not hasattr(target, "life"):
                return False
            # Target must be an opponent
            if target is ctrl:
                return False
            _amount_queue.append(data.get("amount", 1))
            return True

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            amount = _amount_queue.popleft() if _amount_queue else 1
            for _ in range(amount):
                draw_card(game, ctrl)

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.DEALS_DAMAGE,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

    def unregister_triggers(self, game: "GameState") -> None:
        """Clean up no-max-hand-size on controller."""
        controller = getattr(self, "controller", None)
        if controller is not None:
            controller.no_maximum_hand_size = False
