"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.casting import resolve_top
from engine.events import SpellCastTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


def _bear(name: str = "Bear", power: int = 2) -> Creature:
    c = Creature(name=name, base_power=power, base_toughness=2)
    c.card_types = {CardType.CREATURE}
    return c


class TestProperties:
    def test_basics(self) -> None:
        c = SilverquillTheDisputant(owner=None)
        assert c.name == "Silverquill, the Disputant"
        assert c.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert c.base_power == 4 and c.base_toughness == 4
        assert Supertype.LEGENDARY in c.supertypes
        assert {"Elder", "Dragon"} <= c.subtypes
        assert c.keywords & Keyword.FLYING
        assert c.keywords & Keyword.VIGILANCE


class TestCasualty:
    def _setup(self, power: int = 2):
        game = create_game()
        p1 = game.players[0]
        silver = SilverquillTheDisputant(owner=p1, controller=p1)
        bear = _bear("Sac", power=power)
        set_board_state(game, 0, battlefield=[silver, bear])
        silver.register_triggers(game)
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        bolt.owner = p1
        bolt.controller = p1
        spell_obj = StackObject(source=bolt, controller=p1)
        return game, p1, silver, bear, bolt, spell_obj

    def test_casualty_copies_spell_and_sacrifices(self) -> None:
        game, p1, silver, bear, bolt, spell_obj = self._setup()
        p1._script.extend([True, bear])  # pay casualty, sacrifice bear
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=spell_obj, card=bolt, controller=p1, player=p1),
        )
        # Resolve the casualty trigger.
        resolve_top(game)
        # Bear sacrificed.
        assert bear not in game.get_battlefield(p1).get_all()
        assert bear in p1.zones[Zone.GRAVEYARD].get_all()
        # A copy of the spell is on the stack.
        assert not game.stack.is_empty()

    def test_decline_casualty(self) -> None:
        game, p1, silver, bear, bolt, spell_obj = self._setup()
        p1._script.extend([False])  # decline
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=spell_obj, card=bolt, controller=p1, player=p1),
        )
        resolve_top(game)
        assert bear in game.get_battlefield(p1).get_all()
        assert game.stack.is_empty()

    def test_no_trigger_for_non_instant_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silver = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silver, _bear("Sac")])
        silver.register_triggers(game)
        # Casting a creature spell — casualty should not apply.
        ogre = Creature(name="Ogre", base_power=3, base_toughness=3)
        ogre.owner = p1
        ogre.controller = p1
        spell_obj = StackObject(source=ogre, controller=p1)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=spell_obj, card=ogre, controller=p1, player=p1),
        )
        assert game.stack.is_empty()

    def test_no_trigger_for_opponent_cast(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silver = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silver, _bear("Sac")])
        silver.register_triggers(game)
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        bolt.owner = p2
        bolt.controller = p2
        spell_obj = StackObject(source=bolt, controller=p2)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=spell_obj, card=bolt, controller=p2, player=p2),
        )
        assert game.stack.is_empty()
