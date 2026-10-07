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

from cards.fdn.fdn_244.card_impl import Progenitus
from engine.card import Creature, printed_class
from engine.events import (
    MoveToGraveyardReplacementEvent,
)
from engine.game import destroy, sacrifice
from engine.replacement_effects import ReplacementEffect
from engine.types import ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class TestProgenitusProperties:
    """Static card data should match the FDN 244 spec."""

    def test_name(self) -> None:
        assert printed_class(Progenitus(owner=None)) is Progenitus

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

    def test_dying_shuffles_it_into_its_owners_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = Progenitus(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_replacement_effects(game)
        destroy(game, card)
        assert not game.get_battlefield(p1).contains(card)
        assert not game.get_graveyard(p1).contains(card)
        assert p1.zones[Zone.LIBRARY].contains(card)

    def test_sacrificing_it_shuffles_it_into_its_owners_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = Progenitus(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_replacement_effects(game)
        sacrifice(game, p1, card)
        assert not game.get_graveyard(p1).contains(card)
        assert p1.zones[Zone.LIBRARY].contains(card)


