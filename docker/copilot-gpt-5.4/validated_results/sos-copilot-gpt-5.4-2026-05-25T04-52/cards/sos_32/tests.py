"""Tests for SOS 32 — Soaring Stoneglider."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_32.card_impl import SoaringStoneglider
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestSoaringStonegliderProperties:
    """Static card data should match the SOS 32 spec."""

    def test_is_elephant_cleric_creature_with_flying_and_vigilance(self) -> None:
        card = SoaringStoneglider(owner=None)
        assert isinstance(card, Creature)
        assert "Elephant" in card.subtypes
        assert "Cleric" in card.subtypes
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = SoaringStoneglider(owner=None)
        assert card.name == "Soaring Stoneglider"
        assert card.mana_cost == ManaCost.parse("{2}{W}")
        assert card.base_power == 4
        assert card.base_toughness == 3


class TestSoaringStonegliderAdditionalCost:
    """Soaring Stoneglider should demand graveyard exiles or the printed surcharge."""

    def test_casting_with_two_graveyard_cards_exiles_them_and_resolves_normally(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        graveyard_card_a = CardImpl(name="Spent Note")
        graveyard_card_b = CardImpl(name="Old Lesson")
        spell = SoaringStoneglider(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            graveyard=[graveyard_card_a, graveyard_card_b],
            mana={ManaType.WHITE: 3},
        )

        cast_spell_paid(game, p1, spell)

        assert not game.get_graveyard(p1).contains(graveyard_card_a)
        assert not game.get_graveyard(p1).contains(graveyard_card_b)
        assert game.get_exile(p1).contains(graveyard_card_a)
        assert game.get_exile(p1).contains(graveyard_card_b)
        assert game.stack.peek().source is spell

        resolve_top(game)

        assert game.get_battlefield(p1).contains(spell)

    def test_casting_without_two_graveyard_cards_or_extra_mana_is_illegal(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        lone_graveyard_card = CardImpl(name="Only Note")
        spell = SoaringStoneglider(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            graveyard=[lone_graveyard_card],
            mana={ManaType.WHITE: 3},
        )

        with pytest.raises(CastingError):
            cast_spell_paid(game, p1, spell)

        assert game.get_hand(p1).contains(spell)
        assert game.get_graveyard(p1).contains(lone_graveyard_card)
        assert game.stack.is_empty()

    def test_casting_may_pay_the_additional_mana_instead_of_exiling_graveyard_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        spell = SoaringStoneglider(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.WHITE: 4},
        )

        cast_spell_paid(game, p1, spell)

        assert p1.mana_pool.total() == 0
        assert game.stack.peek().source is spell
        assert game.get_exile(p1).get_all() == []

        resolve_top(game)

        assert game.get_battlefield(p1).contains(spell)
