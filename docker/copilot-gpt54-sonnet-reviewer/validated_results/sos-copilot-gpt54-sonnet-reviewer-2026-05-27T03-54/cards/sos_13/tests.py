"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature, Instant
from engine.types import CardType, Color, Keyword, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


def _is_prepared(card) -> bool:
    """Return the card's prepared state using the expected public flag."""
    return bool(getattr(card, "prepared", getattr(card, "is_prepared", False)))


def _inkling_tokens(game, player) -> list[Creature]:
    """Return Inkling creature tokens controlled by *player*."""
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if isinstance(obj, Creature)
        and getattr(obj, "is_token", False)
        and "Inkling" in getattr(obj, "subtypes", set())
    ]


class TestEmeritusOfTruceProperties:
    """Static front-face characteristics should match the SOS 13 spec."""

    def test_is_cat_cleric_creature_with_expected_front_face_stats(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert CardType.CREATURE in card.card_types
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_rules_text_matches_the_oracle_trigger_and_prepared_clause(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)

        assert card.rules_text == (
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)"
        )


class TestEmeritusOfTruceResolution:
    """Resolution should create the target player's Inkling and set prepared correctly."""

    def test_target_player_gets_the_inkling_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1},
        )

        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares", targets=[p2])

        assert game.get_battlefield(p1).contains(card)
        assert len(_inkling_tokens(game, p1)) == 0
        assert len(_inkling_tokens(game, p2)) == 1

    def test_created_inkling_is_a_one_one_flying_creature_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1},
        )

        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares", targets=[p2])

        token = _inkling_tokens(game, p2)[0]
        assert "Inkling" in token.subtypes
        assert CardType.CREATURE in token.card_types
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert Keyword.FLYING in token.keywords
        assert token.owner is p2
        assert token.controller is p2

    def test_created_inkling_exposes_white_and_black_colors(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1},
        )

        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares", targets=[p2])

        token = _inkling_tokens(game, p2)[0]
        assert token.colors == {Color.WHITE, Color.BLACK}
        assert token.color_identity == {Color.WHITE, Color.BLACK}

    def test_becomes_prepared_when_targets_token_makes_an_opponent_control_more_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        opposing_bear = Creature(
            name="Runeclaw Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1},
        )
        set_board_state(game, 1, battlefield=[opposing_bear])

        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares", targets=[p2])

        assert _is_prepared(card) is True

    def test_does_not_become_prepared_when_no_opponent_controls_more_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1},
        )

        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares", targets=[p1])

        assert _is_prepared(card) is False


class TestEmeritusPreparedSpell:
    """Prepared public surfaces should expose and cast the Swords to Plowshares copy."""

    def test_prepared_spell_surface_exposes_the_swords_to_plowshares_half(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        spell = card.prepared_spell

        assert isinstance(spell, Instant)
        assert spell is not None
        assert spell.name == "Swords to Plowshares"
        assert CardType.INSTANT in spell.card_types
        assert spell.mana_cost == ManaCost.parse("{W}")
        assert spell.controller is p1
        assert spell.owner is p1

    def test_cast_prepared_spell_requires_the_card_to_be_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        with pytest.raises(ValueError, match="not prepared"):
            card.cast_prepared_spell(game)

    def test_cast_prepared_spell_unprepares_source_and_puts_copy_on_stack(self) -> None:
        target = Creature(
            name="Target Bear",
            base_power=2,
            base_toughness=2,
        )
        game = create_game(scripts=([target], []))
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[target])
        card.prepare()

        spell = card.cast_prepared_spell(game)

        assert _is_prepared(card) is False
        assert game.get_battlefield(p1).contains(card)
        assert game.stack.peek().source is spell
        assert spell.name == "Swords to Plowshares"

    def test_prepared_spell_copy_exiles_target_creature_and_gains_life_equal_to_power(self) -> None:
        target = Creature(
            name="Siege Mastodon",
            base_power=3,
            base_toughness=5,
        )
        game = create_game(player2_life=10, scripts=([target], []))
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[target])
        card.prepare()

        spell = card.cast_prepared_spell(game)
        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)

        assert spell.name == "Swords to Plowshares"
        assert game.get_exile(p2).contains(target)
        assert not game.get_battlefield(p2).contains(target)
        assert p2.life == 13
