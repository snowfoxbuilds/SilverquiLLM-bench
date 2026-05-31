"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.casting import CastingError, cast_spell_free
from engine.stack import StackObject
from engine.types import CardType, ManaCost, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _mana_value(card: Any) -> int:
    """Return the card's mana value, defaulting to 0 for missing costs."""
    mana_cost = getattr(card, "mana_cost", None)
    if mana_cost is None:
        return 0
    return mana_cost.cmc


def _is_in_zone(game: "GameState", card: Any, zone: Zone) -> bool:
    """Return whether *card* is currently in any player's *zone*."""
    return any(player.zones[zone].contains(card) for player in game.players)


def _is_spell_card(card: Any) -> bool:
    """Return whether *card* is a castable spell rather than a land."""
    return CardType.LAND not in getattr(card, "card_types", set())


def _build_paradigm_copy_stack_object(
    template: "ImprovisationCapstone",
    controller: "Player",
) -> StackObject:
    """Create a cast spell-copy stack object for Paradigm."""
    copied_card = copy.copy(template)
    copied_card.owner = getattr(template, "owner", controller)
    copied_card.controller = controller
    copied_card._is_paradigm_copy = True

    stack_obj = StackObject(
        source=copied_card,
        controller=controller,
        targets=[],
        is_spell=True,
        mana_spent=0,
    )

    def _on_resolve(game: "GameState") -> None:
        copied_card.chosen_targets = []
        copied_card.on_resolve(game)

    stack_obj.on_resolve = _on_resolve
    return stack_obj


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
        self._paradigm_registered: bool = False
        self._is_paradigm_copy: bool = False

    def _resolve_exile_and_cast(self, game: "GameState") -> None:
        """Perform the main exile-and-free-cast effect."""
        controller = self.controller
        if controller is None:
            return

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
            total_mana_value += _mana_value(top_card)

        for card in exiled_cards:
            if not _is_spell_card(card):
                continue
            try:
                if controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} without paying its mana cost?"
                ):
                    cast_spell_free(game, controller, card, Zone.EXILE)
            except CastingError:
                continue

    def _schedule_paradigm(self, game: "GameState") -> None:
        """Schedule recurring Paradigm copy offers for future first main phases."""
        if self._paradigm_registered or self._is_paradigm_copy:
            return

        controller = self.controller
        if controller is None:
            return

        self._paradigm_registered = True
        source = self

        def _offer_copy(current_game: "GameState") -> None:
            if not _is_in_zone(current_game, source, Zone.EXILE):
                return

            source_controller = getattr(source, "controller", None) or controller
            if source_controller.choose_yes_no(
                f"Cast a copy of {source.name} from exile without paying its mana cost?"
            ):
                current_game.stack.push(
                    _build_paradigm_copy_stack_object(source, source_controller)
                )

            current_game.schedule_for_first_main_phase(
                source_controller,
                _offer_copy,
                require_future_turn=True,
            )

        game.schedule_for_first_main_phase(
            controller,
            _offer_copy,
            require_future_turn=True,
        )

    def on_resolve(self, game: "GameState") -> None:
        """Resolve the exile-until-four effect and apply Paradigm exile."""
        self._resolve_exile_and_cast(game)

        if self._is_paradigm_copy:
            return

        self._schedule_paradigm(game)
        if _is_in_zone(game, self, Zone.STACK):
            move_to_zone(game, self, Zone.STACK, Zone.EXILE)
