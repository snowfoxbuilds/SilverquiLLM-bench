"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.abilities import (
    AbilityError,
    ActivatedAbilityInstance,
    activate_ability,
)
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import _resolve_top_of_stack, cast_spell, create_game, set_board_state

_NAME = "Emeritus of Truce // Swords to Plowshares"


def _bear(name: str = "Bear", power: int = 2, toughness: int = 2) -> Creature:
    return Creature(name=name, base_power=power, base_toughness=toughness)


def _swords_instance(emeritus, player) -> ActivatedAbilityInstance:
    ab = emeritus.get_activated_abilities()[0]
    return ActivatedAbilityInstance(
        source=emeritus, controller=player, cost=ab.cost,
        effect=ab.effect, is_mana_ability=False,
    )


class TestEmeritusProperties:
    def test_name(self) -> None:
        assert EmeritusOfTruceSwordsToPlowshares(owner=None).name == _NAME

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_three_three_cat_cleric(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes
        assert CardType.CREATURE in card.card_types

    def test_not_prepared_initially(self) -> None:
        assert EmeritusOfTruceSwordsToPlowshares(owner=None).is_prepared is False


class TestEmeritusETB:
    def test_etb_creates_inkling_for_target_player(self) -> None:
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        # Target the opponent for the token.
        p1._script.append(p2)
        cast_spell(game, 0, _NAME)
        inklings = [
            c for c in game.get_battlefield(p2).get_all()
            if getattr(c, "name", None) == "Inkling"
        ]
        assert len(inklings) == 1
        token = inklings[0]
        assert token.base_power == 1 and token.base_toughness == 1
        assert Keyword.FLYING in token.keywords
        assert token.is_token is True

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        game = create_game()
        p1, p2 = game.players
        # Opponent already controls 3 creatures; we control only Emeritus.
        set_board_state(game, 1, battlefield=[_bear("B1"), _bear("B2"), _bear("B3")])
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        # Target ourselves: token enters under us, my_count = token + Emeritus = 2,
        # opponent has 3 > 2 -> prepared.
        p1._script.append(p1)
        cast_spell(game, 0, _NAME)
        assert emeritus.is_prepared is True

    def test_not_prepared_when_counts_equal(self) -> None:
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        game = create_game()
        p1, p2 = game.players
        # Opponent controls 2 creatures. We target ourselves: token + Emeritus = 2.
        # 2 > 2 is false -> not prepared (token placement subtlety).
        set_board_state(game, 1, battlefield=[_bear("B1"), _bear("B2")])
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        p1._script.append(p1)
        cast_spell(game, 0, _NAME)
        assert emeritus.is_prepared is False

    def test_not_prepared_when_you_have_more(self) -> None:
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_bear("Mine1"), _bear("Mine2")],
                        hand=[emeritus],
                        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        # Opponent has none; target opponent so token goes to them (count 1) —
        # still fewer than our 2 bears + Emeritus.
        p1._script.append(p2)
        cast_spell(game, 0, _NAME)
        assert emeritus.is_prepared is False


class TestEmeritusPreparedSwords:
    def test_cast_copy_exiles_creature_and_gains_life(self) -> None:
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        victim = _bear("Ox", power=4, toughness=4)
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[emeritus], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[victim], life=20)
        emeritus.is_prepared = True
        # Script the target creature for the Swords effect.
        p1._script.append(victim)
        activate_ability(game, p1, _swords_instance(emeritus, p1))
        _resolve_top_of_stack(game)
        assert victim in game.players[1].zones[Zone.EXILE].get_all()
        assert victim not in game.get_battlefield(p2).get_all()
        assert p2.life == 24  # gained life equal to the exiled creature's power
        assert emeritus.is_prepared is False  # casting the copy unprepares it
        assert p1.mana_pool.get(ManaType.WHITE) == 0  # paid {W}

    def test_cannot_cast_copy_when_not_prepared(self) -> None:
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        victim = _bear("Ox")
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[emeritus], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[victim])
        assert emeritus.is_prepared is False
        try:
            activate_ability(game, p1, _swords_instance(emeritus, p1))
        except AbilityError:
            pass
        else:
            raise AssertionError("expected AbilityError — not prepared")
        # Cost not paid; creature untouched.
        assert victim in game.get_battlefield(p2).get_all()
        assert p1.mana_pool.get(ManaType.WHITE) == 1

    def test_copy_is_single_use_per_preparation(self) -> None:
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        v1 = _bear("V1", power=1, toughness=1)
        v2 = _bear("V2", power=1, toughness=1)
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[emeritus], mana={ManaType.WHITE: 2})
        set_board_state(game, 1, battlefield=[v1, v2])
        emeritus.is_prepared = True
        p1._script.append(v1)
        activate_ability(game, p1, _swords_instance(emeritus, p1))
        _resolve_top_of_stack(game)
        # Second activation is illegal — already unprepared.
        try:
            activate_ability(game, p1, _swords_instance(emeritus, p1))
        except AbilityError:
            pass
        else:
            raise AssertionError("expected AbilityError — copy already cast")
        assert v2 in game.get_battlefield(p2).get_all()
