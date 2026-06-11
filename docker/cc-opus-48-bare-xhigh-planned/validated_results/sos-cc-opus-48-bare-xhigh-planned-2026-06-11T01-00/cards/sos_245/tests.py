"""Tests for Witherbloom, the Balancer (sos_245)."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from test_utils import cast_spell, create_game, set_board_state


def _bears(n):
    return [Creature(name=f"Bear{i}", base_power=2, base_toughness=2) for i in range(n)]


class TestProperties:
    def test_static(self):
        c = WitherbloomTheBalancer(owner=None)
        assert c.name == "Witherbloom, the Balancer"
        assert c.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert c.base_power == 5 and c.base_toughness == 5
        assert Keyword.FLYING in c.keywords
        assert Keyword.DEATHTOUCH in c.keywords
        assert Supertype.LEGENDARY in c.supertypes


class TestOwnAffinity:
    def test_affinity_reduces_own_cost(self):
        """3 creatures you control → {6}{B}{G} costs {3}{B}{G}."""
        game = create_game()
        w = WitherbloomTheBalancer(owner=None)
        set_board_state(game, 0, battlefield=_bears(3), hand=[w],
                        mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1,
                              ManaType.GREEN: 1})
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.get_battlefield(game.players[0]).contains(w)

    def test_no_creatures_no_reduction(self):
        """0 creatures → full {6}{B}{G}; 5 generic mana is insufficient."""
        game = create_game()
        w = WitherbloomTheBalancer(owner=None)
        set_board_state(game, 0, battlefield=[], hand=[w],
                        mana={ManaType.COLORLESS: 5, ManaType.BLACK: 1,
                              ManaType.GREEN: 1})
        with pytest.raises(Exception):
            cast_spell(game, 0, "Witherbloom, the Balancer")

    def test_affinity_only_reduces_generic(self):
        """With 8 creatures, generic clamps to 0 but {B}{G} pips remain."""
        game = create_game()
        w = WitherbloomTheBalancer(owner=None)
        set_board_state(game, 0, battlefield=_bears(8), hand=[w],
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1})
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.get_battlefield(game.players[0]).contains(w)


class TestGrantedAffinity:
    def test_grants_affinity_to_instant(self):
        """Witherbloom + 2 bears (3 creatures) → an instant {4} costs {1}."""
        game = create_game()
        w = WitherbloomTheBalancer(owner=None)
        spell = Instant(name="Zap", mana_cost=ManaCost.parse("{4}"))
        set_board_state(game, 0, battlefield=[w] + _bears(2), hand=[spell],
                        mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Zap")
        assert game.get_graveyard(game.players[0]).contains(spell)

    def test_grants_affinity_to_sorcery(self):
        game = create_game()
        w = WitherbloomTheBalancer(owner=None)
        spell = Sorcery(name="Plow", mana_cost=ManaCost.parse("{3}"))
        set_board_state(game, 0, battlefield=[w] + _bears(2), hand=[spell],
                        mana={ManaType.COLORLESS: 0})
        cast_spell(game, 0, "Plow")  # 3 creatures → {3} reduced to {0}
        assert game.get_graveyard(game.players[0]).contains(spell)

    def test_does_not_grant_affinity_to_creature_spell(self):
        """The grant is for instant/sorcery only — a creature spell pays full."""
        game = create_game()
        w = WitherbloomTheBalancer(owner=None)
        big = Creature(name="Ogre", mana_cost=ManaCost.parse("{4}"),
                       base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[w] + _bears(2), hand=[big],
                        mana={ManaType.COLORLESS: 1})
        with pytest.raises(Exception):
            cast_spell(game, 0, "Ogre")
