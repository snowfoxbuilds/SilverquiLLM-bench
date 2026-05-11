"""Audited tests for Gnarlid Colony (FDN collector number 224)."""
from __future__ import annotations
import pytest
from card_impl import GnarlidColony
from engine.card import Creature
from engine.types import ManaCost


@pytest.mark.basic
class TestGnarlidColonyBasic:
    def test_is_creature(self) -> None:
        card = GnarlidColony()
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = GnarlidColony()
        assert card.name == "Gnarlid Colony"

    def test_mana_cost(self) -> None:
        card = GnarlidColony()
        assert card.mana_cost == ManaCost.parse("{1}{G}")

    def test_power_toughness(self) -> None:
        card = GnarlidColony()
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = GnarlidColony()
        assert "Beast" in card.subtypes


@pytest.mark.ability
class TestGnarlidColonyKicker:
    def test_has_kicker(self) -> None:
        card = GnarlidColony()
        assert hasattr(card, "kicked")
        assert card.kicked is False

    def test_kicker_cost(self) -> None:
        card = GnarlidColony()
        assert card.kicker_cost == ManaCost.parse("{2}{G}")

    def test_kicked_etb_adds_two_counters(self) -> None:
        """When kicked, ETB should add two +1/+1 counters."""
        from tests.test_utils import create_game, set_board_state
        from engine.triggers import EventType
        game = create_game()
        p = game.players[0]
        card = GnarlidColony(owner=p)
        card.controller = p
        card.kicked = True
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        counters_before = card.plus_one_counters
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD,
                                        {"permanent": card, "controller": p})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        assert card.plus_one_counters == counters_before + 2

    def test_not_kicked_etb_no_counters(self) -> None:
        """When not kicked, ETB should not add counters."""
        from tests.test_utils import create_game, set_board_state
        from engine.triggers import EventType
        game = create_game()
        p = game.players[0]
        card = GnarlidColony(owner=p)
        card.controller = p
        card.kicked = False
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        counters_before = card.plus_one_counters
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD,
                                        {"permanent": card, "controller": p})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        assert card.plus_one_counters == counters_before
