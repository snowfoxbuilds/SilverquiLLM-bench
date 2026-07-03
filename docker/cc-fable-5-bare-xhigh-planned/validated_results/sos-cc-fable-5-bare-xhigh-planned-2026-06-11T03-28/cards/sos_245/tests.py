"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Supertype
from test_utils import TestSetupError, create_game, set_board_state, cast_spell


def _bears(n: int) -> list[Creature]:
    return [
        Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
        for i in range(n)
    ]


class TestWitherbloomProperties:
    def test_static_data(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert card.base_power == 5
        assert card.base_toughness == 5
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes


class TestWitherbloomOwnAffinity:
    def test_costs_one_less_per_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1)
        set_board_state(game, 0, battlefield=_bears(3), hand=[wb],
                        mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1,
                              ManaType.GREEN: 1})
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.get_battlefield(p1).contains(wb)

    def test_no_creatures_full_price(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1)
        set_board_state(game, 0, battlefield=[], hand=[wb],
                        mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1,
                              ManaType.GREEN: 1})
        try:
            cast_spell(game, 0, "Witherbloom, the Balancer")
            cast_ok = True
        except TestSetupError:
            cast_ok = False
        assert not cast_ok
        assert game.get_hand(p1).contains(wb)

    def test_reduction_never_touches_colored_pips(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1)
        # 20 creatures: generic clamps to 0 but {B}{G} must still be paid.
        set_board_state(game, 0, battlefield=_bears(20), hand=[wb],
                        mana={ManaType.COLORLESS: 2})
        try:
            cast_spell(game, 0, "Witherbloom, the Balancer")
            cast_ok = True
        except TestSetupError:
            cast_ok = False
        assert not cast_ok


class TestWitherbloomGrantsAffinity:
    def test_your_instants_have_affinity_for_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1)
        spell = Instant(name="Probe Bolt", mana_cost=ManaCost.parse("{3}{U}"))
        # Witherbloom + 2 bears = 3 creatures → {3} generic fully reduced.
        set_board_state(game, 0, battlefield=[wb] + _bears(2), hand=[spell],
                        mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Probe Bolt")
        assert game.get_graveyard(p1).contains(spell)

    def test_opponents_spells_unaffected(self) -> None:
        game = create_game()
        p2 = game.players[1]
        wb = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[wb] + _bears(2))
        spell = Instant(name="Probe Bolt", mana_cost=ManaCost.parse("{3}{U}"))
        set_board_state(game, 1, hand=[spell], mana={ManaType.BLUE: 1})
        try:
            cast_spell(game, 1, "Probe Bolt")
            cast_ok = True
        except TestSetupError:
            cast_ok = False
        assert not cast_ok
        assert game.get_hand(p2).contains(spell)

    def test_grant_does_not_apply_to_creature_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1)
        bear = Creature(name="Hand Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{2}"))
        set_board_state(game, 0, battlefield=[wb] + _bears(2), hand=[bear],
                        mana={})
        try:
            cast_spell(game, 0, "Hand Bear")
            cast_ok = True
        except TestSetupError:
            cast_ok = False
        assert not cast_ok
