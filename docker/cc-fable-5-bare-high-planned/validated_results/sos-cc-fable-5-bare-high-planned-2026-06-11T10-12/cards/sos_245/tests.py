"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import TestSetupError, create_game, cast_spell, set_board_state


class TestOwnAffinity:
    def test_costs_one_less_per_creature_you_control(self):
        """With 4 creatures, {6}{B}{G} becomes {2}{B}{G}."""
        game = create_game()
        p1 = game.players[0]
        crew = [Creature(name=f"C{i}", base_power=1, base_toughness=1) for i in range(4)]
        wb = WitherbloomTheBalancer(owner=p1)
        set_board_state(
            game, 0, battlefield=crew, hand=[wb],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 2},
        )
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.get_battlefield(p1).contains(wb)
        assert p1.mana_pool.total() == 0

    def test_no_creatures_full_price(self):
        """No creatures: full {6}{B}{G} required; 7 mana is not enough."""
        game = create_game()
        wb = WitherbloomTheBalancer(owner=game.players[0])
        set_board_state(
            game, 0, hand=[wb],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 5},
        )
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")

    def test_colored_pips_never_reduced(self):
        """Even with 10 creatures, {B}{G} must still be paid."""
        game = create_game()
        crew = [Creature(name=f"C{i}", base_power=1, base_toughness=1) for i in range(10)]
        wb = WitherbloomTheBalancer(owner=game.players[0])
        set_board_state(game, 0, battlefield=crew, hand=[wb],
                        mana={ManaType.COLORLESS: 2})
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")

    def test_keywords(self):
        wb = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in wb.keywords
        assert Keyword.DEATHTOUCH in wb.keywords


class TestGrantedAffinity:
    def test_your_instants_get_affinity_for_creatures(self):
        """With Witherbloom + 2 other creatures out (3 creatures total),
        a {3}{U} instant costs just {U}."""
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1)
        crew = [Creature(name=f"C{i}", base_power=1, base_toughness=1) for i in range(2)]
        spell = Instant(name="Probe", mana_cost=ManaCost.parse("{3}{U}"))
        set_board_state(game, 0, battlefield=[wb] + crew, hand=[spell],
                        mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Probe")
        assert p1.zones[Zone.GRAVEYARD].contains(spell)
        assert p1.mana_pool.total() == 0

    def test_opponent_spells_not_reduced(self):
        """Witherbloom only grants affinity to its controller's spells."""
        game = create_game()
        p1, p2 = game.players
        wb = WitherbloomTheBalancer(owner=p1)
        crew = [Creature(name=f"C{i}", base_power=1, base_toughness=1) for i in range(3)]
        set_board_state(game, 0, battlefield=[wb] + crew)
        spell = Instant(name="Opp Probe", mana_cost=ManaCost.parse("{2}{U}"))
        set_board_state(game, 1, hand=[spell], mana={ManaType.BLUE: 1})
        with pytest.raises(TestSetupError):
            cast_spell(game, 1, "Opp Probe")

    def test_creature_spells_not_reduced(self):
        """The grant applies to instants/sorceries only, not creature spells."""
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1)
        set_board_state(game, 0, battlefield=[wb],
                        mana={ManaType.COLORLESS: 1})
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{2}"))
        p1.zones[Zone.HAND].add(bear)
        bear.owner = bear.controller = p1
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Bear")
