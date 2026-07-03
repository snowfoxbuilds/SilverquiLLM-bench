"""Tests for SOS 70 — Textbook Tabulator."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_70.card_impl import TextbookTabulator
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import cast_spell, create_game, set_board_state


class OneManaTestInstant(Instant):
    """One-mana instant used to exercise Increment."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "One-Mana Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class TestTextbookTabulatorProperties:
    """Static card data should match the SOS 70 spec."""

    def test_is_frog_wizard_creature(self) -> None:
        card = TextbookTabulator(owner=None)
        assert isinstance(card, Creature)
        assert "Frog" in card.subtypes
        assert "Wizard" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = TextbookTabulator(owner=None)
        assert card.name == "Textbook Tabulator"
        assert card.mana_cost == ManaCost.parse("{2}{U}")
        assert card.base_power == 0
        assert card.base_toughness == 3


class TestTextbookTabulatorSurveil:
    """Textbook Tabulator should surveil 2 when it resolves."""

    def test_on_resolve_may_put_both_surveilled_cards_into_the_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        middle = CardImpl(name="Middle Card", owner=p1, controller=p1)
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(middle)
        game.get_library(p1).add(top)
        p1._script.extend([True, True])

        TextbookTabulator(owner=p1, controller=p1).on_resolve(game)

        assert game.get_graveyard(p1).contains(top)
        assert game.get_graveyard(p1).contains(middle)
        assert game.get_library(p1).get_all() == [bottom]

    def test_on_resolve_may_leave_both_surveilled_cards_on_top_of_the_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        middle = CardImpl(name="Middle Card", owner=p1, controller=p1)
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(middle)
        game.get_library(p1).add(top)
        p1._script.extend([False, False])

        TextbookTabulator(owner=p1, controller=p1).on_resolve(game)

        assert game.get_graveyard(p1).get_all() == []
        assert game.get_library(p1).get_all() == [bottom, middle, top]

    def test_empty_library_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]

        TextbookTabulator(owner=p1, controller=p1).on_resolve(game)

        assert game.get_library(p1).get_all() == []
        assert game.get_graveyard(p1).get_all() == []


class TestTextbookTabulatorIncrement:
    """Textbook Tabulator should grow from qualifying spells."""

    def test_casting_a_one_mana_spell_adds_a_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = OneManaTestInstant(owner=p1, controller=p1)
        card = TextbookTabulator(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        card.register_triggers(game)

        cast_spell(game, 0, "One-Mana Test Instant")

        assert card.plus_one_counters == 1
        assert game.get_graveyard(p1).contains(spell)

    def test_casting_a_one_mana_spell_does_not_trigger_increment_once_it_has_a_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = OneManaTestInstant(owner=p1, controller=p1)
        card = TextbookTabulator(owner=p1, controller=p1)
        card.plus_one_counters = 1
        card._base_plus_one_counters = 1
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        card.register_triggers(game)

        cast_spell(game, 0, "One-Mana Test Instant")

        assert card.plus_one_counters == 1
