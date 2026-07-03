"""Card implementation for Transcendent Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.game import discard, draw_card
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class TranscendentArchaic(Creature):
    """Transcendent Archaic."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Transcendent Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{7}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        kwargs.setdefault(
            "rules_text",
            "Vigilance\nConverge — When this creature enters, you may draw X cards, where X is "
            "the number of colors of mana spent to cast this spell. If you draw one or more "
            "cards this way, discard two cards.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        colors_spent = len(set(getattr(self, "colors_spent", [])))
        if colors_spent <= 0:
            return

        try:
            should_draw = controller.choose_yes_no(
                f"Draw {colors_spent} cards with {self.name}?"
            )
        except Exception:
            should_draw = False
        if not should_draw:
            return

        drawn = 0
        for _ in range(colors_spent):
            if draw_card(game, controller) is not None:
                drawn += 1
        if drawn <= 0:
            return

        for _ in range(min(2, len(game.get_hand(controller).get_all()))):
            hand = game.get_hand(controller).get_all()
            if not hand:
                break
            try:
                chosen = controller.choose_card(hand, "Choose a card to discard")
            except Exception:
                chosen = hand[0]
            if chosen is None or not game.get_hand(controller).contains(chosen):
                continue
            discard(game, controller, chosen)
