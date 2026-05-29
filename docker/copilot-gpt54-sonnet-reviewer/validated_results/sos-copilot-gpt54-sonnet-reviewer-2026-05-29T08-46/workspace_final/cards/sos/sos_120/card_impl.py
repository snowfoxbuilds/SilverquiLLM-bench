"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.types import CardType, ManaCost, Phase, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _mana_value(card: Any) -> int:
    """Return *card*'s mana value."""
    mana_cost = getattr(card, "mana_cost", None)
    return int(getattr(mana_cost, "cmc", 0))


def _is_spell_card(card: Any) -> bool:
    """Return whether *card* is a spell card that can be cast."""
    return CardType.LAND not in getattr(card, "card_types", set())


def _register_paradigm_window(
    game: "GameState",
    source_card: Any,
    controller: "Player | None",
) -> None:
    """Create the recurring Paradigm copy-cast window for *source_card*."""
    if controller is None:
        return

    source_owner = getattr(source_card, "owner", controller) or controller

    def _schedule_for_turn(min_turn_number: int) -> None:
        def _condition(current_game: "GameState") -> bool:
            return (
                current_game.turn_number >= min_turn_number
                and current_game.active_player is controller
                and current_game.phase == Phase.PRECOMBAT_MAIN
                and current_game.step is None
                and current_game.get_exile(source_owner).contains(source_card)
            )

        def _effect(current_game: "GameState") -> None:
            from engine.stack import StackObject, copy_spell

            try:
                if controller.choose_yes_no(
                    f"Cast a copy of {getattr(source_card, 'name', 'that spell')} from exile?"
                ):
                    copy_obj = copy_spell(
                        current_game,
                        StackObject(source=source_card, controller=controller),
                        controller,
                    )
                    copy_obj.source.is_paradigm_copy = True
                    current_game.stack.push(copy_obj)
            finally:
                _schedule_for_turn(current_game.turn_number + 1)

        game.schedule_delayed_action(_condition, _effect)

    _schedule_for_turn(game.turn_number + 1)


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards with total "
            "mana value 4 or greater. You may cast any number of spells from among them "
            "without paying their mana costs.\n"
            "Paradigm",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)
        exiled_cards: list[Any] = []
        total_mana_value = 0

        while len(library) > 0 and total_mana_value < 4:
            top_card = library.top(1)[0]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled_cards.append(top_card)
            total_mana_value += _mana_value(top_card)

        for exiled_card in exiled_cards:
            if not _is_spell_card(exiled_card):
                continue
            try:
                if controller.choose_yes_no(
                    f"Cast {getattr(exiled_card, 'name', 'that spell')} without paying its mana cost?"
                ):
                    cast_spell_free(game, controller, exiled_card, Zone.EXILE)
            except Exception:
                continue

        if getattr(self, "is_paradigm_copy", False):
            return

        def _replacement(
            current_game: "GameState",
            event: MoveToGraveyardReplacementEvent,
        ) -> MoveToGraveyardReplacementEvent:
            event.destination = "exile"
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=self,
                condition=lambda current_game, event, source=self: event.card is source,
                replacement=_replacement,
                controller=controller,
            )
        )
        _register_paradigm_window(game, self, controller)
