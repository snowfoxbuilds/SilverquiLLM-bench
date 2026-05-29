"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.casting import cast_spell_copy, cast_spell_free, spell_has_legal_targets
from engine.events import (
    BeginningOfMainPhaseTriggeredEvent,
    MoveToGraveyardReplacementEvent,
)
from engine.replacement_effects import ReplacementEffect
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, Phase, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState


@dataclass
class _ParadigmTrigger:
    """Identity-bearing source for Improvisation Capstone's Paradigm trigger."""

    card: Any
    controller: Any


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards with total mana "
            "value 4 or greater. You may cast any number of spells from among them without "
            "paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell with this name, "
            "you may cast a copy of it from exile without paying its mana cost at the "
            "beginning of each of your first main phases.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Exile through mana value 4, free-cast spells, and set up Paradigm."""
        controller = self.controller
        if controller is None:
            return

        exiled_cards: list[Any] = []
        total_mana_value = 0
        library = game.get_library(controller)

        while total_mana_value < 4 and len(library) > 0:
            next_card = library.top(1)[0]
            move_to_zone(game, next_card, Zone.LIBRARY, Zone.EXILE)
            exiled_cards.append(next_card)
            total_mana_value += getattr(getattr(next_card, "mana_cost", None), "cmc", 0)

        for card in exiled_cards:
            card_types = getattr(card, "card_types", set())
            if not card_types or CardType.LAND in card_types:
                continue
            if not spell_has_legal_targets(game, card):
                continue
            if not controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'this spell')} without paying its mana cost?"
            ):
                continue
            cast_spell_free(game, controller, card, Zone.EXILE)

        if not getattr(self, "is_copy", False):
            self._register_paradigm_replacement(game, controller)
            if self._claim_paradigm_trigger(game, controller):
                self._register_paradigm_trigger(game, controller)

    def _claim_paradigm_trigger(self, game: "GameState", controller: Any) -> bool:
        """Return ``True`` only for the first resolved spell with this name this game."""
        resolved_names = getattr(game, "_paradigm_resolved_spell_names", None)
        if resolved_names is None:
            resolved_names = set()
            game._paradigm_resolved_spell_names = resolved_names

        key = (controller, self.name)
        if key in resolved_names:
            return False

        resolved_names.add(key)
        return True

    def _register_paradigm_replacement(self, game: "GameState", controller: Any) -> None:
        """Exile this spell instead of putting it into its owner's graveyard."""

        def _condition(_game: "GameState", event: MoveToGraveyardReplacementEvent) -> bool:
            return event.card is self and event.from_zone == Zone.STACK

        def _replacement(
            _game: "GameState",
            event: MoveToGraveyardReplacementEvent,
        ) -> MoveToGraveyardReplacementEvent:
            event.destination = "exile"
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=self,
                condition=_condition,
                replacement=_replacement,
                controller=controller,
            )
        )

    def _register_paradigm_trigger(self, game: "GameState", controller: Any) -> None:
        """Register the recurring first-main-phase Paradigm trigger."""
        if getattr(self, "_paradigm_registered", False):
            return

        delayed_source = _ParadigmTrigger(card=self, controller=controller)
        self._paradigm_registered = True

        def _condition(current_game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            if event.player is not controller:
                return False
            if event.phase != Phase.PRECOMBAT_MAIN:
                return False
            if not current_game.get_exile(controller).contains(self):
                current_game.trigger_manager.unregister(delayed_source)
                self._paradigm_registered = False
                return False
            return True

        def _effect(current_game: "GameState") -> None:
            if not current_game.get_exile(controller).contains(self):
                current_game.trigger_manager.unregister(delayed_source)
                self._paradigm_registered = False
                return
            if not controller.choose_yes_no(
                f"Cast a copy of {self.name} from exile without paying its mana cost?"
            ):
                return
            cast_spell_copy(current_game, controller, self)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=delayed_source,
                controller=controller,
            )
        )
