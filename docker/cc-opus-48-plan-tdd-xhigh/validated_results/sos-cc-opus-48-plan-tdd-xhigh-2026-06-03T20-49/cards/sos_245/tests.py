"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, cast_spell, set_board_state


def _bear(name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2)


class TestProperties:
    def test_is_creature(self):
        assert isinstance(WitherbloomTheBalancer(owner=None), Creature)

    def test_name(self):
        assert WitherbloomTheBalancer(owner=None).name == "Witherbloom, the Balancer"

    def test_mana_cost(self):
        assert WitherbloomTheBalancer(owner=None).mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_power_toughness(self):
        c = WitherbloomTheBalancer(owner=None)
        assert c.base_power == 5
        assert c.base_toughness == 5

    def test_keywords(self):
        kw = WitherbloomTheBalancer(owner=None).keywords
        assert Keyword.FLYING in kw
        assert Keyword.DEATHTOUCH in kw

    def test_legendary(self):
        assert Supertype.LEGENDARY in WitherbloomTheBalancer(owner=None).supertypes


class TestSelfAffinity:
    def test_costs_one_less_per_creature_you_control(self):
        game = create_game()
        set_board_state(game, 0, hand=[WitherbloomTheBalancer(owner=None)],
                        battlefield=[_bear("A"), _bear("B")],
                        mana={ManaType.COLORLESS: 4, ManaType.BLACK: 1,
                              ManaType.GREEN: 1})
        # {6}{B}{G} reduced by 2 creatures -> {4}{B}{G}; exactly payable.
        cast_spell(game, 0, "Witherbloom, the Balancer")
        bf_names = [getattr(o, "name", None)
                    for o in game.players[0].zones[Zone.BATTLEFIELD].get_all()]
        assert "Witherbloom, the Balancer" in bf_names

    def test_no_creatures_means_full_cost(self):
        game = create_game()
        set_board_state(game, 0, hand=[WitherbloomTheBalancer(owner=None)],
                        mana={ManaType.COLORLESS: 4, ManaType.BLACK: 1,
                              ManaType.GREEN: 1})
        # No creatures -> full {6}{B}{G}; 6 mana insufficient.
        try:
            cast_spell(game, 0, "Witherbloom, the Balancer")
            assert False, "should not have been castable"
        except Exception:
            pass


class TestGrantedAffinity:
    def test_three_creatures_reduces_by_three(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        spell = Sorcery(name="Filler Spell", mana_cost=ManaCost.parse("{5}"))
        set_board_state(game, 0, hand=[spell],
                        battlefield=[wb, _bear("A"), _bear("B")],
                        mana={ManaType.COLORLESS: 2})
        # 3 creatures -> {5} reduced to {2}; exactly payable.
        cast_spell(game, 0, "Filler Spell")
        gy_names = [getattr(o, "name", None)
                    for o in game.players[0].zones[Zone.GRAVEYARD].get_all()]
        assert "Filler Spell" in gy_names

    def test_no_witherbloom_no_reduction(self):
        game = create_game()
        spell = Sorcery(name="Filler Spell", mana_cost=ManaCost.parse("{5}"))
        set_board_state(game, 0, hand=[spell],
                        battlefield=[_bear("A"), _bear("B"), _bear("C")],
                        mana={ManaType.COLORLESS: 2})
        # No Witherbloom granting affinity -> full {5}; 2 mana insufficient.
        try:
            cast_spell(game, 0, "Filler Spell")
            assert False
        except Exception:
            pass

    def test_creature_spell_not_granted_affinity(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        big = Creature(name="Big Beast", mana_cost=ManaCost.parse("{5}"),
                       base_power=4, base_toughness=4)
        set_board_state(game, 0, hand=[big],
                        battlefield=[wb, _bear("A"), _bear("B")],
                        mana={ManaType.COLORLESS: 2})
        # Granted affinity only applies to instant/sorcery, not creatures.
        try:
            cast_spell(game, 0, "Big Beast")
            assert False
        except Exception:
            pass
