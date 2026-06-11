"""Tests for SOS 62 — Orysa, Tide Choreographer."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_62.card_impl import OrysaTideChoreographer
from benchmarks.sos.workspace.engine.casting import get_cost_reduction
from benchmarks.sos.workspace.engine.card import CardImpl, Creature
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Supertype
from benchmarks.sos.workspace.tests.test_utils import cast_spell, create_game, set_board_state


class TestOrysaTideChoreographerProperties:
    """Static card data should match the SOS 62 spec."""

    def test_is_a_legendary_merfolk_bard_creature(self) -> None:
        card = OrysaTideChoreographer(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Merfolk" in card.subtypes
        assert "Bard" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = OrysaTideChoreographer(owner=None)
        assert card.name == "Orysa, Tide Choreographer"
        assert card.mana_cost == ManaCost.parse("{4}{U}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestOrysaTideChoreographerCasting:
    """Orysa should reduce its own cost from your creatures' total toughness."""

    def test_cost_reduction_is_three_at_total_toughness_ten(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wall = Creature(name="Wall", owner=p1, controller=p1, base_power=0, base_toughness=4)
        whale = Creature(name="Whale", owner=p1, controller=p1, base_power=3, base_toughness=6)
        set_board_state(game, 0, battlefield=[wall, whale])

        card = OrysaTideChoreographer(owner=p1, controller=p1)

        assert get_cost_reduction(game, card, p1) == 3

    def test_cost_reduction_counts_only_your_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ally = Creature(name="Ally", owner=p1, controller=p1, base_power=2, base_toughness=8)
        enemy = Creature(name="Enemy", owner=p2, controller=p2, base_power=5, base_toughness=10)
        set_board_state(game, 0, battlefield=[ally])
        set_board_state(game, 1, battlefield=[enemy])

        card = OrysaTideChoreographer(owner=p1, controller=p1)

        assert get_cost_reduction(game, card, p1) == 0

    def test_reduced_cost_cast_puts_orysa_onto_the_battlefield_and_draws_two_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        draw_one = CardImpl(name="First Draw", owner=p1, controller=p1)
        draw_two = CardImpl(name="Second Draw", owner=p1, controller=p1)
        wall = Creature(name="Wall", owner=p1, controller=p1, base_power=0, base_toughness=4)
        whale = Creature(name="Whale", owner=p1, controller=p1, base_power=3, base_toughness=6)
        spell = OrysaTideChoreographer(owner=p1, controller=p1)
        game.get_library(p1).add(draw_one)
        game.get_library(p1).add(draw_two)
        set_board_state(
            game,
            0,
            battlefield=[wall, whale],
            hand=[spell],
            mana={ManaType.BLUE: 2},
        )

        cast_spell(game, 0, "Orysa, Tide Choreographer")

        assert game.get_battlefield(p1).contains(spell)
        assert game.get_hand(p1).contains(draw_one)
        assert game.get_hand(p1).contains(draw_two)
        assert not game.get_graveyard(p1).contains(spell)
