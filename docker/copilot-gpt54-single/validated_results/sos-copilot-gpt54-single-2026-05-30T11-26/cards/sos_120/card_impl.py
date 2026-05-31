"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, Color, ManaCost, Phase, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _mana_value(card: Any) -> int:
    mana_cost = getattr(card, "mana_cost", None)
    if mana_cost is None:
        return 0
    return mana_cost.cmc


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards with total mana value 4 "
            "or greater. You may cast any number of spells from among them without paying their mana "
            "costs.\nParadigm (Then exile this spell. After you first resolve a spell with this name, "
            "you may cast a copy of it from exile without paying its mana cost at the beginning of "
            "each of your first main phases.)",
        )
        super().__init__(**kwargs)
        self.set_base_colors({Color.RED})

    def get_post_resolve_zone(self, game: "GameState") -> Zone | None:
        return Zone.EXILE

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller or self.owner
        if controller is None:
            return

        exiled_cards: list[Any] = []
        total_mana_value = 0
        library = game.get_library(controller)

        while len(library) > 0 and total_mana_value < 4:
            card = library.top(1)[0]
            move_to_zone(game, card, Zone.LIBRARY, Zone.EXILE)
            exiled_cards.append(card)
            total_mana_value += _mana_value(card)

        from engine.casting import cast_spell_free

        for card in exiled_cards:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            try:
                should_cast = controller.choose_yes_no(
                    f"Cast {card.name} from among the exiled cards without paying its mana cost?"
                )
            except Exception:
                should_cast = False
            if not should_cast:
                continue
            try:
                cast_spell_free(game, controller, card, Zone.EXILE)
            except Exception:
                continue

        self._register_paradigm_trigger(game, controller)

    def _paradigm_registry_key(
        self,
        game: "GameState",
        controller: "Player",
    ) -> tuple[int, str]:
        return (game.get_player_index(controller), self.name)

    def _register_paradigm_trigger(self, game: "GameState", controller: "Player") -> None:
        registered_names = getattr(game, "_paradigm_registered_spell_names", None)
        if registered_names is None:
            registered_names = set()
            setattr(game, "_paradigm_registered_spell_names", registered_names)

        registry_key = self._paradigm_registry_key(game, controller)
        if registry_key in registered_names:
            return
        registered_names.add(registry_key)

        source_card = self

        def _condition(game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            return (
                event.player is controller
                and event.phase == Phase.PRECOMBAT_MAIN
                and game.get_exile(source_card.owner or controller).contains(source_card)
            )

        def _stack_factory(
            game: "GameState",
            event: BeginningOfMainPhaseTriggeredEvent,
            trigger: TriggerRegistration,
        ) -> StackObject | None:
            if not _condition(game, event):
                return None
            copied_card = source_card._create_paradigm_copy(controller)
            game.get_exile(controller).add(copied_card)

            def _resolve_trigger(resolving_game: "GameState") -> None:
                exile_zone = resolving_game.get_exile(controller)
                if not exile_zone.contains(copied_card):
                    return

                try:
                    should_cast = controller.choose_yes_no(
                        "Cast a copy of Improvisation Capstone from exile?"
                    )
                except Exception:
                    should_cast = False

                if not should_cast:
                    exile_zone.remove(copied_card)
                    return

                from engine.casting import cast_spell_free

                try:
                    cast_spell_free(resolving_game, controller, copied_card, Zone.EXILE)
                except Exception:
                    if exile_zone.contains(copied_card):
                        exile_zone.remove(copied_card)

            return StackObject(
                source=copied_card,
                controller=controller,
                on_resolve=_resolve_trigger,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=lambda _game: None,
                stack_factory=_stack_factory,
                source=self,
                controller=controller,
            )
        )

    def _create_paradigm_copy(self, controller: "Player") -> "ImprovisationCapstone":
        copied_card = copy.copy(self)
        copied_card.owner = controller
        copied_card.controller = controller
        copied_card.cease_to_exist_after_resolve = True
        return copied_card

    pass
