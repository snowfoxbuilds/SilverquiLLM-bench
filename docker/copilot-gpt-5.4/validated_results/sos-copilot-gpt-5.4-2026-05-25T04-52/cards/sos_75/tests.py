"""Tests for SOS 75 — Burrog Banemaker."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_75.card_impl import BurrogBanemaker
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.mana import ManaPool
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestBurrogBanemakerProperties:
    """Static card data should match the SOS 75 spec."""

    def test_is_frog_warlock_with_deathtouch(self) -> None:
        card = BurrogBanemaker(owner=None)
        assert isinstance(card, Creature)
        assert "Frog" in card.subtypes
        assert "Warlock" in card.subtypes
        assert Keyword.DEATHTOUCH in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = BurrogBanemaker(owner=None)
        assert card.name == "Burrog Banemaker"
        assert card.mana_cost == ManaCost.parse("{B}")
        assert card.base_power == 1
        assert card.base_toughness == 1


class TestBurrogBanemakerActivatedAbility:
    """Burrog Banemaker should pump itself for {1}{B} until end of turn."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = BurrogBanemaker(owner=None).get_activated_abilities()
        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_requires_one_generic_and_one_black_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BurrogBanemaker(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_activated_abilities()[0]

        p1.mana_pool = ManaPool()
        p1.mana_pool.add(ManaType.BLACK, 1)
        assert ability.cost(game, card) is False
        assert p1.mana_pool.total() == 1

        p1.mana_pool = ManaPool()
        p1.mana_pool.add(ManaType.BLACK, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        assert ability.cost(game, card) is True
        assert p1.mana_pool.total() == 0

    def test_effect_gives_this_creature_plus_one_plus_one_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BurrogBanemaker(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_activated_abilities()[0]

        ability.effect(game)

        assert card.power == 2
        assert card.toughness == 2

    def test_pump_effect_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BurrogBanemaker(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_activated_abilities()[0]

        ability.effect(game)
        assert card.power == 2
        assert card.toughness == 2

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert card.power == 1
        assert card.toughness == 1
