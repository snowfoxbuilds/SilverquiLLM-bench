"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy

from engine.casting import CastingError, cast_spell_copy_free, cast_spell_free
from engine.card import CardImpl, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.player import ScriptExhaustedError
from engine.triggers import TriggerRegistration
from engine.types import CardMechanic, CardType, ManaCost, Phase, Zone

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault("mechanics", {CardMechanic.PARADIGM})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards with "
            "total mana value 4 or greater. You may cast any number of spells "
            "from among them without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell "
            "with this name, you may cast a copy of it from exile without "
            "paying its mana cost at the beginning of each of your first "
            "main phases.)",
        )
        super().__init__(**kwargs)

    def _get_controller(self) -> "Player | None":
        return getattr(self, "controller", None) or getattr(self, "owner", None)

    def _is_in_exile(self, player: "Player | None") -> bool:
        return player is not None and player.zones[Zone.EXILE].contains(self)

    def _exile_revealed_cards(self, game: "GameState") -> list[CardImpl]:
        from engine.zones import move_to_zone

        controller = self._get_controller()
        if controller is None:
            return []

        library = controller.zones[Zone.LIBRARY]
        exiled: list[CardImpl] = []
        total_mana_value = 0

        while len(library) > 0 and total_mana_value < 4:
            top_card = library.get_all()[-1]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top_card)
            total_mana_value += getattr(getattr(top_card, "mana_cost", None), "cmc", 0)

        return exiled

    def _can_free_cast_revealed_card(self, controller: "Player", card: CardImpl) -> bool:
        card_types = getattr(card, "card_types", set())
        return (
            bool(card_types)
            and CardType.LAND not in card_types
            and controller.zones[Zone.EXILE].contains(card)
        )

    def _normalize_revealed_choice(
        self,
        choice: object,
        remaining: list[CardImpl],
    ) -> CardImpl | None:
        if choice in ("done", None):
            return None

        for card in remaining:
            if choice is card or choice == getattr(card, "name", None):
                return card

        return None

    def _cast_revealed_spells(self, game: "GameState", exiled_cards: list[CardImpl]) -> None:
        controller = self._get_controller()
        if controller is None:
            return

        remaining = [
            card for card in exiled_cards
            if self._can_free_cast_revealed_card(controller, card)
        ]

        if getattr(controller, "remaining_choices", 0) > 0:
            while remaining:
                try:
                    choice = controller.choose(
                        list(remaining) + ["done"],
                        "Choose a revealed spell to cast, or done.",
                    )
                except ScriptExhaustedError:
                    break

                chosen_card = self._normalize_revealed_choice(choice, remaining)
                if choice in ("done", None):
                    return
                if chosen_card is None:
                    break

                remaining.remove(chosen_card)
                try:
                    cast_spell_free(game, controller, chosen_card, Zone.EXILE)
                except CastingError:
                    pass

                remaining = [
                    card for card in remaining
                    if self._can_free_cast_revealed_card(controller, card)
                ]

        for card in remaining:
            if not controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'that card')} without paying its mana cost?"
            ):
                continue
            try:
                cast_spell_free(game, controller, card, Zone.EXILE)
            except CastingError:
                continue

    def _resolve_effect(self, game: "GameState") -> None:
        exiled_cards = self._exile_revealed_cards(game)
        self._cast_revealed_spells(game, exiled_cards)

    def _create_paradigm_copy(self, controller: "Player") -> CardImpl:
        copied_spell = copy.copy(self)
        copied_spell.owner = self.owner
        copied_spell.controller = controller
        copied_spell._is_paradigm_copy = True  # type: ignore[attr-defined]
        copied_spell._paradigm_registered = False  # type: ignore[attr-defined]
        if hasattr(copied_spell, "_graveyard_destination_override"):
            delattr(copied_spell, "_graveyard_destination_override")
        return copied_spell

    def _register_paradigm_trigger(self, game: "GameState") -> None:
        if getattr(self, "_paradigm_registered", False):
            return

        controller = self._get_controller()
        if controller is None:
            return

        source = self

        def _condition(_game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            return (
                event.player is controller
                and event.phase == Phase.PRECOMBAT_MAIN
                and source._is_in_exile(controller)
            )

        def _effect(_game: "GameState") -> None:
            if not source._is_in_exile(controller):
                return
            if not controller.choose_yes_no(
                f"Cast a copy of {source.name} from exile without paying its mana cost?"
            ):
                return
            try:
                cast_spell_copy_free(_game, controller, source._create_paradigm_copy(controller))
            except CastingError:
                return

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
        self._paradigm_registered = True  # type: ignore[attr-defined]

    def on_resolve(self, game: "GameState") -> None:
        if not getattr(self, "_is_paradigm_copy", False):
            self._graveyard_destination_override = Zone.EXILE  # type: ignore[attr-defined]
            self._register_paradigm_trigger(game)
        self._resolve_effect(game)
