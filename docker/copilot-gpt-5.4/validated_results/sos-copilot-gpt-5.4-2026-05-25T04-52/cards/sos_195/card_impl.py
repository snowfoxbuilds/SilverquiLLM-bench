"""Card implementation for Imperious Inkmage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _order_kept_cards(controller: Any, kept_top_to_bottom: list[Any]) -> list[Any]:
    if len(kept_top_to_bottom) <= 1:
        return kept_top_to_bottom

    remaining = list(kept_top_to_bottom)
    ordered_top_to_bottom: list[Any] = []
    try:
        while remaining:
            choice = controller.choose_card(
                list(remaining),
                "Choose a card to remain on top of your library",
            )
            if choice not in remaining:
                return kept_top_to_bottom
            ordered_top_to_bottom.append(choice)
            remaining.remove(choice)
    except Exception:
        return kept_top_to_bottom
    return ordered_top_to_bottom


class ImperiousInkmage(Creature):
    """Imperious Inkmage."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Imperious Inkmage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{B}"))
        kwargs.setdefault("subtypes", {"Orc", "Warlock"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        library = game.get_library(controller)
        kept_top_to_bottom: list[Any] = []
        for card in reversed(library.top(2)):
            if controller.choose_yes_no(
                f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
            ):
                move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)
            elif library.contains(card):
                kept_top_to_bottom.append(card)
        if len(kept_top_to_bottom) > 1:
            ordered_top_to_bottom = _order_kept_cards(controller, kept_top_to_bottom)
            for card in kept_top_to_bottom:
                if library.contains(card):
                    library.remove(card)
            for card in reversed(ordered_top_to_bottom):
                library.add(card)
