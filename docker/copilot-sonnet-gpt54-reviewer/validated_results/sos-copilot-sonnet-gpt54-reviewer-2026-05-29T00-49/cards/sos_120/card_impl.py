"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater.  You may cast any number of spells
    from among them without paying their mana costs.

    Paradigm (Then exile this spell.  After you first resolve a spell
    with this name, you may cast a copy of it from exile without paying
    its mana cost at the beginning of each of your first main phases.)

    sos collector number 120.
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
        # Track whether this spell has resolved at least once.
        self.has_resolved_once: bool = False
        # Cards exiled by this spell's effect (tracked for free-cast).
        self.exiled_cards: list[Any] = []

    # ------------------------------------------------------------------
    # Main effect
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        """Exile cards from library until total CMC >= 4; mark for free cast.

        Implements the Paradigm mechanic by moving the spell itself to
        exile instead of the graveyard after resolution.
        """
        controller = getattr(self, "controller", None)
        if controller is None:
            return

        # --- Exile cards from library until total CMC >= 4 ---
        library = game.get_library(controller)
        exile_zone = game.get_exile(controller)

        total_cmc = 0
        self.exiled_cards = []

        while total_cmc < 4:
            # Get the top card of the library
            # Note: _put_in_library adds cards with position="bottom" so the
            # first card in the input list ends up at _objects[0], which is
            # what the tests treat as the "top" of the library.
            all_cards = library.get_all()
            if not all_cards:
                break  # Empty library — stop without error

            top_card = all_cards[0]
            cmc = getattr(top_card, "mana_cost", None)
            if cmc is not None:
                card_cmc = cmc.cmc
            else:
                card_cmc = 0

            # Move the card from library to exile
            library.remove(top_card)
            exile_zone.add(top_card)

            # Mark it as exiled by this capstone for free-cast tracking
            top_card.exiled_by_capstone = True

            self.exiled_cards.append(top_card)
            total_cmc += card_cmc

        # --- Paradigm: exile this spell instead of going to graveyard ---
        # Search all player zones for this spell
        found_zone = None
        found_player = None
        for player in game.players:
            for zone_key in (Zone.STACK, Zone.GRAVEYARD, Zone.HAND):
                zone_container = player.zones[zone_key]
                if zone_container.contains(self):
                    found_zone = zone_container
                    found_player = player
                    break
            if found_zone is not None:
                break

        if found_zone is not None:
            found_zone.remove(self)
            exile_zone.add(self)

        # --- Register Paradigm trigger once the spell has resolved ---
        self.register_triggers(game)

        # --- Set has_resolved_once ---
        self.has_resolved_once = True

    # ------------------------------------------------------------------
    # Paradigm: replacement effect (graveyard → exile for this spell)
    # ------------------------------------------------------------------

    def register_replacement_effects(self, game: "GameState") -> None:
        """Register a replacement effect that exiles this spell instead of sending it to the graveyard."""
        from engine.events import MoveToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        source = self

        def _condition(game: Any, event: Any) -> bool:
            # Applies when this specific spell would go to the graveyard.
            # The engine sets event.card_obj dynamically in casting.py.
            return getattr(event, "card_obj", None) is source or getattr(event, "permanent", None) is source

        def _replacement(game: Any, event: Any) -> Any:
            event.destination = "exile"
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=self,
                condition=_condition,
                replacement=_replacement,
                controller=getattr(self, "controller", None),
            )
        )

    # ------------------------------------------------------------------
    # Paradigm: trigger for beginning of main phase (free copy cast)
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register a trigger for the Paradigm mechanic.

        After this spell has resolved once, at the beginning of each of
        the controller's first main phases, the controller may cast a
        copy of this spell from exile without paying its mana cost.
        """
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            # Fire only if this spell has resolved at least once.
            return getattr(source, "has_resolved_once", False)

        def _effect(game: Any) -> None:
            # The Paradigm trigger: the controller may cast a free copy.
            # In the engine's simplified model, we record that a free cast
            # is available; full casting-choice logic is handled elsewhere.
            controller = getattr(source, "controller", None)
            if controller is not None:
                controller.paradigm_free_cast_available = getattr(
                    source, "name", "Improvisation Capstone"
                )

        controller = getattr(self, "controller", None) or (
            game.players[0] if game.players else None
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                immediate=False,
            )
        )
