"""Card implementation for Mind into Matter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


_PERMANENT_TYPES = {
    CardType.CREATURE,
    CardType.ENCHANTMENT,
    CardType.ARTIFACT,
    CardType.PLANESWALKER,
    CardType.LAND,
}


class MindIntoMatter(Sorcery):
    """Mind into Matter."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mind into Matter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{G}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Draw X cards. You may put a permanent card with mana value X or less from your hand "
            "onto the battlefield tapped.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        x_value = max(0, int(getattr(self, "x_value", 0)))
        for _ in range(x_value):
            draw_card(game, controller)

        hand_cards = list(game.get_hand(controller).get_all())
        candidates = [
            card
            for card in hand_cards
            if bool(getattr(card, "card_types", set()) & _PERMANENT_TYPES)
            and getattr(card, "mana_cost", ManaCost()).cmc <= x_value
        ]
        if not candidates:
            return
        if not controller.choose_yes_no("Put a permanent card onto the battlefield tapped?"):
            return
        chosen_card = controller.choose_card(
            candidates,
            "Choose a permanent card with mana value X or less",
        )
        if chosen_card not in candidates or not game.get_hand(controller).contains(chosen_card):
            return
        if hasattr(chosen_card, "is_tapped"):
            chosen_card.is_tapped = True
        move_to_zone(game, chosen_card, Zone.HAND, Zone.BATTLEFIELD)
