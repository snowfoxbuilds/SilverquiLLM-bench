"""Tests for Emeritus of Truce // Swords to Plowshares (SOS 13)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Color, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _find(zone_container, name):
    for obj in zone_container.get_all():
        if getattr(obj, "name", None) == name:
            return obj
    return None


def _creature(name, power=2, toughness=2, owner=None):
    return Creature(name=name, base_power=power, base_toughness=toughness,
                    owner=owner, controller=owner)


class TestProperties:
    def test_static_data(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 3
        assert CardType.CREATURE in card.card_types
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.prepared is False


class TestEnters:
    def _setup(self, game, p1):
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[emeritus])
        emeritus.register_triggers(game)
        return emeritus

    def test_creates_inkling_for_target_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = self._setup(game, p1)
        emeritus._resolve_target = p2
        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p1))
        _resolve_stack(game)
        token = _find(game.get_battlefield(p2), "Inkling")
        assert token is not None
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert Keyword.FLYING in token.keywords
        assert token.colors == {Color.WHITE, Color.BLACK}
        assert token.is_token is True
        assert _find(game.get_battlefield(p1), "Inkling") is None

    def test_default_target_is_controller(self) -> None:
        game = create_game()
        p1, _ = game.players
        emeritus = self._setup(game, p1)
        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p1))
        _resolve_stack(game)
        assert _find(game.get_battlefield(p1), "Inkling") is not None

    def test_prepared_when_opponent_outnumbers(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[
            _creature("A", owner=p2), _creature("B", owner=p2),
            _creature("C", owner=p2)])
        emeritus.register_triggers(game)
        emeritus._resolve_target = p1  # token to self -> p1 has 2, p2 has 3
        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p1))
        _resolve_stack(game)
        assert emeritus.prepared is True

    def test_not_prepared_when_not_outnumbered(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[_creature("A", owner=p2)])
        emeritus.register_triggers(game)
        emeritus._resolve_target = p1
        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p1))
        _resolve_stack(game)
        assert emeritus.prepared is False


class TestPrepared:
    def test_no_activated_ability_when_not_prepared(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        card.prepared = False
        assert card.get_activated_abilities() == []

    def test_activated_ability_when_prepared(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        card.prepared = True
        abilities = card.get_activated_abilities()
        assert len(abilities) == 1


class TestSwords:
    def test_cast_swords_copy_exiles_and_gains_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        emeritus.prepared = True
        victim = _creature("Victim", power=4, toughness=4, owner=p2)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[victim], life=20)
        emeritus.cast_swords_copy(game, victim)
        assert game.get_battlefield(p2).contains(victim) is False
        assert p2.zones[Zone.EXILE].contains(victim)
        assert p2.life == 24
        assert emeritus.prepared is False

    def test_activate_swords_ability(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        emeritus.prepared = True
        victim = _creature("Victim", power=3, toughness=3, owner=p2)
        set_board_state(game, 0, battlefield=[emeritus],
                        mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[victim], life=20)
        ability = emeritus.get_activated_abilities()[0]
        instance = ActivatedAbilityInstance(
            source=emeritus, controller=p1,
            cost=ability.cost, effect=ability.effect)
        p1._script.append(victim)  # choose_card -> exile the victim
        activate_ability(game, p1, instance)
        _resolve_stack(game)
        assert p2.zones[Zone.EXILE].contains(victim)
        assert p2.life == 23
        assert p1.mana_pool.total() == 0
        assert emeritus.prepared is False
