"""Card implementation for Lunar Insight."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class LunarInsight(Sorcery):
    """Lunar Insight — {2}{U} — Sorcery.

    Draw a card for each different mana value among nonland permanents
    you control.

    FDN collector number 46.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lunar Insight")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Draw a card for each different mana value among nonland "
            "permanents you control.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Draw cards equal to distinct mana values among nonland permanents."""
        from benchmarks.sos.workspace.engine.game import draw_card

        controller = self.controller
        if controller is None:
            return

        battlefield = game.get_battlefield(controller)
        mana_values: set[int] = set()
        for obj in battlefield.get_all():
            card_types = getattr(obj, "card_types", set())
            # Nonland permanents
            if CardType.LAND in card_types:
                continue
            mana_cost = getattr(obj, "mana_cost", None)
            if mana_cost is not None:
                mana_values.add(mana_cost.cmc)
            else:
                # Tokens with no mana cost have MV 0
                mana_values.add(0)

        draw_count = len(mana_values)
        for _ in range(draw_count):
            draw_card(game, controller)
