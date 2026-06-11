"""Tests for SOS 49 — Flow State."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_49 import card_impl as sos_49_card_impl
from benchmarks.sos.workspace.engine.card import CardImpl, Instant, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game

FlowState = getattr(sos_49_card_impl, "FlowState", None)
if FlowState is None:
    FlowState = getattr(sos_49_card_impl, "EssenceScatter")


class TestFlowStateProperties:
    """Static card data should match the SOS 49 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(FlowState(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = FlowState(owner=None)
        assert card.name == "Flow State"
        assert card.mana_cost == ManaCost.parse("{1}{U}")


class TestFlowStateResolution:
    """Flow State should turn top-of-library selection into card advantage."""

    def test_without_an_instant_and_a_sorcery_in_your_graveyard_it_puts_one_chosen_card_into_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        filler = CardImpl(name="Deep Archive", owner=p1, controller=p1)
        first = CardImpl(name="Lesson One", owner=p1, controller=p1)
        second = CardImpl(name="Lesson Two", owner=p1, controller=p1)
        third = CardImpl(name="Lesson Three", owner=p1, controller=p1)
        game.get_library(p1).add(filler)
        game.get_library(p1).add(first)
        game.get_library(p1).add(second)
        game.get_library(p1).add(third)
        p1._script.extend([second, first, third])

        card = FlowState(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_hand(p1).contains(second)
        assert not game.get_library(p1).contains(second)
        final_library = game.get_library(p1).get_all()
        assert final_library[-1] is filler
        assert set(final_library[:-1]) == {first, third}

    def test_with_an_instant_and_a_sorcery_in_your_graveyard_it_puts_two_chosen_cards_into_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        filler = CardImpl(name="Deep Archive", owner=p1, controller=p1)
        first = CardImpl(name="Lesson One", owner=p1, controller=p1)
        second = CardImpl(name="Lesson Two", owner=p1, controller=p1)
        third = CardImpl(name="Lesson Three", owner=p1, controller=p1)
        instant_card = Instant(name="Study Notes", owner=p1, controller=p1, mana_cost=ManaCost.parse("{U}"))
        sorcery_card = Sorcery(name="Lecture Plan", owner=p1, controller=p1, mana_cost=ManaCost.parse("{1}{U}"))
        game.get_library(p1).add(filler)
        game.get_library(p1).add(first)
        game.get_library(p1).add(second)
        game.get_library(p1).add(third)
        game.get_graveyard(p1).add(instant_card)
        game.get_graveyard(p1).add(sorcery_card)
        p1._script.extend([first, third, second])

        card = FlowState(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_hand(p1).contains(first)
        assert game.get_hand(p1).contains(third)
        assert not game.get_library(p1).contains(first)
        assert not game.get_library(p1).contains(third)
        assert game.get_library(p1).get_all() == [second, filler]

    def test_having_only_one_of_the_two_graveyard_card_types_does_not_enable_the_bonus_pick(self) -> None:
        game = create_game()
        p1 = game.players[0]
        first = CardImpl(name="Lesson One", owner=p1, controller=p1)
        second = CardImpl(name="Lesson Two", owner=p1, controller=p1)
        third = CardImpl(name="Lesson Three", owner=p1, controller=p1)
        instant_card = Instant(name="Study Notes", owner=p1, controller=p1, mana_cost=ManaCost.parse("{U}"))
        game.get_library(p1).add(first)
        game.get_library(p1).add(second)
        game.get_library(p1).add(third)
        game.get_graveyard(p1).add(instant_card)
        p1._script.extend([third, first, second])

        card = FlowState(owner=p1, controller=p1)
        card.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == 1
        assert game.get_hand(p1).contains(third)
        assert len(game.get_library(p1).get_all()) == 2
