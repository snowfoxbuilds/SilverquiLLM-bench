"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.casting import cast_spell_free
from engine.events import MoveToGraveyardReplacementEvent
from engine.game_state import DelayedEffect
from engine.replacement_effects import ReplacementEffect
from engine.stack import StackObject
from engine.types import CardType, ManaCost, Phase, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


_SPELL_CARD_TYPES = {
    CardType.CREATURE,
    CardType.INSTANT,
    CardType.SORCERY,
    CardType.ENCHANTMENT,
    CardType.ARTIFACT,
    CardType.PLANESWALKER,
}


def _mana_value(card: Any) -> int:
    cost = getattr(card, "mana_cost", None)
    return int(getattr(cost, "cmc", 0) or 0)


def _is_spell_card(card: Any) -> bool:
    return bool(getattr(card, "card_types", set()) & _SPELL_CARD_TYPES)


def _is_on_stack(game: "GameState", card: Any) -> bool:
    return any(player.zones[Zone.STACK].contains(card) for player in game.players)


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards with "
            "total mana value 4 or greater. You may cast any number of spells "
            "from among them without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell "
            "with this name, you may cast a copy of it from exile without paying "
            "its mana cost at the beginning of each of your first main phases.)",
        )
        super().__init__(**kwargs)
        self._paradigm_tracking_started = getattr(self, "_paradigm_tracking_started", False)

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return

        if _is_on_stack(game, self):
            self._register_paradigm_self_exile(game, controller)
            if not self._paradigm_tracking_started:
                self._paradigm_tracking_started = True
                self._schedule_paradigm_copy_offer(game, controller)

        exiled_cards: list[Any] = []
        total_mana_value = 0
        library = game.get_library(controller)

        while total_mana_value < 4:
            library_cards = library.get_all()
            if not library_cards:
                break
            top_card = library_cards[-1]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled_cards.append(top_card)
            total_mana_value += _mana_value(top_card)

        for card in exiled_cards:
            if not _is_spell_card(card):
                continue
            if controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} without paying its mana cost?"
            ):
                cast_spell_free(game, controller, card, Zone.EXILE)

    def _register_paradigm_self_exile(self, game: "GameState", controller: "Player") -> None:
        marker = object()
        self._paradigm_exile_marker = marker

        def _condition(current_game: "GameState", event: Any) -> bool:
            return (
                isinstance(event, MoveToGraveyardReplacementEvent)
                and event.card is self
                and getattr(self, "_paradigm_exile_marker", None) is marker
            )

        def _replacement(current_game: "GameState", event: Any) -> Any:
            if getattr(self, "_paradigm_exile_marker", None) is marker:
                delattr(self, "_paradigm_exile_marker")
            current_game.replacement_manager.unregister(marker)
            event.destination = "exile"
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=marker,
                condition=_condition,
                replacement=_replacement,
                controller=controller,
            )
        )

    def _schedule_paradigm_copy_offer(self, game: "GameState", controller: "Player") -> None:
        source_card = self

        def _condition(current_game: "GameState") -> bool:
            return (
                current_game.active_player is controller
                and current_game.phase is Phase.PRECOMBAT_MAIN
                and current_game.step is None
            )

        def _effect(current_game: "GameState") -> None:
            exile = current_game.get_exile(controller)
            if not exile.contains(source_card):
                return
            if not controller.choose_yes_no(
                f"Cast a copy of {source_card.name} from exile without paying its mana cost?"
            ):
                return

            copied_card = copy.copy(source_card)
            copied_card.owner = controller
            copied_card.controller = controller

            stack_obj = StackObject(
                source=copied_card,
                controller=controller,
                targets=[],
            )

            def _copy_resolve(resolution_game: "GameState") -> None:
                copied_card.chosen_targets = stack_obj.targets
                copied_card.on_resolve(resolution_game)

            stack_obj.on_resolve = _copy_resolve
            current_game.stack.push(stack_obj)

        game.add_delayed_effect(
            DelayedEffect(
                condition=_condition,
                effect=_effect,
                once=False,
            )
        )
