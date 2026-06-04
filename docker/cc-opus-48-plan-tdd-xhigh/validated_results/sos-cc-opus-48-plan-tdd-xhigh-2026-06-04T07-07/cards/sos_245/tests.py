"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Sorcery
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


def _vanilla(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2,
                    mana_cost=ManaCost.parse("{1}{G}"))


class TestWitherbloomProperties:
    def test_name(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_power_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_legendary(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_keywords(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords


class TestWitherbloomAffinitySelf:
    """Affinity for creatures reduces Witherbloom's own generic cost."""

    def test_two_creatures_reduce_cost_by_two(self) -> None:
        # {6}{B}{G} with 2 creatures -> {4}{B}{G}; give exactly that mana.
        wb = WitherbloomTheBalancer(owner=None)
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[_vanilla("Bear A"), _vanilla("Bear B")],
                        hand=[wb])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 4, ManaType.BLACK: 1,
                                       ManaType.GREEN: 1})
        from test_utils import cast_spell
        cast_spell(game, 0, "Witherbloom, the Balancer")
        bf = game.get_battlefield(p1).get_all()
        assert wb in bf
        assert p1.mana_pool.total() == 0

    def test_insufficient_mana_with_fewer_creatures_fails(self) -> None:
        # Only 1 creature -> {5}{B}{G}; 6 total mana is not enough.
        from test_utils import TestSetupError, cast_spell
        wb = WitherbloomTheBalancer(owner=None)
        game = create_game()
        set_board_state(game, 0, battlefield=[_vanilla("Bear A")], hand=[wb])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 4, ManaType.BLACK: 1,
                                       ManaType.GREEN: 1})
        try:
            cast_spell(game, 0, "Witherbloom, the Balancer")
            raised = False
        except TestSetupError:
            raised = True
        assert raised
        assert wb in game.get_hand(game.players[0]).get_all()


class TestWitherbloomExternalAffinity:
    """Your instant/sorcery spells gain affinity for creatures."""

    def test_sorcery_cost_reduced_by_creature_count(self) -> None:
        from test_utils import cast_spell
        wb = WitherbloomTheBalancer(owner=None)
        spell = Sorcery(name="Test Spell", mana_cost=ManaCost.parse("{4}"))
        game = create_game()
        p1 = game.players[0]
        # Witherbloom + 1 vanilla = 2 creatures -> {4} reduced to {2}.
        set_board_state(game, 0, battlefield=[wb, _vanilla("Bear A")], hand=[spell])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Test Spell")
        assert spell in game.get_graveyard(p1).get_all()
        assert p1.mana_pool.total() == 0

    def test_no_reduction_for_noncreature_spells(self) -> None:
        # An I/S reduction applies only to I/S; a creature spell is unaffected
        # by *external* affinity (it would use its own cost_reduction instead).
        from test_utils import TestSetupError, cast_spell
        wb = WitherbloomTheBalancer(owner=None)
        other = Creature(name="Big Guy", base_power=3, base_toughness=3,
                         mana_cost=ManaCost.parse("{4}"))
        game = create_game()
        # Witherbloom on battlefield, but Big Guy is a creature: external
        # affinity must NOT reduce it.  With only {2} it cannot be cast.
        set_board_state(game, 0, battlefield=[wb], hand=[other])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        try:
            cast_spell(game, 0, "Big Guy")
            raised = False
        except TestSetupError:
            raised = True
        assert raised
