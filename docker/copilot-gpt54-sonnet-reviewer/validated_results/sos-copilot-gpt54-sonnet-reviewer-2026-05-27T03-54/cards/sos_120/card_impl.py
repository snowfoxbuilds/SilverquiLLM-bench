"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.casting import cast_spell_copy, cast_spell_free
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, Phase, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _paradigm_registry(game: "GameState") -> set[tuple[int, str]]:
    """Return the per-game registry of recurring Paradigm spell names."""
    registry = getattr(game, "_paradigm_registry", None)
    if registry is None:
        registry = set()
        setattr(game, "_paradigm_registry", registry)
    return registry


def _is_spell(card: Any) -> bool:
    """Return True if *card* is a spell card that can be cast."""
    return CardType.LAND not in getattr(card, "card_types", set())


def _mana_value(card: Any) -> int:
    """Return *card*'s mana value, defaulting to 0."""
    return int(getattr(getattr(card, "mana_cost", None), "cmc", 0))


def _is_in_exile(game: "GameState", card: Any) -> bool:
    """Return True if *card* is currently in any exile zone."""
    return any(game.get_exile(player).contains(card) for player in game.players)


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault("non_evergreen_keywords", {"Paradigm"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards with total mana value 4 or greater. "
            "You may cast any number of spells from among them without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell with this name, you may cast a copy "
            "of it from exile without paying its mana cost at the beginning of each of your first main phases.)",
        )
        super().__init__(**kwargs)

    def on_cast(self, game: "GameState") -> None:
        """Paradigm exiles the spell after it resolves."""
        del game
        self._exile_on_resolution = True

    def on_resolve(self, game: "GameState") -> None:
        """Exile cards until the threshold is reached, free-cast spells, and set up Paradigm."""
        controller = self.controller
        if controller is None:
            return

        exiled_cards = self._exile_from_library(game, controller)
        for card in exiled_cards:
            if not _is_spell(card):
                continue
            if not controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'that spell')} without paying its mana cost?"
            ):
                continue
            cast_spell_free(game, controller, card, Zone.EXILE)

        if getattr(self, "is_spell_copy", False):
            return
        self._register_paradigm_trigger(game)

    def _exile_from_library(self, game: "GameState", controller: Any) -> list[Any]:
        """Exile cards from the top of the controller's library to total mana value four or more."""
        library = game.get_library(controller)
        exiled: list[Any] = []
        total_mana_value = 0

        while len(library) > 0 and total_mana_value < 4:
            card = library.get_all()[-1]
            move_to_zone(game, card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(card)
            total_mana_value += _mana_value(card)

        return exiled

    def _register_paradigm_trigger(self, game: "GameState") -> None:
        """Register the recurring first-main-phase Paradigm trigger once per name."""
        controller = self.controller
        if controller is None:
            return

        registry_key = (id(controller), self.name)
        registry = _paradigm_registry(game)
        if registry_key in registry:
            return
        registry.add(registry_key)

        source = self

        def _condition(trigger_game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            return (
                event.player is controller
                and trigger_game.active_player is controller
                and trigger_game.phase == Phase.PRECOMBAT_MAIN
            )

        def _effect(trigger_game: "GameState") -> None:
            if not _is_in_exile(trigger_game, source):
                return
            if not controller.choose_yes_no(
                f"Cast a copy of {source.name} from exile without paying its mana cost?"
            ):
                return
            copy_spell = type(source)(owner=source.owner, controller=controller)
            copy_spell.is_spell_copy = True
            cast_spell_copy(trigger_game, controller, copy_spell)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
