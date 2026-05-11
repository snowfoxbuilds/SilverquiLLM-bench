"""Audited tests for Condemn (SPG collector number 74)."""
from __future__ import annotations
import pytest
from card_impl import Condemn
from engine.card import Creature, Instant
from engine.types import ManaCost, Zone
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestCondemnBasic:
    def test_is_instant(self) -> None:
        card = Condemn()
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = Condemn()
        assert card.name == "Condemn"

    def test_mana_cost(self) -> None:
        card = Condemn()
        assert card.mana_cost == ManaCost.parse("{W}")


@pytest.mark.ability
class TestCondemnAbility:
    def test_can_cast_requires_attacking_creature(self) -> None:
        """can_cast returns False when no attackers exist."""
        game = create_game()
        card = Condemn(owner=game.players[0])
        card.controller = game.players[0]
        assert card.can_cast(game) is False

    def test_get_targets_returns_attacking_creatures(self) -> None:
        game = create_game()
        attacker = Creature(name="Bear", owner=game.players[1], base_power=2, base_toughness=2)
        attacker.controller = game.players[1]
        attacker.is_attacking = True
        set_board_state(game, 1, battlefield=[attacker])
        card = Condemn(owner=game.players[0])
        card.controller = game.players[0]
        targets = card.get_targets(game)
        assert attacker in targets

    def test_on_resolve_removes_attacker_from_battlefield(self) -> None:
        """Primary effect: the attacking creature is removed from the battlefield."""
        game = create_game()
        p1 = game.players[1]
        attacker = Creature(name="Bear", owner=p1, base_power=2, base_toughness=3)
        attacker.controller = p1
        attacker.is_attacking = True
        set_board_state(game, 1, battlefield=[attacker])
        card = Condemn(owner=game.players[0])
        card.controller = game.players[0]
        card.chosen_targets = [attacker]
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        assert not bf.contains(attacker)

    def test_on_resolve_puts_attacker_on_bottom_of_library(self) -> None:
        """The attacking creature goes to the bottom of its owner's library."""
        game = create_game()
        p1 = game.players[1]
        attacker = Creature(name="Bear", owner=p1, base_power=2, base_toughness=3)
        attacker.controller = p1
        attacker.is_attacking = True
        set_board_state(game, 1, battlefield=[attacker])
        card = Condemn(owner=game.players[0])
        card.controller = game.players[0]
        card.chosen_targets = [attacker]
        card.on_resolve(game)
        library = p1.zones[Zone.LIBRARY]
        all_cards = library.get_all()
        assert attacker in all_cards

    def test_on_resolve_gains_life_equal_to_toughness(self) -> None:
        game = create_game()
        p1 = game.players[1]
        attacker = Creature(name="Bear", owner=p1, base_power=2, base_toughness=3)
        attacker.controller = p1
        attacker.is_attacking = True
        set_board_state(game, 1, battlefield=[attacker])
        card = Condemn(owner=game.players[0])
        card.controller = game.players[0]
        card.chosen_targets = [attacker]
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before + 3
