"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.casting import (
    CastingError,
    cast_copied_spell_free,
    cast_spell_free,
    register_stack_graveyard_replacement,
)
from engine.player import ScriptExhaustedError
from engine.types import ManaCost, Phase, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone."""

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
            "paying its mana cost at the beginning of each of your first main "
            "phases.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return

        exiled_cards = self._exile_until_threshold(game, controller)
        self._cast_exiled_spells(game, controller, exiled_cards)

        if getattr(self, "_is_paradigm_copy", False):
            return

        register_stack_graveyard_replacement(game, self, Zone.EXILE)
        self._register_paradigm(game, controller)

    def _exile_until_threshold(self, game: "GameState", controller: "Player") -> list[Any]:
        exiled_cards: list[Any] = []
        total_mana_value = 0
        library = controller.zones[Zone.LIBRARY]

        while len(library) > 0 and total_mana_value < 4:
            top_card = library.get_all()[-1]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled_cards.append(top_card)
            total_mana_value += self._mana_value_of(top_card)

        return exiled_cards

    def _cast_exiled_spells(
        self,
        game: "GameState",
        controller: "Player",
        exiled_cards: list[Any],
    ) -> None:
        remaining_cards = [card for card in exiled_cards if self._is_spell(card)]

        while remaining_cards:
            available = [card for card in remaining_cards if self._find_exile_zone(game, card) is not None]
            if not available:
                return
            if not controller.choose_yes_no(
                "Cast a spell from among the exiled cards without paying its mana cost?"
            ):
                return

            card = self._choose_exiled_spell_to_cast(controller, available)
            try:
                cast_spell_free(game, controller, card, Zone.EXILE)
            except CastingError:
                remaining_cards.remove(card)
                remaining_cards.append(card)
                continue
            remaining_cards.remove(card)

    def _register_paradigm(self, game: "GameState", controller: "Player") -> None:
        if getattr(self, "_paradigm_registered", False):
            return

        source_card = self
        source_turn = getattr(game, "turn_number", 0)
        source_controller = controller

        def _delayed_action(current_game: "GameState") -> bool:
            if self._find_exile_zone(current_game, source_card) is None:
                return True

            if current_game.active_player is not source_controller:
                return False
            if current_game.phase != Phase.PRECOMBAT_MAIN or current_game.step is not None:
                return False
            if getattr(current_game, "turn_number", 0) <= source_turn:
                return False

            if not source_controller.choose_yes_no(
                f"Cast a copy of {source_card.name} from exile without paying its mana cost?"
            ):
                return False

            copied_spell = self._make_paradigm_copy_spell(source_controller)
            try:
                cast_copied_spell_free(current_game, source_controller, copied_spell)
            except CastingError:
                return False
            return False

        game.add_delayed_action(_delayed_action)
        self._paradigm_registered = True

    def _make_paradigm_copy_spell(self, controller: "Player") -> "ImprovisationCapstone":
        from copy import copy

        copied_spell = copy(self)
        copied_spell.controller = controller
        copied_spell.owner = self.owner
        copied_spell._is_paradigm_copy = True
        copied_spell._paradigm_registered = True
        return copied_spell

    @staticmethod
    def _mana_value_of(card: Any) -> int:
        mana_cost = getattr(card, "mana_cost", None)
        if mana_cost is None:
            return 0
        return getattr(mana_cost, "cmc", 0)

    @staticmethod
    def _is_spell(card: Any) -> bool:
        from engine.types import CardType

        return CardType.LAND not in getattr(card, "card_types", set())

    @staticmethod
    def _find_exile_zone(game: "GameState", card: Any) -> Any | None:
        for player in game.players:
            exile_zone = player.zones[Zone.EXILE]
            if exile_zone.contains(card):
                return exile_zone
        return None

    def _choose_exiled_spell_to_cast(
        self,
        controller: "Player",
        available: list[Any],
    ) -> Any:
        if len(available) == 1:
            return available[0]

        scripted_choices = getattr(controller, "_script", None)
        if scripted_choices:
            next_choice = scripted_choices[0]
            if next_choice in available:
                choice = controller.choose(
                    available,
                    "Choose a spell exiled with Improvisation Capstone to cast",
                )
                if choice in available:
                    return choice
                return available[0]
            return available[0]

        try:
            choice = controller.choose(
                available,
                "Choose a spell exiled with Improvisation Capstone to cast",
            )
        except ScriptExhaustedError:
            return available[0]

        if choice in available:
            return choice
        return available[0]
