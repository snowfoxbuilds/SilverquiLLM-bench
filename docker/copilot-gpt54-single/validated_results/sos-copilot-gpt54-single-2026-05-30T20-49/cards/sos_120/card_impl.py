"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.casting import cast_spell_free
from engine.events import MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.stack import StackObject
from engine.types import CardType, ManaCost, Phase, Zone

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
            "from among them without paying their mana costs.\nParadigm (Then "
            "exile this spell. After you first resolve a spell with this name, "
            "you may cast a copy of it from exile without paying its mana cost "
            "at the beginning of each of your first main phases.)",
        )
        super().__init__(**kwargs)
        self._paradigm_registered: bool = False
        self._is_paradigm_copy: bool = False

    def _get_cast_order(self, controller: Any, cards: list[Any]) -> list[Any]:
        """Return the player's chosen cast order for the exiled nonland spells."""
        if len(cards) <= 1:
            return list(cards)

        try:
            chosen_order = controller.choose_order(
                list(cards),
                "Choose the order to cast exiled spells",
            )
        except Exception:
            return list(cards)

        ordered_cards: list[Any] = []
        for card in chosen_order:
            if card not in cards or card in ordered_cards:
                continue
            ordered_cards.append(card)
        for card in cards:
            if card not in ordered_cards:
                ordered_cards.append(card)
        return ordered_cards

    def _resolve_exile_and_cast(self, game: "GameState") -> None:
        """Exile from the top of your library, then optionally free-cast spells."""
        from engine.zones import move_to_zone

        controller = self.controller or self.owner
        if controller is None:
            return

        library = game.get_library(controller)
        exiled_cards: list[Any] = []
        total_mana_value = 0

        while total_mana_value < 4 and len(library) > 0:
            top_card = library.get_all()[-1]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled_cards.append(top_card)
            total_mana_value += getattr(getattr(top_card, "mana_cost", None), "cmc", 0)

        castable_cards = [
            card for card in exiled_cards
            if CardType.LAND not in getattr(card, "card_types", set())
        ]
        for card in self._get_cast_order(controller, castable_cards):
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            if not controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} without paying its mana cost?"
            ):
                continue
            try:
                cast_spell_free(game, controller, card, Zone.EXILE)
            except Exception:
                continue

    def _register_exile_on_resolution(self, game: "GameState") -> None:
        """Exile the original spell card instead of letting it hit the graveyard."""
        controller = self.controller or self.owner
        source = self

        def _condition(game: Any, event: MoveToGraveyardReplacementEvent) -> bool:
            return event.card is source

        def _replacement(
            game: Any,
            event: MoveToGraveyardReplacementEvent,
        ) -> MoveToGraveyardReplacementEvent:
            event.destination = "exile"
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=source,
                condition=_condition,
                replacement=_replacement,
                controller=controller,
            )
        )

    def _register_paradigm_callback(self, game: "GameState") -> None:
        """Offer a free copy at the beginning of each of your first main phases."""
        controller = self.controller or self.owner
        source = self
        registry = getattr(game, "_paradigm_registered_names", None)
        if registry is None:
            registry = set()
            game._paradigm_registered_names = registry

        registry_key = (controller, self.name)
        if (
            controller is None
            or self._paradigm_registered
            or self._is_paradigm_copy
            or registry_key in registry
        ):
            return

        self._paradigm_registered = True
        registry.add(registry_key)

        def _offer_copy(current_game: "GameState") -> bool:
            if current_game.active_player is not controller:
                return True
            if current_game.phase != Phase.PRECOMBAT_MAIN or current_game.step is not None:
                return True
            if not current_game.get_exile(controller).contains(source):
                return False
            if not controller.choose_yes_no(
                f"Cast a copy of {source.name} from exile without paying its mana cost?"
            ):
                return True

            copy_card = ImprovisationCapstone(owner=controller, controller=controller)
            copy_card._is_paradigm_copy = True
            stack_obj = StackObject(
                source=copy_card,
                controller=controller,
                targets=[],
                target_requirements=[],
                is_spell=True,
            )

            def _resolve_copy(g: "GameState") -> None:
                copy_card.on_resolve(g)

            stack_obj.on_resolve = _resolve_copy
            current_game.stack.push(stack_obj)
            return True

        game.register_phase_transition_callback(_offer_copy)

    def on_resolve(self, game: "GameState") -> None:
        """Resolve the spell's exile/free-cast effect and Paradigm rider."""
        self._resolve_exile_and_cast(game)
        if self._is_paradigm_copy:
            return
        self._register_exile_on_resolution(game)
        self._register_paradigm_callback(game)
