"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import ManaCost, Zone

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
    """


    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Lesson"}
        kwargs.setdefault(
            "rules_text",
            (
                "Exile cards from the top of your library until you exile cards with "
                "total mana value 4 or greater. You may cast any number of spells from "
                "among them without paying their mana costs.\n"
                "Paradigm (Then exile this spell. After you first resolve a spell with "
                "this name, you may cast a copy of it from exile without paying its mana "
                "cost at the beginning of each of your first main phases.)"
            ),
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Resolve the main exile-from-library effect, then handle Paradigm."""
        controller = self.controller
        if controller is None:
            return

        # --- Main effect: exile cards from library until total MV >= 4 ---
        library = game.get_library(controller)
        exile = game.get_exile(controller)
        total_mv = 0

        while total_mv < 4:
            all_cards = library.get_all()
            if not all_cards:
                break  # Library exhausted
            # Top card is the last element in the list
            top_card = all_cards[-1]
            card_mv = getattr(getattr(top_card, "mana_cost", None), "cmc", 0) or 0
            library.remove(top_card)
            exile.add(top_card)
            total_mv += card_mv

        # --- Paradigm: exile this spell ---
        # Remove this card from the stack (if it's there) and move to exile
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(self):
            stack_zone.remove(self)
            exile.add(self)

        # --- Paradigm: register trigger on first resolution ---
        # UNVERIFIED: "you may cast any number of spells from among them without paying
        #   mana costs" — cast-from-exile pipeline not in engine test infrastructure
        # UNVERIFIED: "Paradigm: create a copy of this object in exile" —
        #   copy-creation API for non-token objects not implemented
        if not getattr(game, '_paradigm_capstone_registered', False):
            game._paradigm_capstone_registered = True
            source = self
            ctrl_ref = controller

            def _paradigm_effect(game: "GameState") -> None:
                # Offer player a chance to cast a copy from exile for free.
                # (For simulation purposes, the trigger is registered; casting
                # logic would be handled by the game engine's casting system.)
                pass

            game.trigger_manager.register(
                TriggerRegistration(
                    event_type=BeginningOfMainPhaseTriggeredEvent,
                    condition=lambda game, event: game.active_player is ctrl_ref,
                    effect=_paradigm_effect,
                    source=source,
                    controller=ctrl_ref,
                )
            )
