"""Audited tests for Goblin Bushwhacker (SPG collector number 78)."""
from __future__ import annotations
import pytest
from card_impl import GoblinBushwhacker
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestGoblinBushwhackerBasic:
    def test_is_creature(self) -> None:
        card = GoblinBushwhacker()
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = GoblinBushwhacker()
        assert card.name == "Goblin Bushwhacker"

    def test_mana_cost(self) -> None:
        card = GoblinBushwhacker()
        assert card.mana_cost == ManaCost.parse("{R}")

    def test_power_toughness(self) -> None:
        card = GoblinBushwhacker()
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_subtypes(self) -> None:
        card = GoblinBushwhacker()
        assert "Goblin" in card.subtypes
        assert "Warrior" in card.subtypes


@pytest.mark.ability
class TestGoblinBushwhackerKicker:
    def test_has_kicker(self) -> None:
        card = GoblinBushwhacker()
        assert card.has_kicker is True

    def test_kicker_cost(self) -> None:
        card = GoblinBushwhacker()
        assert card.kicker_cost == ManaCost.parse("{R}")

    def test_kicked_defaults_false(self) -> None:
        card = GoblinBushwhacker()
        assert card.kicked is False

    def test_register_triggers_succeeds(self) -> None:
        game = create_game()
        p = game.players[0]
        card = GoblinBushwhacker(owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)


@pytest.mark.ability
class TestGoblinBushwhackerKickedETB:
    def test_kicked_etb_grants_haste_to_creatures(self) -> None:
        """When kicked, all creatures you control get haste until end of turn."""
        from engine.triggers import EventType
        game = create_game()
        p = game.players[0]
        card = GoblinBushwhacker(owner=p)
        card.controller = p
        card.kicked = True
        ally = Creature(name="Ally", owner=p, base_power=2, base_toughness=2)
        ally.controller = p
        set_board_state(game, 0, battlefield=[card, ally])
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"permanent": card})
        # Resolve the triggered ability from the stack
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.HASTE & ally.keywords

    def test_kicked_etb_grants_plus_one_power(self) -> None:
        """When kicked, all creatures get +1/+0."""
        from engine.triggers import EventType
        game = create_game()
        p = game.players[0]
        card = GoblinBushwhacker(owner=p)
        card.controller = p
        card.kicked = True
        ally = Creature(name="Ally", owner=p, base_power=2, base_toughness=2)
        ally.controller = p
        set_board_state(game, 0, battlefield=[card, ally])
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"permanent": card})
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert ally.base_power == 3

    def test_not_kicked_etb_does_nothing(self) -> None:
        """When not kicked, creatures don't get buff."""
        from engine.triggers import EventType
        game = create_game()
        p = game.players[0]
        card = GoblinBushwhacker(owner=p)
        card.controller = p
        card.kicked = False
        ally = Creature(name="Ally", owner=p, base_power=2, base_toughness=2)
        ally.controller = p
        set_board_state(game, 0, battlefield=[card, ally])
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"permanent": card})
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert ally.base_power == 2
        assert not (Keyword.HASTE & ally.keywords)
