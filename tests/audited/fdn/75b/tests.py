"""Audited tests for Sphinx's Tutelage (SPG collector number 75, dir 75b)."""
from __future__ import annotations
import pytest
from card_impl import SphinxsTutelage
from engine.card import CardImpl, Enchantment
from engine.triggers import EventType
from engine.types import CardType, ManaCost, Zone
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestSphinxsTutelageBasic:
    def test_is_enchantment(self) -> None:
        card = SphinxsTutelage()
        assert isinstance(card, Enchantment)

    def test_name(self) -> None:
        card = SphinxsTutelage()
        assert card.name == "Sphinx's Tutelage"

    def test_mana_cost(self) -> None:
        card = SphinxsTutelage()
        assert card.mana_cost == ManaCost.parse("{2}{U}")


@pytest.mark.ability
class TestSphinxsTutelageAbilities:
    def test_has_activated_ability(self) -> None:
        card = SphinxsTutelage()
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_activated_ability_description(self) -> None:
        card = SphinxsTutelage()
        abilities = card.get_activated_abilities()
        assert "Draw a card" in abilities[0].description

    def test_register_triggers_succeeds(self) -> None:
        game = create_game()
        card = SphinxsTutelage(owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)


@pytest.mark.rules
class TestSphinxsTutelageMill:
    def test_mill_removes_from_library(self) -> None:
        game = create_game()
        p = game.players[1]
        c1 = CardImpl(name="Card1")
        c2 = CardImpl(name="Card2")
        c1.owner = p
        c2.owner = p
        p.zones[Zone.LIBRARY].add(c1)
        p.zones[Zone.LIBRARY].add(c2)
        milled = SphinxsTutelage._mill(game, p, 2)
        assert len(milled) == 2

    def test_draw_event_triggers_opponent_mill(self) -> None:
        """Firing DRAWS_CARD for the controller mills 2 cards from opponent."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        card = SphinxsTutelage(owner=p0)
        card.controller = p0
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        # Stock opponent library with cards that don't share a color (no repeat)
        lib_card1 = CardImpl(name="LibA")
        lib_card1.card_types = {CardType.CREATURE}
        lib_card1.colors = set()  # colorless
        lib_card2 = CardImpl(name="LibB")
        lib_card2.card_types = {CardType.CREATURE}
        lib_card2.colors = set()  # colorless
        set_board_state(game, 1, life=20)
        p1.zones[Zone.LIBRARY].add(lib_card1)
        p1.zones[Zone.LIBRARY].add(lib_card2)
        lib_before = len(p1.zones[Zone.LIBRARY].get_all())
        # Fire draw event for the controller
        game.trigger_manager.fire_event(game, EventType.DRAWS_CARD, {"player": p0})
        # Resolve the triggered ability from the stack
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        gy_cards = p1.zones[Zone.GRAVEYARD].get_all()
        assert len(gy_cards) >= 2

    def test_draw_event_does_not_trigger_for_opponent(self) -> None:
        """DRAWS_CARD for the opponent should NOT fire the tutelage trigger."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        card = SphinxsTutelage(owner=p0)
        card.controller = p0
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        lib_card = CardImpl(name="LibX")
        p1.zones[Zone.LIBRARY].add(lib_card)
        game.trigger_manager.fire_event(game, EventType.DRAWS_CARD, {"player": p1})
        # Stack should be empty — no trigger fired
        assert game.stack.is_empty()
