"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.casting import get_cost_reduction
from engine.types import Keyword, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


class TestProperties:
    def test_static_data(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.base_power == 5 and card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords


class TestOwnAffinity:
    def test_costs_one_less_per_creature_you_control(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[_bear("B1"), _bear("B2"), _bear("B3")])
        game.get_hand(p1).add(card)
        card.owner = p1
        card.controller = p1
        assert get_cost_reduction(game, card, p1) == 3

        # End to end: pay {3}{B}{G} instead of {6}{B}{G}.
        set_board_state(
            game, 0,
            battlefield=[_bear("B1"), _bear("B2"), _bear("B3")],
            hand=[card],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 3},
        )
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.get_battlefield(p1).contains(card)
        assert p1.mana_pool.total() == 0

    def test_no_creatures_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[], hand=[card])
        assert get_cost_reduction(game, card, p1) == 0


class TestGrantedAffinity:
    def test_your_instants_cost_less(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer()
        # Witherbloom itself is a creature you control → counts itself.
        set_board_state(game, 0, battlefield=[wb, _bear("B1")])
        trick = Instant(name="Trick", mana_cost=ManaCost.parse("{3}{U}"))
        game.get_hand(p1).add(trick)
        trick.owner = p1
        trick.controller = p1
        assert get_cost_reduction(game, trick, p1) == 2

        # End to end: {3}{U} costs {1}{U}.
        set_board_state(game, 0, hand=[trick],
                        mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Trick")
        assert game.get_graveyard(p1).contains(trick)
        assert p1.mana_pool.total() == 0

    def test_opponent_spells_unaffected(self) -> None:
        game = create_game()
        p2 = game.players[1]
        wb = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[wb, _bear("B1")])
        opp_trick = Instant(name="Opp Trick", mana_cost=ManaCost.parse("{3}{U}"))
        game.get_hand(p2).add(opp_trick)
        opp_trick.owner = p2
        opp_trick.controller = p2
        assert get_cost_reduction(game, opp_trick, p2) == 0

    def test_creatures_unaffected_by_grant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[wb])
        bear = Creature(name="Costly Bear", mana_cost=ManaCost.parse("{3}{G}"),
                        base_power=2, base_toughness=2)
        game.get_hand(p1).add(bear)
        bear.owner = p1
        bear.controller = p1
        # Grant applies only to instants/sorceries.
        assert get_cost_reduction(game, bear, p1) == 0
