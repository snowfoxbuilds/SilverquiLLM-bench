"""Audited tests for Wishclaw Talisman (FDN collector number 617)."""
from __future__ import annotations
import pytest
from card_impl import WishclawTalisman
from engine.card import Artifact, CardImpl
from engine.types import CardType, Zone
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestWishclawTalismanBasic:
    def test_is_artifact(self) -> None:
        card = WishclawTalisman(name="Wishclaw Talisman", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types
    def test_name(self) -> None:
        card = WishclawTalisman(name="Wishclaw Talisman", owner=None)
        assert card.name == "Wishclaw Talisman"
    def test_starts_with_three_wish_counters(self) -> None:
        card = WishclawTalisman(name="Wishclaw Talisman", owner=None)
        assert card.wish_counters == 3
    def test_has_activated_ability(self) -> None:
        card = WishclawTalisman(name="Wishclaw Talisman", owner=None)
        assert len(card.get_activated_abilities()) >= 1

@pytest.mark.ability
class TestWishclawTalismanAbility:
    def test_activation_removes_wish_counter(self) -> None:
        """Activating removes a wish counter."""
        game = create_game()
        talisman = WishclawTalisman(name="Wishclaw Talisman", owner=game.players[0])
        talisman.controller = game.players[0]
        set_board_state(game, 0, battlefield=[talisman])
        lib_card = CardImpl(name="LibCard", owner=game.players[0])
        game.players[0].zones[Zone.LIBRARY].add(lib_card)
        abilities = talisman.get_activated_abilities()
        abilities[0].cost(game, talisman)
        assert talisman.wish_counters == 2

    def test_activation_tutors_card_to_hand(self) -> None:
        """Activating searches library and puts a card into hand."""
        game = create_game()
        talisman = WishclawTalisman(name="Wishclaw Talisman", owner=game.players[0])
        talisman.controller = game.players[0]
        lib_card = CardImpl(name="LibCard", owner=game.players[0])
        set_board_state(game, 0, battlefield=[talisman])
        game.players[0].zones[Zone.LIBRARY].add(lib_card)
        hand_before = len(list(game.players[0].zones[Zone.HAND].get_all()))
        abilities = talisman.get_activated_abilities()
        abilities[0].cost(game, talisman)
        abilities[0].effect(game)
        hand_after = len(list(game.players[0].zones[Zone.HAND].get_all()))
        assert hand_after == hand_before + 1

    def test_cannot_activate_with_zero_counters(self) -> None:
        """Cannot activate when wish counters are exhausted."""
        game = create_game()
        talisman = WishclawTalisman(name="Wishclaw Talisman", owner=game.players[0])
        talisman.controller = game.players[0]
        talisman.wish_counters = 0
        set_board_state(game, 0, battlefield=[talisman])
        abilities = talisman.get_activated_abilities()
        cost_paid = abilities[0].cost(game, talisman)
        assert not cost_paid
