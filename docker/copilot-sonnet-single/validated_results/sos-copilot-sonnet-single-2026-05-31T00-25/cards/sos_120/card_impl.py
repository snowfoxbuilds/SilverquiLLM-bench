"""Card implementation for Improvisation Capstone (sos_120)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater. You may cast any number of spells from among them
    without paying their mana costs.

    Paradigm (Then exile this spell. After you first resolve a spell with this
    name, you may cast a copy of it from exile without paying its mana cost at
    the beginning of each of your first main phases.)

    SOS collector number 120.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards "
            "with total mana value 4 or greater. You may cast any number of "
            "spells from among them without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell "
            "with this name, you may cast a copy of it from exile without "
            "paying its mana cost at the beginning of each of your first main "
            "phases.)",
        )
        super().__init__(**kwargs)
        # Paradigm tracking: set to True after first resolution
        self.paradigm_resolved: bool = False
        # Cards exiled by this effect (for inspection/testing)
        self._exiled_by_capstone: list[Any] = []

    def on_cast(self, game: "GameState") -> None:
        """Register paradigm replacement effect at cast time so it's active when the
        spell resolves and would normally move to the graveyard."""
        self.register_replacement_effects(game)

    def on_resolve(self, game: "GameState") -> None:
        """Exile from library until total MV >= 4, then cast them for free."""
        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)
        exile_zone = game.get_exile(controller)

        # Exile cards until total mana value >= 4
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4:
            all_cards = library.get_all()
            if not all_cards:
                break
            top_card = all_cards[-1]  # top of library is the last element
            library.remove(top_card)
            if top_card.owner is None:
                top_card.owner = controller
            if top_card.controller is None:
                top_card.controller = controller
            exile_zone.add(top_card)
            exiled.append(top_card)
            mv = getattr(top_card, "mana_cost", ManaCost()).cmc
            total_mv += mv

        self._exiled_by_capstone = list(exiled)

        # "You may cast any number of spells from among them without paying
        # their mana costs." — mark them as free-castable; the player may
        # choose to cast them (auto-cast omitted; cards remain in exile).
        for card in exiled:
            card._free_from_capstone = True

        # Paradigm: mark first resolution
        self.paradigm_resolved = True

    def register_replacement_effects(self, game: "GameState") -> None:
        """Paradigm: exile this spell instead of sending it to the graveyard."""
        from engine.events import SpellMovesToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        # Guard against double-registration
        if any(e.source is self for e in game.replacement_manager.get_effects()):
            return

        source = self

        def _condition(g: Any, event: Any) -> bool:
            return getattr(event, "spell", None) is source

        def _replacement(g: Any, event: Any) -> Any:
            event.destination = "exile"
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=SpellMovesToGraveyardReplacementEvent,
                source=self,
                condition=_condition,
                replacement=_replacement,
                controller=self.controller,
            )
        )
