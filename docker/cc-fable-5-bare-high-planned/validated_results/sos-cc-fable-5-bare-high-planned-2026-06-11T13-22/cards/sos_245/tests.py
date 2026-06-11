"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


class TestSelfAffinity:
    def test_costs_one_less_per_creature_you_control(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        bears = [
            Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
            for i in range(4)
        ]
        set_board_state(
            game, 0, battlefield=bears, hand=[wb],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 2},
        )
        # {6}{B}{G} with 4 creatures -> {2}{B}{G}
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(wb)
        assert game.players[0].mana_pool.total() == 0

    def test_no_creatures_no_reduction(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        set_board_state(
            game, 0, hand=[wb],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 2},
        )
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")

    def test_colored_pips_never_reduced(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        bears = [
            Creature(name=f"Bear {i}", base_power=1, base_toughness=1)
            for i in range(10)
        ]
        # 10 creatures cannot pay for the {B}{G} pips.
        set_board_state(game, 0, battlefield=bears, hand=[wb],
                        mana={ManaType.COLORLESS: 2})
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")

    def test_keywords(self):
        wb = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in wb.keywords
        assert Keyword.DEATHTOUCH in wb.keywords


class TestGrantedAffinity:
    def test_instant_costs_less_with_witherbloom_on_battlefield(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        bears = [
            Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
            for i in range(3)
        ]
        inst = Instant(name="Big Trick", mana_cost=ManaCost.parse("{3}{U}"))
        set_board_state(
            game, 0, battlefield=[wb] + bears, hand=[inst],
            mana={ManaType.BLUE: 1},
        )
        # Witherbloom counts itself + 3 bears = 4 creatures -> generic 3 -> 0.
        cast_spell(game, 0, "Big Trick")
        assert game.players[0].zones[Zone.GRAVEYARD].contains(inst)

    def test_non_instant_sorcery_not_reduced(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        creature_spell = Creature(
            name="Giant", mana_cost=ManaCost.parse("{4}"),
            base_power=4, base_toughness=4,
        )
        set_board_state(game, 0, battlefield=[wb], hand=[creature_spell],
                        mana={ManaType.COLORLESS: 3})
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Giant")

    def test_opponents_spells_not_reduced(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        sorc = Sorcery(name="Op Spell", mana_cost=ManaCost.parse("{2}{R}"))
        set_board_state(game, 0, battlefield=[wb])
        set_board_state(game, 1, hand=[sorc], mana={ManaType.RED: 1})
        with pytest.raises(TestSetupError):
            cast_spell(game, 1, "Op Spell")
