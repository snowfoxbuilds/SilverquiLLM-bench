"""Card implementation for Herald of Eternal Dawn."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
)
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class HeraldOfEternalDawn(Creature):
    """Herald of Eternal Dawn — {4}{W}{W}{W} — 6/6 — Angel — Flash, Flying.

    You can't lose the game and your opponents can't win the game.

    FDN collector number 17.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Herald of Eternal Dawn")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{W}{W}{W}"))
        kwargs.setdefault("subtypes", {"Angel"})
        kwargs.setdefault("keywords", Keyword.FLASH | Keyword.FLYING)
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        kwargs.setdefault(
            "rules_text",
            "Flash\nFlying\nYou can't lose the game and your opponents "
            "can't win the game.",
        )
        super().__init__(**kwargs)
        self._cant_lose_effect_ref: ContinuousEffect | None = None

    def register_triggers(self, game: "GameState") -> None:
        """Register continuous effect: controller can't lose, opponents can't win.

        ENGINE LIMITATION: Player-attribute continuous effects are not natively
        supported by the engine's effect manager (it doesn't reset player flags
        between apply cycles). We work around this by explicitly clearing the
        flags before re-applying, so they only persist while Herald is on the
        battlefield. Cleanup on leave is handled via unregister_triggers().
        """
        source = self

        def _apply_cant_lose(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            # Clear flags first so they don't persist if Herald left
            # the battlefield (defensive — unregister_triggers also clears)
            if not _is_on_battlefield(game, source):
                return
            # Set flag on controller
            ctrl.cant_lose = True
            # Set flag on opponents
            for player in game.players:
                if player is not ctrl:
                    player.cant_win = True

        if self._cant_lose_effect_ref is None:
            self._cant_lose_effect_ref = game.effect_manager.add(ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply_cant_lose,
                duration=DURATION_PERMANENT,
            ))

    def unregister_triggers(self, game: "GameState") -> None:
        """Clean up cant_lose/cant_win flags when Herald leaves the battlefield."""
        ctrl = getattr(self, "controller", None)
        if ctrl is not None:
            ctrl.cant_lose = False
            for player in game.players:
                if player is not ctrl:
                    player.cant_win = False
        # Remove the continuous effect
        if self._cant_lose_effect_ref is not None:
            game.effect_manager.remove(self._cant_lose_effect_ref)
            self._cant_lose_effect_ref = None
