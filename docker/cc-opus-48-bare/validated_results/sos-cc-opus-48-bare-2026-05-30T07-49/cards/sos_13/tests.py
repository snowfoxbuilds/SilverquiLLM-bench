"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _fire_etb(game, permanent, controller) -> None:
    game.trigger_manager.fire_event(
        game,
        EntersBattlefieldTriggeredEvent(permanent=permanent, controller=controller),
    )


def _inkling_tokens(game, player) -> list:
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if getattr(obj, "name", None) == "Inkling"
    ]


class TestEmeritusProperties:
    def test_name_and_stats(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_types_and_not_prepared_initially(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card._prepared is False


class TestEmeritusEnters:
    def test_creates_inkling_flier_for_chosen_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[emeritus])
        emeritus.register_triggers(game)

        p1._script.append(p2)  # target player for the token
        _fire_etb(game, emeritus, p1)
        _resolve_all(game)

        tokens = _inkling_tokens(game, p2)
        assert len(tokens) == 1
        token = tokens[0]
        assert token.power == 1
        assert token.toughness == 1
        assert Keyword.FLYING in token.keywords
        assert token.is_token is True
        assert "Inkling" in token.subtypes

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        foe1 = Creature(name="Foe1", base_power=1, base_toughness=1)
        foe2 = Creature(name="Foe2", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[foe1, foe2])
        emeritus.register_triggers(game)

        # Give the token to the opponent so counts are unambiguous:
        # p1 has 1 creature (Emeritus); p2 ends with 3 (foe1, foe2, token).
        p1._script.append(p2)
        _fire_etb(game, emeritus, p1)
        _resolve_all(game)

        assert emeritus._prepared is True

    def test_not_prepared_when_you_have_at_least_as_many(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        ally = Creature(name="Ally", base_power=2, base_toughness=2)
        foe = Creature(name="Foe", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[emeritus, ally])
        set_board_state(game, 1, battlefield=[foe])
        emeritus.register_triggers(game)

        # p1 has Emeritus + Ally + token = 3; p2 has 1. Opponent has fewer.
        p1._script.append(p1)
        _fire_etb(game, emeritus, p1)
        _resolve_all(game)

        assert emeritus._prepared is False


class TestEmeritusPrepared:
    def test_prepared_ability_exiles_and_gains_life_then_unprepares(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        victim = Creature(name="Ox", base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[emeritus], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[victim], life=20)
        emeritus._prepared = True

        ability = emeritus.get_activated_abilities()[0]
        assert ability.cost(game, emeritus) is True
        p1._script.append(victim)  # creature to exile
        ability.effect(game)

        assert victim in game.get_exile(p2).get_all()
        assert victim not in game.get_battlefield(p2).get_all()
        assert p2.life == 24  # its controller gains life equal to its power
        assert p1.mana_pool.total() == 0
        assert emeritus._prepared is False

    def test_ability_unavailable_when_not_prepared(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        victim = Creature(name="Ox", base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[emeritus], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[victim], life=20)
        emeritus._prepared = False

        ability = emeritus.get_activated_abilities()[0]
        assert ability.cost(game, emeritus) is False
        # Mana was not spent and nothing was exiled.
        assert p1.mana_pool.total() == 1
        assert victim in game.get_battlefield(p2).get_all()

    def test_ability_unavailable_without_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        victim = Creature(name="Ox", base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[emeritus], mana={})
        set_board_state(game, 1, battlefield=[victim], life=20)
        emeritus._prepared = True

        ability = emeritus.get_activated_abilities()[0]
        assert ability.cost(game, emeritus) is False
