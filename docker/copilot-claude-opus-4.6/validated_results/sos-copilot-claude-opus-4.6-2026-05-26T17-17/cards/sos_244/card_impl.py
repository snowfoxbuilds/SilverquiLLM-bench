"""Card implementation for Witherbloom Charm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomCharm(Instant):
    """Witherbloom Charm — {B}{G} — Instant.

    Choose one —
    - You may sacrifice a permanent. If you do, draw two cards.
    - You gain 5 life.
    - Destroy target nonland permanent with mana value 2 or less.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom Charm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}{G}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState", mode: int = 1, **kwargs: Any) -> None:
        """Resolve with the chosen mode."""
        if mode == 1:
            self._mode_1(game, kwargs.get("sacrifice_target"))
        elif mode == 2:
            self._mode_2(game)
        elif mode == 3:
            self._mode_3(game, kwargs.get("targets", []))

    def _mode_1(self, game: "GameState", sacrifice_target: Any) -> None:
        """You may sacrifice a permanent. If you do, draw two cards."""
        from engine.game import draw_card, sacrifice

        controller = self.controller or self.owner
        if sacrifice_target is not None:
            sacrifice(game, controller, sacrifice_target)
            draw_card(game, controller)
            draw_card(game, controller)

    def _mode_2(self, game: "GameState") -> None:
        """You gain 5 life."""
        controller = self.controller or self.owner
        controller.life += 5

    def _mode_3(self, game: "GameState", targets: list[Any]) -> None:
        """Destroy target nonland permanent with mana value 2 or less."""
        from engine.game import destroy

        if not targets:
            return

        target = targets[0]
        # Check mana value <= 2 and not a land
        card_types = getattr(target, "card_types", set())
        if CardType.LAND in card_types:
            return

        mc = getattr(target, "mana_cost", None)
        mv = mc.cmc if mc is not None else 0
        if mv <= 2:
            destroy(game, target)
