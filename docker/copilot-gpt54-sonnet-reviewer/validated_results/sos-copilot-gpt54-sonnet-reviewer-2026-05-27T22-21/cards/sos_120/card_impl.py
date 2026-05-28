"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.casting import cast_spell_free
from engine.events import MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.stack import StackObject
from engine.types import CardType, Color, ManaCost, Phase, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "colors",
            {Color.RED},
        )
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards with total mana value 4 "
            "or greater. You may cast any number of spells from among them without paying their mana "
            "costs.\nParadigm (Then exile this spell. After you first resolve a spell with this name, "
            "you may cast a copy of it from exile without paying its mana cost at the beginning of "
            "each of your first main phases.)",
        )
        super().__init__(**kwargs)
        self._paradigm_armed: bool = False
        self._is_paradigm_copy: bool = False

    def on_cast(self, game: "GameState") -> None:
        """Improvisation Capstone exiles itself instead of going to the graveyard."""
        if self._is_paradigm_copy:
            return

        source = self

        def _condition(_game: Any, event: "MoveToGraveyardReplacementEvent") -> bool:
            return event.card is source

        def _replacement(
            _game: Any,
            event: "MoveToGraveyardReplacementEvent",
        ) -> "MoveToGraveyardReplacementEvent":
            event.destination = "exile"
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=self,
                condition=_condition,
                replacement=_replacement,
                controller=self.controller,
            )
        )

    def on_resolve(self, game: "GameState") -> None:
        """Exile cards to mana value four, then free-cast spells among them."""
        exiled_cards = self._exile_until_total_mana_value_reaches_four(game)
        self._cast_exiled_spells(game, exiled_cards)
        self._arm_paradigm(game)

    def _exile_until_total_mana_value_reaches_four(self, game: "GameState") -> list[Any]:
        controller = self.controller
        if controller is None:
            return []

        library = game.get_library(controller)
        exiled_cards: list[Any] = []
        total_mana_value = 0

        while total_mana_value < 4:
            cards = library.get_all()
            if not cards:
                break
            top_card = cards[-1]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled_cards.append(top_card)
            total_mana_value += getattr(getattr(top_card, "mana_cost", None), "cmc", 0)

        return exiled_cards

    def _cast_exiled_spells(self, game: "GameState", exiled_cards: list[Any]) -> None:
        controller = self.controller
        if controller is None:
            return

        for card in exiled_cards:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            try:
                if controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} without paying its mana cost?"
                ):
                    cast_spell_free(game, controller, card, Zone.EXILE)
            except Exception:
                continue

    def _arm_paradigm(self, game: "GameState") -> None:
        if self._is_paradigm_copy or self._paradigm_armed:
            return

        controller = self.controller
        owner = self.owner if self.owner is not None else controller
        if controller is None or owner is None:
            return

        self._paradigm_armed = True
        source = self

        def _paradigm_callback(g: "GameState") -> None:
            exile = g.get_exile(owner)
            if not exile.contains(source):
                return

            if g.phase is Phase.PRECOMBAT_MAIN:
                try:
                    should_cast = controller.choose_yes_no(
                        f"Cast a copy of {source.name} from exile without paying its mana cost?"
                    )
                except Exception:
                    should_cast = False
                if should_cast:
                    g.stack.push(source._create_paradigm_copy_stack_object(controller))

            g.schedule_beginning_of_next_main_phase(controller, _paradigm_callback)

        game.schedule_beginning_of_next_main_phase(controller, _paradigm_callback)

    def _create_paradigm_copy_stack_object(self, controller: Any) -> StackObject:
        copied_spell = copy.copy(self)
        copied_spell.owner = self.owner
        copied_spell.controller = controller
        copied_spell._is_paradigm_copy = True
        copied_spell._paradigm_armed = True

        stack_obj = StackObject(
            source=copied_spell,
            controller=controller,
            targets=[],
            on_resolve=lambda g: copied_spell.on_resolve(g),
        )
        return stack_obj
