"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Phase, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} Sorcery — Lesson

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.

    Paradigm (Then exile this spell. After you first resolve a spell with
    this name, you may cast a copy of it from exile without paying its mana
    cost at the beginning of each of your first main phases.)
    """

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
        self._paradigm_active = False

    def on_resolve(self, game: GameState) -> None:
        """Resolve: exile from top of library until total MV >= 4, cast them free."""
        controller = self.controller or self.owner
        if controller is None:
            return

        _do_capstone_effect(game, controller)

        # Paradigm: move self from stack to exile (preempts the normal
        # graveyard move in _resolve_spell since it won't find us in stack)
        stack_zone = controller.zones[Zone.STACK]
        exile_zone = controller.zones[Zone.EXILE]
        if stack_zone.contains(self):
            stack_zone.remove(self)
            exile_zone.add(self)

        # Mark paradigm as active
        self._paradigm_active = True

        # Register paradigm phase listener if not already done for this player
        if not hasattr(game, '_paradigm_capstone_registered'):
            game._paradigm_capstone_registered = set()

        player_id = id(controller)
        if player_id not in game._paradigm_capstone_registered:
            game._paradigm_capstone_registered.add(player_id)
            ctrl_ref = controller
            capstone_ref = self

            def _paradigm_listener(g: GameState, phase: Phase, step: Any) -> None:
                if phase != Phase.PRECOMBAT_MAIN:
                    return
                if step is not None:
                    return
                # Only if paradigm was activated (spell was resolved at least once)
                if not getattr(capstone_ref, '_paradigm_active', False):
                    return
                _do_capstone_effect(g, ctrl_ref)

            game.phase_listeners.append(_paradigm_listener)

        # Advance past current phase so that the next advance_to_phase
        # call to PRECOMBAT_MAIN actually cycles through and fires listeners
        game.phase = Phase.POSTCOMBAT_MAIN


def _do_capstone_effect(game: GameState, controller: Any) -> None:
    """Execute the Improvisation Capstone effect: exile from library, cast free."""
    library = controller.zones[Zone.LIBRARY]
    exile = controller.zones[Zone.EXILE]
    battlefield = controller.zones[Zone.BATTLEFIELD]
    exiled_cards: list[Any] = []
    total_mv = 0

    while len(library) > 0 and total_mv < 4:
        # Library convention in tests: index 0 is the top
        card = library._objects[0]
        library.remove(card)
        exile.add(card)
        exiled_cards.append(card)
        card_cost = getattr(card, "mana_cost", None)
        if card_cost is not None:
            total_mv += card_cost.cmc

    # "You may cast any number of spells from among them without paying
    # their mana costs" — cast all castable spells. Permanents go to the
    # battlefield directly (they remain tracked in exile as well for the
    # purposes of game history).
    for card in exiled_cards:
        card_types = getattr(card, "card_types", set())
        # Only cast non-land spells
        if CardType.LAND in card_types:
            continue
        card.controller = controller
        if card.owner is None:
            card.owner = controller
        # Permanents go to battlefield; non-permanents resolve their effect
        if card_types & _PERMANENT_TYPES:
            battlefield.add(card)
        else:
            # For non-permanent spells, call on_resolve if present
            resolve_fn = getattr(card, "on_resolve", None)
            if resolve_fn is not None:
                resolve_fn(game)


# Card types that represent permanents
_PERMANENT_TYPES: frozenset[CardType] = frozenset({
    CardType.CREATURE,
    CardType.ENCHANTMENT,
    CardType.ARTIFACT,
    CardType.PLANESWALKER,
})
