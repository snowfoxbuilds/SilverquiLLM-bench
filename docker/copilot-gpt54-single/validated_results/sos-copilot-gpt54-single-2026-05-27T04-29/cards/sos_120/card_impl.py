"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, Phase, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_PARADIGM_REGISTRY_ATTR = "_paradigm_triggered_spell_names"


def _mana_value(card: Any) -> int:
    mana_cost = getattr(card, "mana_cost", None)
    if mana_cost is None:
        return 0
    return getattr(mana_cost, "cmc", 0)


def _paradigm_registry(game: "GameState") -> set[tuple[int, str]]:
    registry = getattr(game, _PARADIGM_REGISTRY_ATTR, None)
    if registry is None:
        registry = set()
        setattr(game, _PARADIGM_REGISTRY_ATTR, registry)
    return registry


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards with total "
            "mana value 4 or greater. You may cast any number of spells from among "
            "them without paying their mana costs.\nParadigm (Then exile this spell. "
            "After you first resolve a spell with this name, you may cast a copy of "
            "it from exile without paying its mana cost at the beginning of each of "
            "your first main phases.)",
        )
        super().__init__(**kwargs)

    def on_cast(self, game: "GameState") -> None:
        del game
        self.exile_instead_of_graveyard_from_stack = True

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller or self.owner
        if controller is None:
            return

        self._register_paradigm_trigger(game, controller)

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

        if not exiled_cards:
            return

        from engine.casting import CastingError, cast_spell_free

        remaining_spells = [
            card for card in exiled_cards if CardType.LAND not in getattr(card, "card_types", set())
        ]
        while remaining_spells:
            if not controller.choose_yes_no(
                "Cast a spell from among the exiled cards without paying its mana cost?"
            ):
                break

            choice = remaining_spells[0]
            if len(remaining_spells) > 1:
                chosen = controller.choose(
                    list(remaining_spells),
                    "Choose a spell to cast from among the exiled cards",
                )
                if chosen in remaining_spells:
                    choice = chosen

            remaining_spells.remove(choice)
            try:
                cast_spell_free(game, controller, choice, Zone.EXILE)
            except CastingError:
                continue

    def _register_paradigm_trigger(self, game: "GameState", controller: Any) -> None:
        repeat_targets = getattr(game, "_advance_to_phase_repeat_targets", None)
        if repeat_targets is None:
            repeat_targets = set()
            game._advance_to_phase_repeat_targets = repeat_targets
        repeat_targets.add((Phase.PRECOMBAT_MAIN, None))

        registry = _paradigm_registry(game)
        key = (id(controller), self.name)
        if key in registry:
            return
        registry.add(key)

        source = self

        def _condition(game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            del game
            return event.player is controller and event.phase == Phase.PRECOMBAT_MAIN

        def _effect(game: "GameState") -> None:
            if source.owner is None:
                return
            exile = game.get_exile(source.owner)
            if not exile.contains(source):
                return
            if not controller.choose_yes_no(
                f"Cast a copy of {source.name} from exile without paying its mana cost?"
            ):
                return
            from engine.casting import CastingError, cast_spell_copy_free

            try:
                cast_spell_copy_free(game, controller, source, from_zone=Zone.EXILE)
            except CastingError:
                return

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
