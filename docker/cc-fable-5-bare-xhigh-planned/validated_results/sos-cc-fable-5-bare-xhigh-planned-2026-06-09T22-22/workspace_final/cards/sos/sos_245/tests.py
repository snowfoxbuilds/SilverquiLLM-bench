"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.casting import get_cost_reduction
from engine.types import Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state, cast_spell


class MarkerSpell(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Marker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 1


def _bears(n):
    return [Creature(name=f"Bear{i}", base_power=2, base_toughness=2) for i in range(n)]


class TestProperties:
    def test_basics(self):
        c = WitherbloomTheBalancer(owner=None)
        assert c.name == "Witherbloom, the Balancer"
        assert c.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert c.base_power == 5 and c.base_toughness == 5
        assert Keyword.FLYING in c.keywords
        assert Keyword.DEATHTOUCH in c.keywords
        assert Supertype.LEGENDARY in c.supertypes


class TestOwnAffinity:
    def test_reduced_by_creatures(self):
        game = create_game()
        p0 = game.players[0]
        set_board_state(game, 0, battlefield=_bears(3),
                        hand=[WitherbloomTheBalancer(owner=None)],
                        mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1})
        # {6}{B}{G} - 3 creatures = {3}{B}{G}.
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert "Witherbloom, the Balancer" in [c.name for c in game.get_battlefield(p0).get_all()]

    def test_no_creatures_no_reduction(self):
        game = create_game()
        p0 = game.players[0]
        w = WitherbloomTheBalancer(owner=p0, controller=p0)
        assert get_cost_reduction(game, w, p0) == 0


class TestGrantedAffinity:
    def test_instant_gets_affinity(self):
        game = create_game()
        p0 = game.players[0]
        w = WitherbloomTheBalancer(owner=None)
        # Witherbloom + 2 bears = 3 creatures controlled.
        set_board_state(game, 0, battlefield=[w] + _bears(2))
        spell = Instant(name="Probe", mana_cost=ManaCost.parse("{3}{U}"))
        spell.controller = p0
        # {3}{U} reduced by 3 → {U}. Generic fully reduced.
        assert get_cost_reduction(game, spell, p0) == 3

    def test_instant_castable_with_reduction(self):
        game = create_game()
        p0 = game.players[0]
        w = WitherbloomTheBalancer(owner=None)
        set_board_state(game, 0, battlefield=[w] + _bears(2),
                        hand=[MarkerSpell(owner=None)],
                        mana={ManaType.BLUE: 1})
        # {3}{U} - 3 = {U}; only {U} available → still castable.
        cast_spell(game, 0, "Marker")
        assert p0.life == 21

    def test_no_reduction_when_witherbloom_absent(self):
        game = create_game()
        p0 = game.players[0]
        spell = Instant(name="Probe", mana_cost=ManaCost.parse("{3}{U}"))
        spell.controller = p0
        set_board_state(game, 0, battlefield=_bears(2))
        assert get_cost_reduction(game, spell, p0) == 0
