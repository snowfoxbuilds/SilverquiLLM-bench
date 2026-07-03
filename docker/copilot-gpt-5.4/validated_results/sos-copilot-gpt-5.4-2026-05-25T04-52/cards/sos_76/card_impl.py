"""Card implementation for Cheerful Osteomancer // Raise Dead."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class RaiseDead(Sorcery):
    """Prepared spell copy for Cheerful Osteomancer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Raise Dead")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        graveyard = game.get_graveyard(controller)
        creature_cards = [
            card
            for card in graveyard.get_all()
            if CardType.CREATURE in getattr(card, "card_types", set())
        ]
        if not creature_cards:
            return
        try:
            chosen = controller.choose_card(creature_cards, "creature card to return to hand")
        except Exception:
            chosen = creature_cards[0]
        if chosen is None or not graveyard.contains(chosen):
            return
        move_to_zone(game, chosen, Zone.GRAVEYARD, Zone.HAND)


class CheerfulOsteomancerRaiseDead(Creature):
    """Cheerful Osteomancer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cheerful Osteomancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("subtypes", {"Orc", "Warlock"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "This creature enters prepared. (While it's prepared, you may cast a copy "
            "of its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return RaiseDead(owner=self.owner, controller=self.controller)
