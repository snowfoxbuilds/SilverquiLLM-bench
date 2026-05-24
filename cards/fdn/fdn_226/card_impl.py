"""Card implementation for Inspiring Call."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
)
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class InspiringCall(Instant):
    """Inspiring Call — {2}{G} — Instant.

    Draw a card for each creature you control with a +1/+1 counter on
    it. Those creatures gain indestructible until end of turn.

    FDN collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Inspiring Call")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Draw a card for each creature you control with a +1/+1 counter "
            "on it. Those creatures gain indestructible until end of turn.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Draw cards and grant indestructible to creatures with +1/+1 counters."""
        from benchmarks.sos.workspace.engine.game import draw_card

        controller = self.controller
        if controller is None:
            return

        bf = game.get_battlefield(controller)
        creatures_with_counters: list[Any] = []
        for obj in bf.get_all():
            if CardType.CREATURE not in getattr(obj, "card_types", set()):
                continue
            if getattr(obj, "plus_one_counters", 0) > 0:
                creatures_with_counters.append(obj)

        # Draw a card for each
        for _ in creatures_with_counters:
            draw_card(game, controller)

        # Grant indestructible until end of turn
        for creature in creatures_with_counters:
            creature_ref = creature

            def _apply_indestructible(game: Any, c=creature_ref) -> None:
                c.keywords = c.keywords | Keyword.INDESTRUCTIBLE

            game.effect_manager.add(ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply_indestructible,
                duration=DURATION_END_OF_TURN,
            ))
