"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone
from engine.events import TriggeredEvent
from engine.triggers import TriggerRegistration

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone -- {5}{R}{R} -- Sorcery -- Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells
    from among them without paying their mana costs.

    Paradigm (Then exile this spell. After you first resolve a spell
    with this name, you may cast a copy of it from exile without paying
    its mana cost at the beginning of each of your first main phases.)

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
            "paying its mana cost at the beginning of each of your first "
            "main phases.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        """Resolve: exile from library, free-cast, then Paradigm."""
        controller = self.controller or self.owner
        if controller is None:
            return

        # --- Main effect: exile from top of library until total MV >= 4 ---
        library = game.get_library(controller)
        exile = game.get_exile(controller)
        exiled_cards: list[Any] = []
        total_mv = 0

        while len(library) > 0 and total_mv < 4:
            # Take from the top of the library (last element)
            top_cards = library.top(1)
            if not top_cards:
                break
            card = top_cards[0]
            library.remove(card)
            exile.add(card)
            exiled_cards.append(card)
            # Add the card's mana value to the running total
            card_cost = getattr(card, "mana_cost", None)
            if card_cost is not None:
                total_mv += card_cost.cmc

        # --- Free-cast from among exiled cards ---
        # For each non-land exiled card, ask the controller whether to cast it
        for card in exiled_cards:
            card_types = getattr(card, "card_types", set())
            # Lands cannot be cast (they are not spells)
            if CardType.LAND in card_types:
                continue

            # Ask the player whether they want to cast this spell
            try:
                wants_to_cast = controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} without paying its mana cost?"
                )
            except Exception:
                continue

            if not wants_to_cast:
                continue

            # Cast the spell: resolve it immediately (simplified free-cast)
            # Remove from exile first
            if exile.contains(card):
                exile.remove(card)

            # Set controller/owner
            card.controller = controller
            if card.owner is None:
                card.owner = controller

            # Resolve the spell
            card.on_resolve(game)

            # Determine where the card goes after resolution
            permanent_types = {
                CardType.CREATURE, CardType.ENCHANTMENT,
                CardType.ARTIFACT, CardType.PLANESWALKER
            }
            if card_types & permanent_types:
                # Permanents go to the battlefield
                battlefield = game.get_battlefield(controller)
                battlefield.add(card)
            else:
                # Non-permanents (instant/sorcery) go to the graveyard
                graveyard = game.get_graveyard(controller)
                graveyard.add(card)

        # --- Paradigm ---
        # 1. Exile this spell (set marker for _resolve_spell in casting pipeline)
        #    The _paradigm_exile flag tells _resolve_spell to move the card
        #    from stack to exile instead of stack to graveyard, consistent with
        #    the _dawning_archaic_exile pattern from sos_1.
        self._paradigm_exile = True  # type: ignore[attr-defined]

        # 2. Register a delayed trigger for Paradigm (only on first resolution)
        # Use a game-level tracker to ensure we only register once per card name
        if not hasattr(game, "_paradigm_registered"):
            game._paradigm_registered = set()  # type: ignore[attr-defined]

        card_name = self.name
        if card_name not in game._paradigm_registered:  # type: ignore[attr-defined]
            game._paradigm_registered.add(card_name)  # type: ignore[attr-defined]

            paradigm_controller = controller
            paradigm_source = self

            def _paradigm_condition(g: GameState, event: Any) -> bool:
                """Fire at the beginning of controller's precombat main phase."""
                from engine.types import Phase
                active = getattr(g, "active_player", None)
                phase = getattr(g, "phase", None)
                if active is not paradigm_controller:
                    return False
                return phase == Phase.PRECOMBAT_MAIN

            def _paradigm_effect(g: GameState) -> None:
                """Cast a copy of Improvisation Capstone from exile for free.

                Finds the exiled original, creates a shallow copy, and offers
                the controller a free-cast.  The copy resolves immediately
                using the simplified free-cast pipeline (same as the main
                effect's free-cast of exiled spells).
                """
                import copy as _copy

                ctrl = paradigm_controller
                if ctrl is None:
                    return

                # Find an Improvisation Capstone in exile
                exile_zone = g.get_exile(ctrl)
                original = None
                for c in exile_zone.get_all():
                    if getattr(c, "name", "") == "Improvisation Capstone":
                        original = c
                        break

                if original is None:
                    return

                # Ask the controller whether they want to cast the copy
                try:
                    wants_to_cast = ctrl.choose_yes_no(
                        "Cast a copy of Improvisation Capstone from exile "
                        "without paying its mana cost?"
                    )
                except Exception:
                    return

                if not wants_to_cast:
                    return

                # Create a copy of the card
                copied = _copy.copy(original)
                copied.controller = ctrl
                copied.owner = ctrl

                # Resolve the copy immediately (simplified free-cast)
                copied.on_resolve(g)

            trigger_reg = TriggerRegistration(
                event_type=TriggeredEvent,
                condition=_paradigm_condition,
                effect=_paradigm_effect,
                source=self,
                controller=controller,
            )
            game.trigger_manager.register(trigger_reg)
