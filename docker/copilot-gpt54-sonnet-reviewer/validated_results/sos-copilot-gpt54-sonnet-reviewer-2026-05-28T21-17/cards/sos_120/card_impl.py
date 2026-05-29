"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import CardImpl, Sorcery
from engine.casting import cast_spell_free
from engine.events import BeginningOfFirstMainPhaseTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState


if not hasattr(Keyword, "PARADIGM"):
    Keyword.PARADIGM = Keyword(max(keyword.value for keyword in Keyword) << 1)  # type: ignore[attr-defined]


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault("keywords", Keyword.PARADIGM)
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards with total mana value 4 "
            "or greater. You may cast any number of spells from among them without paying their mana "
            "costs.\nParadigm (Then exile this spell. After you first resolve a spell with this name, "
            "you may cast a copy of it from exile without paying its mana cost at the beginning of "
            "each of your first main phases.)",
        )
        super().__init__(**kwargs)
        self._original_keywords = self.keywords

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller or self.owner
        if controller is None:
            return

        total_mana_value = 0
        exiled_cards: list[CardImpl] = []
        library = game.get_library(controller)

        while len(library) > 0 and total_mana_value < 4:
            next_card = library.top(1)[0]
            move_to_zone(game, next_card, Zone.LIBRARY, Zone.EXILE)
            exiled_cards.append(next_card)
            total_mana_value += getattr(getattr(next_card, "mana_cost", None), "cmc", 0)

        for card in exiled_cards:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            if controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} without paying its mana cost?"
            ):
                cast_spell_free(game, controller, card, Zone.EXILE)

        self._graveyard_destination_override = Zone.EXILE

        if not getattr(self, "_is_paradigm_copy", False):
            self._register_paradigm_trigger(game)

    def _register_paradigm_trigger(self, game: "GameState") -> None:
        if getattr(self, "_paradigm_trigger_registered", False):
            return

        controller = self.controller or self.owner
        if controller is None:
            return

        source = self

        def _condition(game: "GameState", event: BeginningOfFirstMainPhaseTriggeredEvent) -> bool:
            exile = game.get_exile(source.owner or controller)
            return event.player is controller and exile.contains(source)

        def _effect(game: "GameState") -> None:
            current_controller = source.controller or source.owner
            if current_controller is None:
                return
            exile = game.get_exile(source.owner or current_controller)
            if not exile.contains(source):
                return
            if not current_controller.choose_yes_no(
                f"Cast a copy of {source.name} from exile without paying its mana cost?"
            ):
                return

            spell_copy = ImprovisationCapstone(
                owner=source.owner or current_controller,
                controller=current_controller,
            )
            spell_copy._is_paradigm_copy = True
            game.get_exile(spell_copy.owner or current_controller).add(spell_copy)
            cast_spell_free(game, current_controller, spell_copy, Zone.EXILE)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfFirstMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
        self._paradigm_trigger_registered = True
