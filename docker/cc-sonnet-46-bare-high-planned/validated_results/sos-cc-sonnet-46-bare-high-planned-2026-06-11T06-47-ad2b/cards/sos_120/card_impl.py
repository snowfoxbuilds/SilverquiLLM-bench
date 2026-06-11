"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy as _copy_module
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Supertype, Zone

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
            "Exile cards from the top of your library until you exile cards with "
            "total mana value 4 or greater. You may cast any number of spells from "
            "among them without paying their mana costs.\nParadigm (Then exile this "
            "spell. After you first resolve a spell with this name, you may cast a "
            "copy of it from exile without paying its mana cost at the beginning of "
            "each of your first main phases.)",
        )
        super().__init__(**kwargs)
        # Set to True once Paradigm has been activated (first resolution).
        self._paradigm_activated: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """Main effect + Paradigm."""
        controller = self.controller
        if controller is None:
            return

        # --- Main effect: exile from library until total MV >= 4 ---
        exiled_cards = _exile_from_library(game, controller)

        # --- Cast any number of the exiled cards for free ---
        _offer_cast_exiled(game, controller, exiled_cards)

        # --- Paradigm: exile this card, then register recurring trigger ---
        _apply_paradigm(game, controller, self)

    # Override the default Sorcery graveyard movement — Paradigm moves it to exile.
    # The actual exile is handled in on_resolve via _apply_paradigm before the
    # engine moves it, so we mark _paradigm_activated to suppress on_resolve repetition.


def _exile_from_library(game: "GameState", controller: Any) -> list[Any]:
    """Peel cards from the top of the library until total MV >= 4."""
    library = controller.zones[Zone.LIBRARY]
    exile_zone = game.get_exile(controller)
    total_mv = 0
    exiled: list[Any] = []
    while len(library) > 0 and total_mv < 4:
        card = library.top(1)[0]
        library.remove(card)
        card.owner = card.owner or controller
        card.controller = controller
        exile_zone.add(card)
        exiled.append(card)
        cost = getattr(card, "mana_cost", None)
        if cost is not None:
            total_mv += cost.cmc
    return exiled


def _offer_cast_exiled(
    game: "GameState", controller: Any, exiled_cards: list[Any]
) -> None:
    """Offer the controller the option to cast each exiled card for free."""
    from engine.casting import cast_spell_free, CastingError

    castable = [
        c for c in exiled_cards
        if CardType.LAND not in getattr(c, "card_types", set())
    ]

    # Ask which cards to cast; player may choose multiple via repeated choose_card.
    # Pattern: keep asking until None is returned.
    remaining = list(castable)
    while remaining:
        try:
            chosen = controller.choose_card(remaining, "cast for free from exile?")
        except Exception:
            break
        if chosen is None or chosen not in remaining:
            break
        remaining.remove(chosen)
        try:
            cast_spell_free(game, controller, chosen, Zone.EXILE)
        except CastingError:
            pass  # Skip uncastable cards (e.g. can_cast fails).


def _apply_paradigm(game: "GameState", controller: Any, card: "ImprovisationCapstone") -> None:
    """Apply Paradigm: exile this card; if first resolution, register E2 trigger.

    on_resolve fires before the engine moves the card to the graveyard.
    We remove the card from the stack zone now so that the engine's subsequent
    move_to_zone(STACK→GRAVEYARD) call can't find it and returns early.
    """
    # Remove from stack zone to preempt the engine's graveyard move.
    stack_zone = controller.zones[Zone.STACK]
    if stack_zone.contains(card):
        stack_zone.remove(card)
    exile_zone = game.get_exile(controller)
    if not exile_zone.contains(card):
        exile_zone.add(card)

    if card._paradigm_activated:
        return
    card._paradigm_activated = True

    # Register the recurring E2 trigger.
    _register_paradigm_trigger(game, controller, card)


def _register_paradigm_trigger(
    game: "GameState", controller: Any, source_card: Any
) -> None:
    """Register a recurring BeginningOfPrecombatMainTriggeredEvent trigger."""
    from engine.casting import cast_spell_free, CastingError
    from engine.events import BeginningOfPrecombatMainTriggeredEvent
    from engine.triggers import TriggerRegistration

    def _condition(game: Any, event: Any) -> bool:
        return game.active_player is controller

    def _effect(game: "GameState") -> None:
        exile_zone = game.get_exile(controller)
        if not exile_zone.contains(source_card):
            return
        # Offer to cast a copy of Improvisation Capstone from exile.
        try:
            cast_it = controller.choose_yes_no(
                "Cast Improvisation Capstone copy from exile?"
            )
        except Exception:
            cast_it = False
        if not cast_it:
            return
        # Create a copy, place it in exile temporarily, then cast it from exile.
        cap_copy = _copy_module.copy(source_card)
        cap_copy.controller = controller
        cap_copy.owner = controller
        cap_copy._paradigm_activated = True  # copies don't re-activate Paradigm
        exile_zone.add(cap_copy)
        try:
            cast_spell_free(game, controller, cap_copy, Zone.EXILE)
        except CastingError:
            exile_zone.remove(cap_copy)

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=source_card,
            controller=controller,
        )
    )
