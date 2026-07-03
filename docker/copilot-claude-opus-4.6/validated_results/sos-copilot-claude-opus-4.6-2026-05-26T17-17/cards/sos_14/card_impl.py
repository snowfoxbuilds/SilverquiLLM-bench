"""Card implementation for Ennis, Debate Moderator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class EnnisDebateModerator(Creature):
    """Ennis, Debate Moderator — {1}{W} — 1/1 — Legendary Human Cleric.

    ETB: exile up to one other target creature you control. Return that card
    at the beginning of the next end step.
    At the beginning of your end step, if one or more cards were put into
    exile this turn, put a +1/+1 counter on Ennis.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ennis, Debate Moderator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Cleric"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)
        self._exiled_this_turn: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """ETB: exile up to one other target creature you control."""
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target = chosen[0]
        if target is None:
            return

        controller = self.controller
        if controller is None:
            return

        bf = game.get_battlefield(controller)
        if not bf.contains(target):
            return

        # Exile the target
        exile(game, target)
        self._exiled_this_turn = True

    def on_end_step(self, game: "GameState") -> None:
        """At your end step, if card(s) were exiled this turn, +1/+1 counter."""
        if self._exiled_this_turn:
            from engine.game import add_counter
            add_counter(game, self, "+1/+1", 1)
            if hasattr(self, "_base_plus_one_counters"):
                self._base_plus_one_counters = self.plus_one_counters

    def end_step_trigger(self, game: "GameState") -> None:
        """Alias for on_end_step for test compatibility."""
        self.on_end_step(game)
