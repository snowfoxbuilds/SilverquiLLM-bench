"""Tests for Witherbloom, the Balancer (sos_245)."""

from __future__ import annotations

import pytest
from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class TestWitherbloomProperties:
    """Static card properties."""

    def test_name(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"

    def test_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert isinstance(card, Creature)

    def test_power_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_mana_cost(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_has_flying(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING & card.keywords

    def test_has_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.DEATHTOUCH & card.keywords

    def test_is_legendary(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


class TestWitherbloomAffinity:
    """Affinity for creatures: reduce own cost by 1 per creature you control."""

    def test_cost_reduction_zero_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_cost_reduction_one_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear])
        assert card.cost_reduction(game) == 1

    def test_cost_reduction_three_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Creature{i}", base_power=1, base_toughness=1,
                     owner=p1, controller=p1)
            for i in range(3)
        ]
        set_board_state(game, 0, battlefield=creatures)
        assert card.cost_reduction(game) == 3

    def test_opponent_creatures_do_not_count(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        opp_bear = Creature(name="OppBear", base_power=2, base_toughness=2,
                            owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[opp_bear])
        assert card.cost_reduction(game) == 0


class TestWitherbloomGrantsAffinityToSpells:
    """Instant and sorcery spells you cast have affinity for creatures."""

    def test_global_reducer_registered_on_etb(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        assert len(getattr(game, "_global_cost_reducers", [])) >= 1

    def test_instant_gets_affinity_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[witherbloom])
        witherbloom.register_triggers(game)

        # Give p1 3 creatures on battlefield (includes witherbloom)
        bear1 = Creature(name="Bear1", base_power=2, base_toughness=2,
                         owner=p1, controller=p1)
        bear2 = Creature(name="Bear2", base_power=2, base_toughness=2,
                         owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[witherbloom, bear1, bear2])

        # Instant should get 3 reduction (witherbloom + 2 bears)
        spell = Instant(name="Shock", owner=p1, controller=p1)
        from engine.casting import get_cost_reduction
        reduction = sum(
            fn(game, spell, p1)
            for fn in game._global_cost_reducers
        )
        assert reduction == 3  # 3 creatures on battlefield

    def test_non_instant_sorcery_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[witherbloom, bear])
        witherbloom.register_triggers(game)

        # Creature spell should not get the reduction
        creature = Creature(name="TestCreature", base_power=1, base_toughness=1)
        for fn in game._global_cost_reducers:
            reduction = fn(game, creature, p1)
            assert reduction == 0

    def test_opponent_instant_no_reduction(self) -> None:
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[witherbloom, bear])
        witherbloom.register_triggers(game)

        # Opponent's spell should not get reduction
        opp_spell = Instant(name="OppShock", owner=p2, controller=p2)
        for fn in game._global_cost_reducers:
            reduction = fn(game, opp_spell, p2)
            assert reduction == 0
