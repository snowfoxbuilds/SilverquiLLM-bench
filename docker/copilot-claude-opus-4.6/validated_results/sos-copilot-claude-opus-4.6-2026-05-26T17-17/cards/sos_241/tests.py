"""Tests for SOS 241 — Vicious Rivalry.

Sorcery {2}{B}{G}
As an additional cost to cast this spell, pay X life.
Destroy all artifacts and creatures with mana value X or less.
"""

from __future__ import annotations

from cards.sos.sos_241.card_impl import ViciousRivalry
from engine.card import Creature, Artifact, Sorcery
from engine.types import ManaCost, Zone
from test_utils import create_game, set_board_state


class TestViciousRivalryProperties:
    """Static card data should match the SOS 241 spec."""

    def test_name(self) -> None:
        card = ViciousRivalry(owner=None)
        assert card.name == "Vicious Rivalry"

    def test_mana_cost(self) -> None:
        card = ViciousRivalry(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{B}{G}")

    def test_is_sorcery(self) -> None:
        card = ViciousRivalry(owner=None)
        assert isinstance(card, Sorcery)


class TestViciousRivalryEffect:
    """Destroy all artifacts and creatures with mana value X or less."""

    def test_destroys_creatures_with_mv_equal_to_x(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ViciousRivalry(owner=p1, controller=p1)
        # Create a creature with mana value 2
        target = Creature(name="Bear", base_power=2, base_toughness=2)
        target.mana_cost = ManaCost.parse("{1}{G}")
        set_board_state(game, 1, battlefield=[target])
        # Cast with X=2 (pay 2 life as additional cost)
        card.x_value = 2
        card.on_resolve(game)
        # Bear (mv=2) should be destroyed
        bf = game.get_battlefield(p2).get_all()
        assert target not in bf

    def test_destroys_creatures_with_mv_less_than_x(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ViciousRivalry(owner=p1, controller=p1)
        target = Creature(name="Mite", base_power=1, base_toughness=1)
        target.mana_cost = ManaCost.parse("{W}")
        set_board_state(game, 1, battlefield=[target])
        card.x_value = 3
        card.on_resolve(game)
        bf = game.get_battlefield(p2).get_all()
        assert target not in bf

    def test_does_not_destroy_creatures_with_mv_greater_than_x(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ViciousRivalry(owner=p1, controller=p1)
        big = Creature(name="Dragon", base_power=5, base_toughness=5)
        big.mana_cost = ManaCost.parse("{4}{R}{R}")
        set_board_state(game, 1, battlefield=[big])
        card.x_value = 3
        card.on_resolve(game)
        bf = game.get_battlefield(p2).get_all()
        assert big in bf

    def test_destroys_artifacts_with_mv_equal_to_x(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ViciousRivalry(owner=p1, controller=p1)
        art = Artifact(name="Sol Ring")
        art.mana_cost = ManaCost.parse("{1}")
        set_board_state(game, 1, battlefield=[art])
        card.x_value = 1
        card.on_resolve(game)
        bf = game.get_battlefield(p2).get_all()
        assert art not in bf

    def test_x_zero_destroys_zero_mv_permanents(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ViciousRivalry(owner=p1, controller=p1)
        token = Creature(name="Token", base_power=1, base_toughness=1)
        token.mana_cost = ManaCost.parse("{0}")
        set_board_state(game, 1, battlefield=[token])
        card.x_value = 0
        card.on_resolve(game)
        bf = game.get_battlefield(p2).get_all()
        assert token not in bf

    def test_destroys_own_creatures_too(self) -> None:
        """Board wipe is symmetrical — destroys controller's creatures too."""
        game = create_game()
        p1 = game.players[0]
        card = ViciousRivalry(owner=p1, controller=p1)
        own_creature = Creature(name="Elf", base_power=1, base_toughness=1)
        own_creature.mana_cost = ManaCost.parse("{G}")
        set_board_state(game, 0, battlefield=[own_creature])
        card.x_value = 1
        card.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        assert own_creature not in bf
