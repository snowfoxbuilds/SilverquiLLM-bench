"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.types import Color, Keyword, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


def _make_bear(name: str) -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _normalized_colors(card: object) -> set[str]:
    colors = getattr(card, "colors", set())
    normalized: set[str] = set()
    for color in colors:
        if isinstance(color, Color):
            normalized.add(color.value)
        else:
            normalized.add(str(color))
    return normalized


class TestEmeritusOfTruceProperties:
    """Static front-face data and prepared tracking should match the spec."""

    def test_is_a_cat_cleric_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_name(self) -> None:
        assert (
            EmeritusOfTruceSwordsToPlowshares(owner=None).name
            == "Emeritus of Truce // Swords to Plowshares"
        )

    def test_front_face_mana_cost(self) -> None:
        assert (
            EmeritusOfTruceSwordsToPlowshares(owner=None).mana_cost
            == ManaCost.parse("{1}{W}{W}")
        )

    def test_power_and_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_starts_unprepared(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert hasattr(card, "is_prepared")
        assert card.is_prepared is False


class TestEmeritusOfTruceEntersAbility:
    """Its ETB should create the targeted Inkling, then check preparation."""

    def test_target_player_gets_a_1_1_white_black_inkling_with_flying(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1},
        )

        p1.choose_card = lambda cards, _description: p2  # type: ignore[method-assign]
        p1.choose_target = lambda _options, _requirement: p2  # type: ignore[method-assign]

        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")

        tokens = [
            permanent
            for permanent in game.get_battlefield(p2).get_all()
            if getattr(permanent, "is_token", False)
        ]
        assert len(tokens) == 1

        token = tokens[0]
        assert isinstance(token, Creature)
        assert token.name == "Inkling"
        assert "Inkling" in token.subtypes
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert Keyword.FLYING in token.keywords
        assert _normalized_colors(token) == {"W", "B"}
        assert token.owner is p2
        assert token.controller is p2

    def test_becomes_prepared_only_after_the_created_token_changes_creature_counts(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1},
        )
        set_board_state(game, 1, battlefield=[_make_bear("Opponent Bear")])

        p1.choose_card = lambda cards, _description: p2  # type: ignore[method-assign]
        p1.choose_target = lambda _options, _requirement: p2  # type: ignore[method-assign]

        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")

        assert card.is_prepared is True

    def test_does_not_become_prepared_when_no_opponent_controls_more_creatures_after_resolution(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1},
        )
        set_board_state(game, 1, battlefield=[_make_bear("Opponent Bear")])

        p1.choose_card = lambda cards, _description: p1  # type: ignore[method-assign]
        p1.choose_target = lambda _options, _requirement: p1  # type: ignore[method-assign]

        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")

        tokens = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if getattr(permanent, "is_token", False)
        ]
        assert len(tokens) == 1
        assert card.is_prepared is False
