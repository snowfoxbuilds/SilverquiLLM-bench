"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater. You may cast any number of spells from among
    them without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with this
    name, you may cast a copy of it from exile without paying its mana cost at
    the beginning of each of your first main phases.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards with total "
            "mana value 4 or greater. You may cast any number of spells from among them "
            "without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell with this "
            "name, you may cast a copy of it from exile without paying its mana cost at "
            "the beginning of each of your first main phases.)",
        )
        super().__init__(**kwargs)
        # Track whether Paradigm has been set up (so it only happens once).
        self._paradigm_registered: bool = False

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)

        # Step 1: Exile from top until total MV >= 4.
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top_cards = library.top(1)
            if not top_cards:
                break
            card = top_cards[0]
            library.remove(card)
            exile_zone = game.get_exile(controller)
            exile_zone.add(card)
            exiled.append(card)
            mv = _mana_value(card)
            total_mv += mv

        # Step 2: May cast any number of non-land spells from exiled cards for free.
        castable = [
            c for c in exiled
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        for card in castable:
            try:
                want = controller.choose_yes_no(f"Cast {getattr(card, 'name', 'card')} for free?")
                if want:
                    from engine.casting import cast_spell_free
                    cast_spell_free(game, controller, card, Zone.EXILE)
            except Exception:
                pass

        # Step 3: Paradigm — exile this spell and register recurring trigger.
        # The spell will be moved to graveyard by the engine after on_resolve.
        # We intercept by registering a one-shot replacement effect to redirect to exile.
        # Then register the recurring main-phase trigger.
        if not self._paradigm_registered:
            self._paradigm_registered = True
            _register_paradigm(game, controller, self)


def _mana_value(card: Any) -> int:
    """Return the mana value of a card (sum of all mana cost components)."""
    cost = getattr(card, "mana_cost", None)
    if cost is None:
        return 0
    return cost.generic + sum(cost.pips.values()) + len(getattr(cost, "hybrid", []))


def _register_paradigm(
    game: "GameState",
    controller: Any,
    capstone: "ImprovisationCapstone",
) -> None:
    """Exile the capstone (via replacement effect) and register the recurring trigger."""
    from engine.events import (
        BeginningOfPrecombatMainTriggeredEvent,
        SpellResolvesToGraveyardReplacementEvent,
    )
    from engine.replacement_effects import ReplacementEffect
    from engine.triggers import TriggerRegistration

    # Register a one-shot replacement effect to exile the capstone instead of graveyard.
    def _condition(g: Any, ev: Any) -> bool:
        return ev.card is capstone

    def _replacement(g: Any, ev: Any) -> Any:
        owner = getattr(capstone, "owner", controller)
        if owner is not None:
            exile_zone = owner.zones[Zone.EXILE]
            exile_zone.add(capstone)
        ev.prevented = True
        return ev

    # Use a one-shot sentinel source
    sentinel = object()
    repl = ReplacementEffect(
        event_type=SpellResolvesToGraveyardReplacementEvent,
        source=sentinel,
        condition=_condition,
        replacement=_replacement,
        controller=controller,
    )
    game.replacement_manager.register(repl)

    # Register recurring Paradigm trigger on each of the controller's first main phases.
    def _paradigm_condition(g: Any, event: Any) -> bool:
        return g.active_player is controller

    def _paradigm_effect(g: "GameState") -> None:
        # Check if capstone is still in exile.
        exile_zone = controller.zones[Zone.EXILE]
        if not exile_zone.contains(capstone):
            return

        try:
            want = controller.choose_yes_no("Cast a copy of Improvisation Capstone from exile?")
        except Exception:
            want = False

        if not want:
            return

        # Create a copy and cast it from exile.
        from engine.stack import copy_spell, StackObject
        from engine.casting import cast_spell_free
        import copy as _copy

        # Instead of casting the original (which would leave exile), create a copy
        # and put it in exile temporarily, then cast it from exile.
        copy_card = _copy.copy(capstone)
        copy_card.controller = controller
        copy_card.owner = getattr(capstone, "owner", controller)
        copy_card._paradigm_registered = True  # don't re-register Paradigm for the copy

        # Add copy to exile so cast_spell_free can find it.
        exile_zone.add(copy_card)
        try:
            cast_spell_free(g, controller, copy_card, Zone.EXILE)
        except Exception:
            exile_zone.remove(copy_card)

    # Use a persistent source object (not the sentinel) so it doesn't get unregistered.
    paradigm_source = object()
    game.trigger_manager.register(
        TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_paradigm_condition,
            effect=_paradigm_effect,
            source=paradigm_source,
            controller=controller,
        )
    )
