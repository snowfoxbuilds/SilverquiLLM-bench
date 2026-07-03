"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


class TestWitherbloomStatics:
    def test_card_data(self):
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.base_power == 5 and card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords


class TestWitherbloomOwnAffinity:
    def test_costs_one_less_per_creature_you_control(self):
        game = create_game()
        creatures = [
            Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
            for i in range(3)
        ]
        set_board_state(
            game, 0,
            hand=[WitherbloomTheBalancer(owner=None)],
            battlefield=creatures,
            mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        # {6}{B}{G} − 3 creatures = {3}{B}{G}; exactly that in pool.
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.players[0].mana_pool.total() == 0
        bf = game.get_battlefield(game.players[0])
        assert any(c.name == "Witherbloom, the Balancer" for c in bf.get_all())

    def test_no_creatures_full_cost(self):
        game = create_game()
        set_board_state(
            game, 0,
            hand=[WitherbloomTheBalancer(owner=None)],
            battlefield=[],
            mana={ManaType.COLORLESS: 6, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.players[0].mana_pool.total() == 0


class TestWitherbloomGrantsAffinity:
    def test_your_sorcery_gets_affinity(self):
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=None)
        bears = [
            Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
            for i in range(2)
        ]
        set_board_state(
            game, 0,
            battlefield=[witherbloom] + bears,
            hand=[TogetherAsOne(owner=None)],
            mana={ManaType.GREEN: 3},
        )
        # {6} sorcery − 3 creatures (Witherbloom counts itself) = {3}.
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        assert p1.mana_pool.total() == 0

    def test_opponents_spells_not_reduced(self):
        game = create_game()
        p1, p2 = game.players
        set_board_state(
            game, 0,
            battlefield=[WitherbloomTheBalancer(owner=None)],
        )
        set_board_state(game, 1, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.RED: 3})
        # Opponent has 3 mana but the {6} sorcery gets no reduction from
        # MY Witherbloom — the cast must fail.
        import pytest
        from test_utils import TestSetupError

        with pytest.raises(TestSetupError):
            cast_spell(game, 1, "Together as One", targets=[p1, p2])

    def test_creature_spells_not_reduced_by_grant(self):
        game = create_game()
        witherbloom = WitherbloomTheBalancer(owner=None)
        bears = [
            Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
            for i in range(4)
        ]
        set_board_state(
            game, 0,
            battlefield=[witherbloom] + bears,
            hand=[Creature(name="Hill Giant", base_power=3, base_toughness=3,
                           mana_cost=ManaCost.parse("{3}{R}"))],
            mana={ManaType.RED: 2},
        )
        # The grant only applies to instants/sorceries; a creature spell
        # with {3}{R} cannot be cast off {R}{R}.
        import pytest
        from test_utils import TestSetupError

        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Hill Giant")
