"""Card implementation for Improvisation Capstone.

Oracle text:
    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with
    this name, you may cast a copy of it from exile without paying its mana
    cost at the beginning of each of your first main phases.)
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.casting import _SpellToGraveyardReplacementEvent, cast_spell_free
from engine.events import BeginningOfMainPhaseEvent, MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """{5}{R}{R} Sorcery — Lesson, CMC 7.

    Exile cards from top of library until MV sum >= 4, offer to cast each.
    Paradigm: self-exiles on resolution; recurring trigger from exile.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost(generic=5, pips={ManaType.RED: 2}))
        kwargs.setdefault("card_types", set())
        kwargs["card_types"] = kwargs["card_types"] | {CardType.SORCERY}
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault("keywords", Keyword(0))
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

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: GameState) -> None:
        """Exile cards from top of library until MV sum >= 4, offer casts."""
        controller = self.controller
        if controller is None:
            return

        library = controller.zones[Zone.LIBRARY]
        exile_zone = controller.zones[Zone.EXILE]

        exiled_cards: list[Any] = []
        mv_sum = 0

        while mv_sum < 4:
            top_cards = library.top(1)
            if not top_cards:
                break  # Library exhausted
            card = top_cards[0]
            library.remove(card)
            exile_zone.add(card)
            card_mv = getattr(card, "mana_cost", None)
            if card_mv is not None:
                mv_sum += card_mv.cmc
            exiled_cards.append(card)

        # Offer to cast each exiled nonland card for free.
        # Oracle says "cast spells" — lands aren't spells, so skip them.
        for exiled_card in exiled_cards:
            card_types = getattr(exiled_card, "card_types", set())
            if CardType.LAND in card_types:
                continue  # Lands can't be cast as spells
            may_cast = controller.choose_yes_no(
                f"Cast {getattr(exiled_card, 'name', 'card')} from exile without paying its mana cost?"
            )
            if may_cast:
                # Cast for free from exile via the proper casting pipeline
                try:
                    cast_spell_free(game, controller, exiled_card, Zone.EXILE)
                    # Drain the stack (resolve the cast spell)
                    from engine.state_based_actions import resolve_state_based_actions
                    while not game.stack.is_empty():
                        obj = game.stack.pop()
                        obj.on_resolve(game)
                        resolve_state_based_actions(game)
                except Exception:
                    pass  # If cast fails, card stays in exile

    # ------------------------------------------------------------------
    # Paradigm — replacement effect (self to exile)
    # ------------------------------------------------------------------

    def register_replacement_effects(self, game: GameState) -> None:
        """Register Paradigm replacement: route self to exile on resolution.

        Uses the same ReplacementManager mechanism as sos_1. The effect
        matches _SpellToGraveyardReplacementEvent for this card and
        redirects its destination to exile.
        """

        def _condition(g: Any, event: Any) -> bool:
            card = getattr(event, "spell", None) or getattr(event, "card", None)
            return card is self

        def _replacement(g: Any, event: Any) -> Any:
            event.destination = "exile"
            return event

        effect = ReplacementEffect(
            event_type=MoveToGraveyardReplacementEvent,
            source=self,
            condition=_condition,
            replacement=_replacement,
            controller=self.controller,
        )
        game.replacement_manager.register(effect)

    # ------------------------------------------------------------------
    # Paradigm — recurring trigger from exile
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        """Register the recurring Paradigm trigger: at the beginning of the
        controller's first main phase, may cast a copy from exile without
        paying its mana cost. Persists until this card leaves exile.
        """
        controller = self.controller

        def _condition(g: GameState, event: Any) -> bool:
            # Only fire if this card is still in exile
            exile_zone = controller.zones[Zone.EXILE]
            if not exile_zone.contains(self):
                return False
            # Only fire for the controller
            event_player = getattr(event, "player", None)
            return event_player is controller

        def _effect(g: GameState) -> None:
            # Check card is still in exile
            exile_zone = controller.zones[Zone.EXILE]
            if not exile_zone.contains(self):
                return
            # May choice
            may_cast = controller.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile without paying its mana cost?"
            )
            if not may_cast:
                return
            # Create a copy and cast it free through the proper pipeline.
            # Place copy in exile so cast_spell_free can move it to stack.
            copied = copy.copy(self)
            copied.controller = controller
            copied.owner = controller
            exile_zone = controller.zones[Zone.EXILE]
            exile_zone.add(copied)
            try:
                cast_spell_free(g, controller, copied, Zone.EXILE)
                # Resolve the cast copy immediately (drain stack)
                from engine.state_based_actions import resolve_state_based_actions
                while not g.stack.is_empty():
                    obj = g.stack.pop()
                    obj.on_resolve(g)
                    resolve_state_based_actions(g)
            except Exception:
                pass  # If cast fails, copy stays in exile

        trigger = TriggerRegistration(
            event_type=BeginningOfMainPhaseEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        )
        game.trigger_manager.register(trigger)

