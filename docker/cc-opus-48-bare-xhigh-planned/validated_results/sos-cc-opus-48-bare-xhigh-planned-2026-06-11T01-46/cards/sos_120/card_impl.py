"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy as _copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _mana_value(card: Any) -> int:
    cost = getattr(card, "mana_cost", None)
    return cost.cmc if cost is not None else 0


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater.  You may cast any number of spells from among them
    without paying their mana costs.
    Paradigm (Then exile this spell.  After you first resolve a spell with this
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
            "spells from among them without paying their mana costs.\nParadigm "
            "(Then exile this spell. After you first resolve a spell with this "
            "name, you may cast a copy of it from exile without paying its mana "
            "cost at the beginning of each of your first main phases.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return

        self._improvise(game, controller)

        # Paradigm sets up only from the real cast, never from a copy.
        if not getattr(self, "_is_paradigm_copy", False):
            self._register_exile_instead(game)
            self._register_paradigm(game, controller)

    # ------------------------------------------------------------------
    # Primary effect
    # ------------------------------------------------------------------

    def _improvise(self, game: "GameState", controller: "Player") -> None:
        from engine.casting import cast_spell_free
        from engine.zones import move_to_zone

        library = game.get_library(controller)
        exiled: list[Any] = []
        total = 0
        while total < 4 and len(library) > 0:
            top = library.top(1)[0]
            move_to_zone(game, top, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top)
            total += _mana_value(top)

        for card in exiled:
            # Lands aren't spells — they stay exiled.
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            if not game.get_exile(controller).contains(card):
                continue
            if controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} for free?"
            ):
                cast_spell_free(game, controller, card, Zone.EXILE)

    # ------------------------------------------------------------------
    # Paradigm
    # ------------------------------------------------------------------

    def _register_exile_instead(self, game: "GameState") -> None:
        """Then exile this spell (instead of going to the graveyard)."""
        from engine.events import SpellResolvesToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        card = self

        def _condition(g: "GameState", event: Any) -> bool:
            return getattr(event, "spell", None) is card

        def _replacement(g: "GameState", event: Any) -> Any:
            event.destination = "exile"
            g.replacement_manager.unregister(card)  # one-shot
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=SpellResolvesToGraveyardReplacementEvent,
                source=card,
                condition=_condition,
                replacement=_replacement,
                controller=self.controller,
            )
        )

    def _register_paradigm(self, game: "GameState", controller: "Player") -> None:
        """Each of your first main phases, you may cast a copy from exile."""
        from engine.triggers import TriggerRegistration
        from engine.events import BeginningOfPrecombatMainTriggeredEvent

        original = self

        def _condition(g: "GameState", event: Any) -> bool:
            return (
                g.active_player is controller
                and g.get_exile(controller).contains(original)
            )

        def _effect(g: "GameState") -> None:
            from engine.casting import cast_spell_free

            if not controller.choose_yes_no(
                "Paradigm: cast a copy of Improvisation Capstone from exile?"
            ):
                return
            copy_card = _copy.copy(original)
            copy_card._is_paradigm_copy = True
            copy_card.is_token = True  # the copy ceases to exist after resolving
            copy_card.owner = controller
            copy_card.controller = controller
            for attr in ("chosen_targets", "colors_spent", "mana_spent"):
                if hasattr(copy_card, attr):
                    delattr(copy_card, attr)
            g.get_exile(controller).add(copy_card)
            cast_spell_free(g, controller, copy_card, Zone.EXILE)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=original,
                controller=controller,
            )
        )
