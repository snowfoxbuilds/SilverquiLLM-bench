"""Reference test for FDN 244 — Progenitus.

Illustrative test covering **replacement effects** via
``game.replacement_manager.register()``. Progenitus has a continuous
replacement that intercepts any ``MoveToGraveyardReplacementEvent``
targeting itself and redirects the card to its owner's library instead
of the graveyard. The replacement callback sets ``event.prevented`` to
signal that the engine should skip its own zone move, and returns the
modified event.
"""

from __future__ import annotations

from benchmarks.sos.workspace.cards.fdn.fdn_244.card_impl import Progenitus
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import (
    CreatureDiesReplacementEvent,
    MoveToGraveyardReplacementEvent,
)
from benchmarks.sos.workspace.engine.replacement_effects import ReplacementEffect
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestProgenitusProperties:
    """Static card data should match the FDN 244 spec."""

    def test_name(self) -> None:
        assert Progenitus(owner=None).name == "Progenitus"

    def test_mana_cost(self) -> None:
        cost = ManaCost.parse("{W}{W}{U}{U}{B}{B}{R}{R}{G}{G}")
        assert Progenitus(owner=None).mana_cost == cost

    def test_legendary_hydra_avatar(self) -> None:
        card = Progenitus(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Hydra", "Avatar"} <= card.subtypes


class TestProgenitusReplacementRegistration:
    """register_replacement_effects must wire a ReplacementEffect for
    MoveToGraveyardReplacementEvent through the replacement_manager."""

    def test_registers_one_replacement_effect(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = Progenitus(owner=p1, controller=p1)
        before = len(game.replacement_manager._effects)
        card.register_replacement_effects(game)
        after = len(game.replacement_manager._effects)
        assert after - before == 1

    def test_registered_replacement_uses_typed_event_class(self) -> None:
        """The registered ReplacementEffect must use the typed
        MoveToGraveyardReplacementEvent class, not a string event name."""
        game = create_game()
        p1 = game.players[0]
        card = Progenitus(owner=p1, controller=p1)
        card.register_replacement_effects(game)
        registered = next(
            (e for e in game.replacement_manager._effects if e.source is card),
            None,
        )
        assert registered is not None
        assert isinstance(registered, ReplacementEffect)
        assert registered.event_type is MoveToGraveyardReplacementEvent


class TestProgenitusGraveyardReplacement:
    """The replacement callback shuffles the card into its owner's
    library and prevents the move to graveyard."""

    def test_replacement_redirects_to_library_and_prevents(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = Progenitus(owner=p1, controller=p1)
        card.register_replacement_effects(game)
        # Use the creature-dies subclass so the event's ``card`` property
        # resolves to this Progenitus instance (the base class's ``card``
        # property returns None).
        event = CreatureDiesReplacementEvent(
            creature=card,
            destination="graveyard",
            controller=p1,
            owner=p1,
        )
        result = game.replacement_manager.apply(game, event)
        # Replacement callback should return the event with prevented=True
        # and shuffle the card into the library.
        assert result.prevented is True
        library = p1.zones[Zone.LIBRARY]
        assert library.contains(card)


