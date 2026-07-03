"""Tests for SOS 82 — Eternal Student."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_82.card_impl import EternalStudent
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestEternalStudentProperties:
    """Static card data should match the SOS 82 spec."""

    def test_is_zombie_warlock_creature(self) -> None:
        card = EternalStudent(owner=None)
        assert isinstance(card, Creature)
        assert "Zombie" in card.subtypes
        assert "Warlock" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = EternalStudent(owner=None)
        assert card.name == "Eternal Student"
        assert card.mana_cost == ManaCost.parse("{3}{B}")
        assert card.base_power == 4
        assert card.base_toughness == 2


class TestEternalStudentActivatedAbility:
    """Eternal Student should exile itself from your graveyard for two Inklings."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = EternalStudent(owner=None).get_activated_abilities()
        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_requires_one_and_black_mana_and_exiles_this_card_from_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EternalStudent(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[card])
        ability = card.get_activated_abilities()[0]

        p1.mana_pool.add(ManaType.BLACK, 1)
        assert ability.cost(game, card) is False
        assert game.get_graveyard(p1).contains(card)

        p1.mana_pool.add(ManaType.COLORLESS, 1)
        assert ability.cost(game, card) is True
        assert p1.mana_pool.total() == 0
        assert not game.get_graveyard(p1).contains(card)
        assert game.get_exile(p1).contains(card)

    def test_activation_cost_fails_when_this_card_is_not_in_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EternalStudent(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 1, ManaType.BLACK: 1},
        )
        ability = card.get_activated_abilities()[0]

        assert ability.cost(game, card) is False
        assert game.get_hand(p1).contains(card)
        assert not game.get_exile(p1).contains(card)

    def test_effect_creates_two_white_and_black_inkling_tokens_with_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ability = EternalStudent(owner=p1, controller=p1).get_activated_abilities()[0]

        ability.effect(game)

        tokens = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if getattr(permanent, "is_token", False)
        ]
        assert len(tokens) == 2

        for token in tokens:
            assert isinstance(token, Creature)
            assert token.power == 1
            assert token.toughness == 1
            assert "Inkling" in token.subtypes
            assert Keyword.FLYING in token.keywords
            assert get_colors(token) == {Color.WHITE, Color.BLACK}
            assert token.controller is p1
