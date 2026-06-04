"""Tests for Silverquill, the Disputant (SOS 226)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.events import SpellCastTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class _GainLifeInstant(Instant):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Surge")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 3


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _push_spell(game, spell, controller):
    obj = StackObject(source=spell, controller=controller,
                      on_resolve=lambda g: spell.on_resolve(g))
    game.stack.push(obj)
    return obj


class TestProperties:
    def test_static_data(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert card.base_power == 4
        assert card.base_toughness == 4
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes


class TestCasualty:
    def _setup(self, game, p1, *, fodder=True):
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        bf = [dragon]
        creature = None
        if fodder:
            creature = Creature(name="Token", base_power=2, base_toughness=2,
                                owner=p1, controller=p1)
            bf.append(creature)
        set_board_state(game, 0, battlefield=bf, life=20)
        dragon.register_triggers(game)
        return dragon, creature

    def test_pay_copies_spell(self) -> None:
        game = create_game()
        p1, _ = game.players
        _dragon, creature = self._setup(game, p1)
        surge = _GainLifeInstant(owner=p1, controller=p1)
        _push_spell(game, surge, p1)
        p1._script.extend([True, creature])  # pay, sacrifice the token
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(spell=surge, card=surge,
                                          player=p1, controller=p1))
        _resolve_stack(game)
        # Original + copy each gain 3 -> +6.
        assert p1.life == 26
        assert game.get_graveyard(p1).contains(creature)

    def test_decline_no_copy(self) -> None:
        game = create_game()
        p1, _ = game.players
        _dragon, creature = self._setup(game, p1)
        surge = _GainLifeInstant(owner=p1, controller=p1)
        _push_spell(game, surge, p1)
        p1._script.append(False)
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(spell=surge, card=surge,
                                          player=p1, controller=p1))
        _resolve_stack(game)
        assert p1.life == 23
        assert game.get_battlefield(p1).contains(creature)

    def test_no_fodder_no_copy(self) -> None:
        # Casualty can sacrifice any creature with power >= 1, including the
        # dragon itself — so the no-fodder branch only triggers when the
        # controller has no eligible creatures at all.
        game = create_game()
        p1, _ = game.players
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, life=20)
        dragon.register_triggers(game)
        surge = _GainLifeInstant(owner=p1, controller=p1)
        _push_spell(game, surge, p1)
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(spell=surge, card=surge,
                                          player=p1, controller=p1))
        _resolve_stack(game)
        assert p1.life == 23
        assert p1.remaining_choices == 0

    def test_not_opponent_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        self._setup(game, p1)
        opp_surge = _GainLifeInstant(owner=p2, controller=p2)
        _push_spell(game, opp_surge, p2)
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(spell=opp_surge, card=opp_surge,
                                          player=p2, controller=p2))
        _resolve_stack(game)
        # No casualty prompt consumed; opponent's spell resolved once only.
        assert p1.remaining_choices == 0

    def test_not_creature_spell(self) -> None:
        game = create_game()
        p1, _ = game.players
        dragon, _creature = self._setup(game, p1)
        beast = Creature(name="Beast", base_power=3, base_toughness=3,
                         owner=p1, controller=p1)
        obj = StackObject(source=beast, controller=p1)
        game.stack.push(obj)
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(spell=beast, card=beast,
                                          player=p1, controller=p1))
        # Creature spell shouldn't push a casualty trigger.
        assert len(game.stack._items) == 1
