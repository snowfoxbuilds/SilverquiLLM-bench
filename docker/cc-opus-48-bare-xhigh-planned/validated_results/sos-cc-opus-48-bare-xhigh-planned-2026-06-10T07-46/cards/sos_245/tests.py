"""Tests for SOS 245 — Witherbloom, the Balancer (affinity + E3 grant)."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state, cast_spell


def _bear(name: str) -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


class TestProperties:
    def test_static_data(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.base_power == 5 and card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes


class TestSelfAffinity:
    def test_three_creatures_reduce_generic_by_three(self) -> None:
        """{6}{B}{G} with 3 creatures you control → {3}{B}{G}."""
        game = create_game()
        p0 = game.players[0]
        card = WitherbloomTheBalancer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[_bear("A"), _bear("B"), _bear("C")],
                        hand=[card],
                        mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1})
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.get_battlefield(p0).contains(card)

    def test_no_creatures_no_reduction(self) -> None:
        """0 creatures → full {6}{B}{G}; 5 mana is insufficient."""
        from test_utils import TestSetupError

        game = create_game()
        p0 = game.players[0]
        card = WitherbloomTheBalancer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[], hand=[card],
                        mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1})
        try:
            cast_spell(game, 0, "Witherbloom, the Balancer")
            assert False, "should not be castable"
        except TestSetupError:
            pass
        assert game.get_hand(p0).contains(card)


class TestGrantedAffinity:
    def test_instant_gets_affinity_from_witherbloom(self) -> None:
        """Witherbloom + 2 bears = 3 creatures → an instant {3}{U} → {U}."""
        game = create_game()
        p0 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p0, controller=p0)
        probe = Instant(name="Probe", mana_cost=ManaCost.parse("{3}{U}"))
        set_board_state(game, 0, battlefield=[wb, _bear("A"), _bear("B")],
                        hand=[probe], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Probe")
        assert game.get_graveyard(p0).contains(probe)

    def test_grant_only_helps_instants_and_sorceries(self) -> None:
        """A creature spell does NOT get the granted affinity (E3 is i/s only)."""
        from test_utils import TestSetupError

        game = create_game()
        p0 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p0, controller=p0)
        # A {3} creature with Witherbloom + 2 bears out: if affinity applied it
        # would be free, but creatures don't get the granted affinity.
        creature_spell = Creature(name="BigGuy", mana_cost=ManaCost.parse("{3}"),
                                  base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[wb, _bear("A"), _bear("B")],
                        hand=[creature_spell], mana={})
        try:
            cast_spell(game, 0, "BigGuy")
            assert False, "creature should not get granted affinity"
        except TestSetupError:
            pass
        assert game.get_hand(p0).contains(creature_spell)

    def test_grant_only_for_controllers_spells(self) -> None:
        """Opponent's instant is not reduced by your Witherbloom."""
        from test_utils import TestSetupError

        game = create_game()
        p0, p1 = game.players
        wb = WitherbloomTheBalancer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[wb, _bear("A"), _bear("B")])
        opp_instant = Instant(name="OppProbe", mana_cost=ManaCost.parse("{3}{U}"))
        set_board_state(game, 1, hand=[opp_instant], mana={ManaType.BLUE: 1})
        try:
            cast_spell(game, 1, "OppProbe")
            assert False, "opponent's spell should not get your affinity"
        except TestSetupError:
            pass
        assert game.get_hand(p1).contains(opp_instant)
