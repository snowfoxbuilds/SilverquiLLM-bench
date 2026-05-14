"""Card implementation for Vanguard Seraph."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class VanguardSeraph(Creature):
    """Vanguard Seraph — {3}{W} — 3/3 — Angel Warrior — Flying.

    Whenever you gain life for the first time each turn, surveil 1.
    (Look at the top card of your library. You may put it into your
    graveyard.)

    FDN collector number 28.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vanguard Seraph")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Angel", "Warrior"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying\n"
            "Whenever you gain life for the first time each turn, surveil 1.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register life-gain trigger: first time each turn -> surveil 1."""
        from engine.triggers import EventType, TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # Track turn number for once-per-turn reset
        source._vanguard_surveil_on_turn: int = -1

        def _gain_life_condition(game: Any, data: dict) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            if data.get("player") is not ctrl:
                return False
            # Only first time each turn
            current_turn = getattr(game, "turn_number", 0)
            if getattr(source, "_vanguard_surveil_on_turn", -1) == current_turn:
                return False
            return True

        def _gain_life_effect(game: "GameState") -> None:
            source._vanguard_surveil_on_turn = getattr(game, "turn_number", 0)
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            # Surveil 1: look at top card, may put it into graveyard
            from engine.types import Zone

            library = ctrl.zones[Zone.LIBRARY]
            cards = list(library.get_all())
            if not cards:
                return
            top_card = cards[-1]
            # Ask controller whether to put it into graveyard
            put_in_gy = ctrl.choose_yes_no(
                f"Surveil 1: Put {getattr(top_card, 'name', 'card')} into your graveyard?"
            )
            if put_in_gy:
                library.remove(top_card)
                ctrl.zones[Zone.GRAVEYARD].add(top_card)

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.GAINS_LIFE,
            condition=_gain_life_condition,
            effect=_gain_life_effect,
            source=self,
            controller=controller,
        ))
