"""Tests for Witherbloom, the Balancer (SOS 245)."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


def _creatures(player, n):
    return [Creature(name=f"C{i}", base_power=1, base_toughness=1,
                     owner=player, controller=player) for i in range(n)]


class TestProperties:
    def test_static_data(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert CardType.CREATURE in card.card_types
        assert card.base_power == 5
        assert card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes


class TestSelfAffinity:
    def test_cost_reduction_counts_creatures(self) -> None:
        game = create_game()
        p1, _ = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        others = _creatures(p1, 3)
        set_board_state(game, 0, battlefield=[card, *others])
        # 4 creatures total (Witherbloom counts itself once on battlefield).
        assert card.cost_reduction(game) == 4

    def test_cost_reduction_no_creatures(self) -> None:
        game = create_game()
        p1, _ = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0


class TestGrantedAffinity:
    def test_grants_to_instant_same_controller(self) -> None:
        game = create_game()
        p1, _ = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card, *_creatures(p1, 2)])
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{5}"),
                       owner=p1, controller=p1)
        assert card.grant_cost_reduction(game, bolt) == 3

    def test_no_grant_to_creature_spell(self) -> None:
        game = create_game()
        p1, _ = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        creature_spell = Creature(name="Beast", base_power=2, base_toughness=2,
                                  owner=p1, controller=p1)
        assert card.grant_cost_reduction(game, creature_spell) == 0

    def test_no_grant_to_opponent_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card, *_creatures(p1, 2)])
        opp_spell = Sorcery(name="OppSpell", mana_cost=ManaCost.parse("{5}"),
                            owner=p2, controller=p2)
        assert card.grant_cost_reduction(game, opp_spell) == 0


class TestGapDIntegration:
    def test_get_cost_reduction_applies_granted(self) -> None:
        game = create_game()
        p1, _ = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card, *_creatures(p1, 2)])
        sorc = Sorcery(name="BigSorc", mana_cost=ManaCost.parse("{5}"),
                       owner=p1, controller=p1)
        # 3 creatures -> {5} generic reduced by 3.
        assert get_cost_reduction(game, sorc, p1) == 3

    def test_get_cost_reduction_clamped_to_generic(self) -> None:
        game = create_game()
        p1, _ = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card, *_creatures(p1, 5)])
        sorc = Sorcery(name="Tiny", mana_cost=ManaCost.parse("{2}"),
                       owner=p1, controller=p1)
        # 6 creatures but only 2 generic in cost.
        assert get_cost_reduction(game, sorc, p1) == 2
