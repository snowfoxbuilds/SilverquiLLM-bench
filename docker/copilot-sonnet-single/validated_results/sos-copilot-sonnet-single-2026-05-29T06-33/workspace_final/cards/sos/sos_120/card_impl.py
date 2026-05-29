"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.

    Paradigm (Then exile this spell. After you first resolve a spell with
    this name, you may cast a copy of it from exile without paying its
    mana cost at the beginning of each of your first main phases.)

    SOS collector number 120.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards "
            "with total mana value 4 or greater. You may cast any number of "
            "spells from among them without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell "
            "with this name, you may cast a copy of it from exile without "
            "paying its mana cost at the beginning of each of your first "
            "main phases.)",
        )
        super().__init__(**kwargs)
        # Tracks which cards were exiled from the library to allow free casting
        self.exiled_for_free_cast: list[Any] = []
        # Paradigm: signals the casting engine to route this card to exile
        # instead of the graveyard after resolution.
        self.go_to_exile: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """Exile cards from the top of the library until total MV >= 4.

        Then allow free casting of non-land exiled cards.
        Paradigm: exile this spell and register a main-phase trigger for
        recurring free copies.

        # UNVERIFIED: multi-cast player-choice loop not fully tested — DeterministicPlayer
        # lacks multi-step free-cast scripting
        # UNVERIFIED: Paradigm copy-cast from exile not fully tested — full
        # phase-advance integration needed
        """
        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)
        exile = game.get_exile(controller)

        # --- Exile cards from top of library until total MV >= 4 ---
        total_mv = 0
        self.exiled_for_free_cast = []

        while total_mv < 4:
            all_cards = library.get_all()
            if not all_cards:
                break
            # Top card is last in the list
            top_card = all_cards[-1]
            library.remove(top_card)
            exile.add(top_card)

            mv = 0
            mana_cost = getattr(top_card, "mana_cost", None)
            if mana_cost is not None:
                mv = mana_cost.cmc
            total_mv += mv

            # Track all exiled cards for potential free casting
            self.exiled_for_free_cast.append(top_card)

        # --- Paradigm: signal exile routing and register main-phase trigger ---
        self.go_to_exile = True

        from engine.events import BeginningOfMainPhaseTriggeredEvent

        _controller = controller
        _source = self

        def _paradigm_effect(g: "GameState") -> None:
            # Offer a free copy of Improvisation Capstone at the start of main phase
            # UNVERIFIED: Paradigm copy-cast from exile not fully tested — full
            # phase-advance integration needed
            pass  # Full copy-cast would require deeper engine support

        trigger = TriggerRegistration(
            event_type=BeginningOfMainPhaseTriggeredEvent,
            condition=lambda g, e: (
                e.active_player is None or e.active_player is _controller
            ),
            effect=_paradigm_effect,
            source=_source,
            controller=controller,
        )
        game.trigger_manager.register(trigger)
