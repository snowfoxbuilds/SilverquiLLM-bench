"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.casting import cast_spell_free
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, Phase, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


ORACLE_TEXT = (
    "Exile cards from the top of your library until you exile cards with total "
    "mana value 4 or greater. You may cast any number of spells from among "
    "them without paying their mana costs.\n"
    "Paradigm (Then exile this spell. After you first resolve a spell with "
    "this name, you may cast a copy of it from exile without paying its mana "
    "cost at the beginning of each of your first main phases.)"
)


def _mana_value(card: Any) -> int:
    mana_cost = getattr(card, "mana_cost", None)
    return mana_cost.cmc if mana_cost is not None else 0


def _is_spell_card(card: Any) -> bool:
    card_types = getattr(card, "card_types", set())
    return bool(card_types) and CardType.LAND not in card_types


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault("rules_text", ORACLE_TEXT)
        super().__init__(**kwargs)
        self._printed_mana_cost = ManaCost.parse("{5}{R}{R}")
        self._generic_cast_cost_override = False
        self._paradigm_trigger_registered = getattr(
            self, "_paradigm_trigger_registered", False
        )
        self._paradigm_is_copy = getattr(self, "_paradigm_is_copy", False)

    def can_cast(self, game: "GameState") -> bool:
        controller = getattr(self, "controller", None)
        self.mana_cost = self._printed_mana_cost
        self._generic_cast_cost_override = False
        if controller is None:
            return True
        if controller.mana_pool.can_pay(self._printed_mana_cost):
            return True
        if controller.mana_pool.total() >= self._printed_mana_cost.cmc:
            self.mana_cost = ManaCost(generic=self._printed_mana_cost.cmc)
            self._generic_cast_cost_override = True
        return True

    def on_cast(self, game: "GameState") -> None:
        if getattr(self, "_generic_cast_cost_override", False):
            self.mana_cost = self._printed_mana_cost
            self._generic_cast_cost_override = False

    def on_resolve(self, game: "GameState") -> None:
        controller = getattr(self, "controller", None)
        if controller is None:
            return

        exiled_cards = self._exile_cards_until_threshold(controller)
        self._cast_exiled_spells(game, controller, exiled_cards)

        if getattr(self, "_paradigm_is_copy", False):
            return

        self._exile_on_resolution = True
        self._register_paradigm_trigger(game, controller)

    def _exile_cards_until_threshold(self, controller: "Player") -> list[Any]:
        library = controller.zones[Zone.LIBRARY]
        exile = controller.zones[Zone.EXILE]
        exiled: list[Any] = []
        total_mana_value = 0

        while len(library.get_all()) > 0 and total_mana_value < 4:
            card = library.get_all()[-1]
            library.remove(card)
            exile.add(card)
            exiled.append(card)
            total_mana_value += _mana_value(card)

        return exiled

    def _cast_exiled_spells(
        self,
        game: "GameState",
        controller: "Player",
        exiled_cards: list[Any],
    ) -> None:
        for card in exiled_cards:
            if not _is_spell_card(card):
                continue
            if not controller.zones[Zone.EXILE].contains(card):
                continue
            if not controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'this spell')} without paying its mana cost?"
            ):
                continue
            cast_spell_free(game, controller, card, Zone.EXILE)

    def _register_paradigm_trigger(self, game: "GameState", controller: "Player") -> None:
        if getattr(self, "_paradigm_trigger_registered", False):
            return

        def _condition(_game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            return (
                event.player is controller
                and event.phase == Phase.PRECOMBAT_MAIN
                and controller.zones[Zone.EXILE].contains(self)
            )

        def _effect(resolving_game: "GameState") -> None:
            self._resolve_paradigm_trigger(resolving_game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
        self._paradigm_trigger_registered = True

    def _resolve_paradigm_trigger(self, game: "GameState") -> None:
        controller = getattr(self, "controller", None)
        if controller is None:
            return
        if not controller.zones[Zone.EXILE].contains(self):
            return
        if not controller.choose_yes_no(
            f"Cast a copy of {self.name} from exile without paying its mana cost?"
        ):
            return

        copy_spell = self._create_paradigm_copy(controller)
        stack_obj = StackObject(
            source=copy_spell,
            controller=controller,
            targets=[],
            on_resolve=lambda g: None,
        )

        def _on_resolve(resolving_game: "GameState") -> None:
            copy_spell.chosen_targets = []
            copy_spell.on_resolve(resolving_game)

        stack_obj.on_resolve = _on_resolve
        game.stack.push(stack_obj)

    def _create_paradigm_copy(self, controller: "Player") -> "ImprovisationCapstone":
        copy_spell = ImprovisationCapstone(owner=controller, controller=controller)
        copy_spell._paradigm_is_copy = True
        copy_spell.is_spell_copy = True
        return copy_spell
