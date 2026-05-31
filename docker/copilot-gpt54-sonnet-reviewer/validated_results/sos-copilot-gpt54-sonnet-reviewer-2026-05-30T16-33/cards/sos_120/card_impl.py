"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.casting import cast_spell_free
from engine.events import MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.stack import StackObject
from engine.types import ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


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
        self.mechanic_keywords: set[str] = {"Paradigm"}
        self._is_paradigm_copy: bool = getattr(self, "_is_paradigm_copy", False)

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller or self.owner
        if controller is None:
            return

        exiled_cards = self._exile_until_threshold(game, controller)
        self._cast_exiled_spells(game, controller, exiled_cards)

        if self._is_paradigm_copy:
            return

        self._register_self_exile_replacement(game, controller)
        self._register_paradigm_recursion(game, controller)

    def _exile_until_threshold(self, game: "GameState", controller: Any) -> list[Any]:
        from engine.zones import move_to_zone

        library = game.get_library(controller)
        exiled_cards: list[Any] = []
        total_mana_value = 0

        while total_mana_value < 4:
            library_cards = library.get_all()
            if not library_cards:
                break

            top_card = library_cards[-1]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled_cards.append(top_card)
            mana_cost = getattr(top_card, "mana_cost", None)
            total_mana_value += mana_cost.cmc if mana_cost is not None else 0

        return exiled_cards

    def _cast_exiled_spells(
        self,
        game: "GameState",
        controller: Any,
        exiled_cards: list[Any],
    ) -> None:
        for card in exiled_cards:
            if not getattr(card, "can_cast", None):
                continue
            try:
                can_cast = bool(card.can_cast(game))
            except Exception:
                continue
            if not can_cast:
                continue
            if not controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'that card')} without paying its mana cost?"
            ):
                continue
            cast_spell_free(game, controller, card, Zone.EXILE)

    def _register_self_exile_replacement(self, game: "GameState", controller: Any) -> None:
        replacement_source = object()

        def _condition(game: "GameState", event: MoveToGraveyardReplacementEvent) -> bool:
            return event.card is self

        def _replacement(
            game: "GameState",
            event: MoveToGraveyardReplacementEvent,
        ) -> MoveToGraveyardReplacementEvent:
            event.destination = "exile"
            game.replacement_manager.unregister(replacement_source)
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=replacement_source,
                condition=_condition,
                replacement=_replacement,
                controller=controller,
            )
        )

    def _register_paradigm_recursion(self, game: "GameState", controller: Any) -> None:
        if getattr(self, "_paradigm_registered", False):
            return
        self._paradigm_registered = True

        def _offer_copy(g: "GameState") -> bool:
            exile = g.get_exile(controller)
            if not exile.contains(self):
                return False
            if not controller.choose_yes_no(
                f"Cast a copy of {self.name} from exile without paying its mana cost?"
            ):
                return True

            copied_card = copy.copy(self)
            copied_card.controller = controller
            copied_card.owner = self.owner or controller
            copied_card._is_paradigm_copy = True

            copy_obj = StackObject(source=copied_card, controller=controller, targets=[])

            def _copy_resolve(game: "GameState") -> None:
                copied_card.chosen_targets = []
                copied_card.on_resolve(game)

            copy_obj.on_resolve = _copy_resolve
            g.stack.push(copy_obj)
            return True

        game.schedule_for_each_first_main_phase(controller, _offer_copy)
