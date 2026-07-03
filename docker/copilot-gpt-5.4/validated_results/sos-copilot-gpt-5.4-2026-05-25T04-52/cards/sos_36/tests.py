"""Tests for SOS 36 — Stone Docent."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_36.card_impl import StoneDocent
from benchmarks.sos.workspace.engine.card import ActivatedAbility, CardImpl, Creature
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestStoneDocentProperties:
    """Static card data should match the SOS 36 spec."""

    def test_is_spirit_chimera_creature(self) -> None:
        card = StoneDocent(owner=None)
        assert isinstance(card, Creature)
        assert "Spirit" in card.subtypes
        assert "Chimera" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = StoneDocent(owner=None)
        assert card.name == "Stone Docent"
        assert card.mana_cost == ManaCost.parse("{1}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 1


class TestStoneDocentActivatedAbility:
    """Stone Docent should exile itself from your graveyard for life and surveil."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = StoneDocent(owner=None).get_activated_abilities()
        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_requires_white_mana_and_exiles_this_card_from_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = StoneDocent(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[card])
        ability = card.get_activated_abilities()[0]

        assert ability.cost(game, card) is False
        assert game.get_graveyard(p1).contains(card)

        p1.mana_pool.add(ManaType.WHITE, 1)
        assert ability.cost(game, card) is True
        assert p1.mana_pool.total() == 0
        assert not game.get_graveyard(p1).contains(card)
        assert game.get_exile(p1).contains(card)

    def test_activation_cost_fails_outside_sorcery_speed(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = StoneDocent(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[card])
        ability = card.get_activated_abilities()[0]
        p1.mana_pool.add(ManaType.WHITE, 1)

        assert ability.cost(game, card) is False
        assert p1.mana_pool.total() == 1
        assert game.get_graveyard(p1).contains(card)
        assert not game.get_exile(p1).contains(card)

    def test_effect_gains_two_life_and_may_surveil_the_top_card_into_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom_card = CardImpl(name="Earlier Lesson", owner=p1, controller=p1)
        top_card = CardImpl(name="Latest Lesson", owner=p1, controller=p1)
        game.get_library(p1).add(bottom_card)
        game.get_library(p1).add(top_card)
        p1._script.append(True)
        ability = StoneDocent(owner=p1, controller=p1).get_activated_abilities()[0]

        ability.effect(game)

        assert p1.life == 22
        assert game.get_graveyard(p1).contains(top_card)
        assert game.get_library(p1).top(1) == [bottom_card]

    def test_effect_may_leave_the_surveilled_card_on_top_of_your_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom_card = CardImpl(name="Earlier Lesson", owner=p1, controller=p1)
        top_card = CardImpl(name="Latest Lesson", owner=p1, controller=p1)
        game.get_library(p1).add(bottom_card)
        game.get_library(p1).add(top_card)
        p1._script.append(False)
        ability = StoneDocent(owner=p1, controller=p1).get_activated_abilities()[0]

        ability.effect(game)

        assert p1.life == 22
        assert game.get_graveyard(p1).get_all() == []
        assert game.get_library(p1).get_all() == [bottom_card, top_card]
