"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.types import CardType, Color, Keyword, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


def _bear(name: str) -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _creatures_on_battlefield(game, player) -> list[Creature]:
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if isinstance(obj, Creature)
    ]


class TestEmeritusOfTruceProperties:
    """Static card data should match the SOS 13 creature-side spec."""

    def test_is_cat_cleric_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)

        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_name_and_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)

        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_power_and_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)

        assert card.base_power == 3
        assert card.base_toughness == 3


class TestEmeritusOfTruceEntersAbility:
    """ETB trigger should create the targeted Inkling and set prepared correctly."""

    def test_target_player_gets_a_one_one_flying_inkling_token(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1},
        )
        p1.choose_target = lambda options, requirement: p2

        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")

        assert game.get_battlefield(p1).contains(card)
        creatures = _creatures_on_battlefield(game, p2)
        assert len(creatures) == 1

        token = creatures[0]
        assert token.is_token is True
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert "Inkling" in token.subtypes
        assert Keyword.FLYING in token.keywords

    def test_target_player_gets_white_and_black_inkling_token(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1},
        )
        p1.choose_target = lambda options, requirement: p2

        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")

        token = _creatures_on_battlefield(game, p2)[0]
        assert token.colors == {Color.WHITE, Color.BLACK}

    def test_becomes_prepared_when_opponent_still_controls_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1},
        )
        set_board_state(
            game,
            1,
            battlefield=[_bear("Bear A"), _bear("Bear B")],
        )
        p1.choose_target = lambda options, requirement: p2

        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")

        assert getattr(card, "is_prepared", False) is True

    def test_does_not_become_prepared_when_your_token_catches_you_up(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1},
        )
        set_board_state(
            game,
            1,
            battlefield=[_bear("Bear A"), _bear("Bear B")],
        )
        p1.choose_target = lambda options, requirement: p1

        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")

        assert len(_creatures_on_battlefield(game, p1)) == 2
        assert getattr(card, "is_prepared", False) is False
