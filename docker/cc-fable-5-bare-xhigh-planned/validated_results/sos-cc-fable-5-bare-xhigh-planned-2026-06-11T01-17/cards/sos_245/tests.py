"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state, cast_spell


def _bears(n: int) -> list[Creature]:
    return [Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
            for i in range(n)]


class TestWitherbloomProperties:
    def test_static_data(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert card.base_power == 5 and card.base_toughness == 5
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes


class TestWitherbloomOwnAffinity:
    def test_three_creatures_reduce_to_three_generic(self) -> None:
        """{6}{B}{G} with 3 creatures → {3}{B}{G}."""
        game = create_game()
        card = WitherbloomTheBalancer(owner=None)
        set_board_state(game, 0, battlefield=_bears(3), hand=[card],
                        mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1,
                              ManaType.GREEN: 1})
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.get_battlefield(game.players[0]).contains(card)

    def test_no_creatures_full_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[])
        assert card.cost_reduction(game) == 0

    def test_colored_pips_never_reduced(self) -> None:
        """Even with 10 creatures, {B}{G} must still be paid."""
        game = create_game()
        card = WitherbloomTheBalancer(owner=None)
        set_board_state(game, 0, battlefield=_bears(10), hand=[card],
                        mana={ManaType.COLORLESS: 2})
        try:
            cast_spell(game, 0, "Witherbloom, the Balancer")
            raised = False
        except Exception:
            raised = True
        assert raised, "cast must fail without {B}{G}"

    def test_opponent_creatures_do_not_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 1, battlefield=_bears(4))
        assert card.cost_reduction(game) == 0


class TestWitherbloomGrantsAffinity:
    def test_your_instants_cost_less(self) -> None:
        """Witherbloom + 2 bears = 3 creatures → {4} instant costs {1}."""
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        spell = Instant(name="Big Trick", mana_cost=ManaCost.parse("{4}"))
        set_board_state(game, 0, battlefield=[wb] + _bears(2), hand=[spell],
                        mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Big Trick")
        assert game.get_graveyard(game.players[0]).contains(spell)

    def test_grant_is_generic_only(self) -> None:
        """{1}{U} instant with 3 creatures still needs the {U}."""
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        spell = Instant(name="Blue Trick", mana_cost=ManaCost.parse("{1}{U}"))
        set_board_state(game, 0, battlefield=[wb] + _bears(2), hand=[spell],
                        mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Blue Trick")  # generic reduced to 0, pay {U}
        assert game.get_graveyard(game.players[0]).contains(spell)

    def test_creature_spells_not_granted_affinity(self) -> None:
        """The grant applies to instants/sorceries only, not creatures."""
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        bear = Creature(name="Costly Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{3}"))
        set_board_state(game, 0, battlefield=[wb] + _bears(2), hand=[bear],
                        mana={})
        try:
            cast_spell(game, 0, "Costly Bear")
            raised = False
        except Exception:
            raised = True
        assert raised, "creature spell must not be reduced"
