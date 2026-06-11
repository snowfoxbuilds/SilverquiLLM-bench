"""Tests for SOS 37 — Summoned Dromedary."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_37.card_impl import SummonedDromedary
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestSummonedDromedaryProperties:
    """Static card data should match the SOS 37 spec."""

    def test_is_spirit_camel_creature_with_vigilance(self) -> None:
        card = SummonedDromedary(owner=None)
        assert isinstance(card, Creature)
        assert "Spirit" in card.subtypes
        assert "Camel" in card.subtypes
        assert Keyword.VIGILANCE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = SummonedDromedary(owner=None)
        assert card.name == "Summoned Dromedary"
        assert card.mana_cost == ManaCost.parse("{3}{W}")
        assert card.base_power == 4
        assert card.base_toughness == 3


class TestSummonedDromedaryActivatedAbility:
    """Summoned Dromedary should return itself from graveyard to hand at sorcery speed."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = SummonedDromedary(owner=None).get_activated_abilities()
        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_requires_one_and_white_and_leaves_the_card_in_your_graveyard_until_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = SummonedDromedary(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[card])
        ability = card.get_activated_abilities()[0]

        p1.mana_pool.add(ManaType.WHITE, 1)
        assert ability.cost(game, card) is False
        assert game.get_graveyard(p1).contains(card)

        p1.mana_pool.empty()
        p1.mana_pool.add(ManaType.WHITE, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        assert ability.cost(game, card) is True
        assert p1.mana_pool.total() == 0
        assert game.get_graveyard(p1).contains(card)
        assert not game.get_hand(p1).contains(card)

    def test_activation_cost_fails_outside_sorcery_speed(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = SummonedDromedary(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[card])
        ability = card.get_activated_abilities()[0]
        p1.mana_pool.add(ManaType.WHITE, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 1)

        assert ability.cost(game, card) is False
        assert p1.mana_pool.total() == 2
        assert game.get_graveyard(p1).contains(card)
        assert not game.get_hand(p1).contains(card)

    def test_effect_returns_this_card_from_your_graveyard_to_your_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SummonedDromedary(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[card])
        ability = card.get_activated_abilities()[0]

        ability.effect(game)

        assert not game.get_graveyard(p1).contains(card)
        assert game.get_hand(p1).contains(card)
