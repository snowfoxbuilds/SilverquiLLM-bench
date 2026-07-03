"""Card implementation for Jadzi, Steward of Fate // Oracle's Gift."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.game import discard, draw_card
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class OraclesGift(Sorcery):
    """Prepared spell copy for Jadzi."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Oracle's Gift")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{X}{U}"))
        super().__init__(**kwargs)


class JadziStewardOfFateOraclesGift(Creature):
    """Jadzi, Steward of Fate."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Jadzi, Steward of Fate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        self.become_prepared()
        if controller is None:
            return
        for _ in range(2):
            draw_card(game, controller)
        for _ in range(2):
            hand = game.get_hand(controller)
            cards_in_hand = list(hand.get_all())
            if not cards_in_hand:
                break
            chosen = controller.choose_card(cards_in_hand, "Choose a card to discard")
            discard(game, controller, chosen)

    def create_prepared_spell_copy(self) -> Sorcery:
        return OraclesGift(owner=self.owner, controller=self.controller)
