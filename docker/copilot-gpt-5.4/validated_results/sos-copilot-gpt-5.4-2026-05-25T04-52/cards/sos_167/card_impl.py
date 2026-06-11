"""Card implementation for Wild Hypothesis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.game import create_token, look_at_cards
from benchmarks.sos.workspace.engine.types import Color, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _create_fractal_token(counter_count: int) -> Creature:
    token = Creature(
        name="Fractal",
        base_power=0,
        base_toughness=0,
        subtypes={"Fractal"},
    )
    token.colors = {Color.GREEN, Color.BLUE}  # type: ignore[attr-defined]
    token.plus_one_counters = counter_count
    token._base_plus_one_counters = counter_count
    token.snapshot_current_characteristics()
    return token


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


class WildHypothesis(Sorcery):
    """Wild Hypothesis."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wild Hypothesis")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{G}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        x_value = max(0, int(getattr(self, "x_value", 0)))
        create_token(game, controller, _create_fractal_token(x_value))

        library = game.get_library(controller)
        looked_at = list(library.top(2))
        if not looked_at:
            return

        look_at_cards(game, controller, looked_at, source=self, reason="Wild Hypothesis")
        kept_top_to_bottom: list[Any] = []
        for card in reversed(looked_at):
            put_into_graveyard = controller.choose_yes_no(
                f"Put {getattr(card, 'name', 'that card')} into your graveyard?"
            )
            if put_into_graveyard and library.contains(card):
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
