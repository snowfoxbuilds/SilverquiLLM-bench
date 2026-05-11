"""Audited tests for Gatekeeper of Malakir (FDN collector number 713)."""
from __future__ import annotations
import pytest
from card_impl import GatekeeperOfMalakir
from engine.card import Creature
from engine.types import ManaCost


@pytest.mark.basic
class TestGatekeeperOfMalakirBasic:
    def test_is_creature(self) -> None:
        card = GatekeeperOfMalakir()
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = GatekeeperOfMalakir()
        assert card.name == "Gatekeeper of Malakir"

    def test_mana_cost(self) -> None:
        card = GatekeeperOfMalakir()
        assert card.mana_cost == ManaCost.parse("{B}{B}")

    def test_power_toughness(self) -> None:
        card = GatekeeperOfMalakir()
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = GatekeeperOfMalakir()
        assert "Vampire" in card.subtypes
        assert "Warrior" in card.subtypes


@pytest.mark.ability
class TestGatekeeperOfMalakirKicker:
    def test_has_kicker(self) -> None:
        card = GatekeeperOfMalakir()
        assert hasattr(card, "kicked")
        assert card.kicked is False

    def test_kicker_cost(self) -> None:
        card = GatekeeperOfMalakir()
        assert card.kicker_cost == ManaCost.parse("{B}")

    def test_kicked_etb_forces_sacrifice(self) -> None:
        """When kicked, ETB should cause target player to sacrifice a creature."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature as Cr
        from engine.triggers import EventType
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        card = GatekeeperOfMalakir(owner=p0)
        card.controller = p0
        card.kicked = True
        # Target p1 who has a creature
        victim = Cr(name="Victim", owner=p1, base_power=1, base_toughness=1)
        victim.controller = p1
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[victim])
        card.chosen_targets = [p1]
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD,
                                        {"permanent": card, "controller": p0})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        bf1 = game.get_battlefield(p1)
        assert not bf1.contains(victim)

    def test_not_kicked_etb_no_sacrifice(self) -> None:
        """When not kicked, ETB should not cause sacrifice."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature as Cr
        from engine.triggers import EventType
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        card = GatekeeperOfMalakir(owner=p0)
        card.controller = p0
        card.kicked = False
        victim = Cr(name="Victim", owner=p1, base_power=1, base_toughness=1)
        victim.controller = p1
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[victim])
        card.chosen_targets = [p1]
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD,
                                        {"permanent": card, "controller": p0})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        bf1 = game.get_battlefield(p1)
        assert bf1.contains(victim)
