"""Card implementation for Emeritus of Woe // Demonic Tutor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EndStepTriggeredEvent
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfWoeDemonicTutor(Creature):
    """Emeritus of Woe // Demonic Tutor — {3}{B} — 5/4 — Vampire Warlock.

    This creature enters prepared. (While it's prepared, you may cast a copy
    of its spell. Doing so unprepares it.)
    At the beginning of your end step, if two or more creatures died this turn,
    this creature becomes prepared.

    Spell side: Demonic Tutor {1}{B} — Search your library for a card, put it
    into your hand.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Woe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Warlock"})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "This creature enters prepared.\n"
            "At the beginning of your end step, if two or more creatures "
            "died this turn, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = True

    def on_enter(self, game: GameState) -> None:
        """This creature enters the battlefield prepared."""
        self.is_prepared = True

    def can_cast_prepared_spell(self, game: GameState) -> bool:
        """Check if the prepared spell can be cast."""
        return self.is_prepared

    def cast_prepared_spell(self, game: GameState) -> None:
        """Cast the prepared spell (Demonic Tutor): search library, put card in hand.

        Unprepares this creature.
        """
        self.is_prepared = False
        controller = self.controller
        library = game.get_library(controller)
        hand = game.get_hand(controller)
        all_cards = library.get_all()
        if all_cards:
            # Pick the first card (in a real game, player would choose)
            card = all_cards[0]
            library.remove(card)
            hand.add(card)

    def check_end_step_trigger(self, game: GameState) -> None:
        """Check and apply the end step trigger."""
        deaths = game.get_creature_deaths_this_turn()
        if len(deaths) >= 2:
            self.is_prepared = True

    def end_step_condition(self, game: GameState, event: EndStepTriggeredEvent) -> bool:
        """Check if the end step trigger condition is met.

        Returns True only if it's the controller's end step AND 2+ creatures
        died this turn.
        """
        if event.player is not self.controller:
            return False
        deaths = game.get_creature_deaths_this_turn()
        return len(deaths) >= 2
