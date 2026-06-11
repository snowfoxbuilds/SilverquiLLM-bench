"""Card implementation for Flow State."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player


class FlowState(Sorcery):
    """Flow State."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Flow State")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)
        looked_at = list(library.top(3))
        if not looked_at:
            return
        for card in looked_at:
            library.remove(card)

        picks = 2 if self._has_instant_and_sorcery_in_graveyard(game, controller) else 1
        chosen_for_hand = self._choose_cards(controller, looked_at, picks)
        hand = game.get_hand(controller)
        remaining = list(looked_at)
        for card in chosen_for_hand:
            if card in remaining:
                remaining.remove(card)
                hand.add(card)

        ordered_bottom = self._choose_cards(controller, remaining, len(remaining))
        for card in ordered_bottom:
            if card in remaining:
                remaining.remove(card)
                library.add(card, position="bottom")

    def _has_instant_and_sorcery_in_graveyard(self, game: GameState, controller: Player) -> bool:
        graveyard_cards = game.get_graveyard(controller).get_all()
        has_instant = any(CardType.INSTANT in getattr(card, "card_types", set()) for card in graveyard_cards)
        has_sorcery = any(CardType.SORCERY in getattr(card, "card_types", set()) for card in graveyard_cards)
        return has_instant and has_sorcery

    def _choose_cards(self, controller: Player, cards: list[Any], count: int) -> list[Any]:
        chosen: list[Any] = []
        remaining = list(cards)
        for index in range(min(count, len(remaining))):
            selection = None
            try:
                selection = controller.choose_card(remaining, f"Choose card {index + 1}")
            except Exception:
                selection = None
            if selection not in remaining:
                selection = remaining[0]
            chosen.append(selection)
            remaining.remove(selection)
        return chosen
