"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state, cast_spell


def _vanilla(n):
    return [Creature(name=f"Bear{i}", base_power=2, base_toughness=2) for i in range(n)]


class _SmallSpell(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Small Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        pass


class TestProperties:
    def test_static(self):
        c = WitherbloomTheBalancer(owner=None)
        assert c.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert Keyword.FLYING in c.keywords
        assert Keyword.DEATHTOUCH in c.keywords
        assert Supertype.LEGENDARY in c.supertypes
        assert (c.base_power, c.base_toughness) == (5, 5)


class TestOwnAffinity:
    def test_reduced_by_creatures(self):
        game = create_game()
        p0 = game.players[0]
        set_board_state(game, 0, battlefield=_vanilla(3),
                        hand=[WitherbloomTheBalancer(owner=None)],
                        mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1})
        # {6}{B}{G} - 3 = {3}{B}{G} = 5 mana, exactly provided.
        cast_spell(game, 0, "Witherbloom, the Balancer")
        bf = [getattr(c, "name", "") for c in game.get_battlefield(p0).get_all()]
        assert "Witherbloom, the Balancer" in bf

    def test_no_creatures_no_reduction(self):
        game = create_game()
        p0 = game.players[0]
        set_board_state(game, 0, battlefield=[],
                        hand=[WitherbloomTheBalancer(owner=None)],
                        mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1})
        try:
            cast_spell(game, 0, "Witherbloom, the Balancer")
        except Exception:
            pass
        # 5 mana < 8 → still in hand.
        hand = [getattr(c, "name", "") for c in game.get_hand(p0).get_all()]
        assert "Witherbloom, the Balancer" in hand


class TestGrantedAffinity:
    def test_instant_gets_affinity(self):
        game = create_game()
        p0 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p0, controller=p0)
        # Witherbloom + 2 vanilla = 3 creatures controlled.
        set_board_state(game, 0, battlefield=[wb] + _vanilla(2),
                        hand=[_SmallSpell()],
                        mana={ManaType.COLORLESS: 1, ManaType.BLUE: 1})
        # {4}{U} - 3 = {1}{U} = 2 mana, exactly provided.
        cast_spell(game, 0, "Small Spell")
        assert p0.zones[Zone.GRAVEYARD].contains(
            next(c for c in p0.zones[Zone.GRAVEYARD].get_all()
                 if getattr(c, "name", "") == "Small Spell")
        )

    def test_instant_no_reduction_without_witherbloom(self):
        game = create_game()
        p0 = game.players[0]
        set_board_state(game, 0, battlefield=_vanilla(2),
                        hand=[_SmallSpell()],
                        mana={ManaType.COLORLESS: 1, ManaType.BLUE: 1})
        # No Witherbloom granting affinity → vanilla creatures don't reduce.
        try:
            cast_spell(game, 0, "Small Spell")
        except Exception:
            pass
        hand = [getattr(c, "name", "") for c in game.get_hand(p0).get_all()]
        assert "Small Spell" in hand
