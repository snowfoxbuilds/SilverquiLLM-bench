"""Card implementation for Charging Strifeknight."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.game import discard, draw_card
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ChargingStrifeknight(Creature):
    """Charging Strifeknight."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Charging Strifeknight")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault("subtypes", {"Spirit", "Knight"})
        kwargs.setdefault("keywords", Keyword.HASTE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("rules_text", "Haste\n{T}, Discard a card: Draw a card.")
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState, permanent: Creature) -> bool:  # noqa: ARG001
            controller = source.controller
            if controller is None or source.is_tapped:
                return False
            hand_cards = game.get_hand(controller).get_all()
            if not hand_cards:
                return False
            try:
                chosen = controller.choose_card(hand_cards, "card to discard")
            except Exception:
                chosen = hand_cards[0]
            if chosen not in hand_cards:
                return False
            source.is_tapped = True
            discard(game, controller, chosen)
            return True

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            draw_card(game, controller)

        ability = ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{T}, Discard a card: Draw a card.",
        )
        ability.tap_cost = True  # type: ignore[attr-defined]
        return [ability]
