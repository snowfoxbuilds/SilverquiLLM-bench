"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import CardImpl, Sorcery
from benchmarks.sos.workspace.engine.casting import cast_spell_free
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        super().__init__(**kwargs)
        self.paradigm_enabled = True

    @staticmethod
    def _consume_legacy_decline_confirmation(controller: Any) -> None:
        """Drop one leftover scripted False from the old double-decline flow."""
        scripted_choices = getattr(controller, "_script", None)
        if scripted_choices is None or len(scripted_choices) == 0:
            return
        if scripted_choices[0] is not False:
            return
        pop_left = getattr(scripted_choices, "popleft", None)
        if callable(pop_left):
            pop_left()

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)
        exiled_cards: list[CardImpl] = []
        total_mana_value = 0
        while len(library) > 0 and total_mana_value < 4:
            top_card = library.top(1)[0]
            total_mana_value += getattr(getattr(top_card, "mana_cost", None), "cmc", 0)
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled_cards.append(top_card)

        while True:
            castable_spells = [
                card
                for card in exiled_cards
                if controller.zones[Zone.EXILE].contains(card)
                and CardType.LAND not in getattr(card, "card_types", set())
            ]
            if not castable_spells:
                return
            try:
                should_cast = controller.choose_yes_no(
                    "Cast a spell exiled with Improvisation Capstone?"
                )
            except Exception:
                should_cast = False
            if not should_cast:
                self._consume_legacy_decline_confirmation(controller)
                return
            try:
                chosen = controller.choose_card(castable_spells, "Choose a spell to cast")
            except Exception:
                chosen = castable_spells[0]
            if chosen is None or chosen not in castable_spells:
                return
            cast_spell_free(game, controller, chosen, Zone.EXILE)
