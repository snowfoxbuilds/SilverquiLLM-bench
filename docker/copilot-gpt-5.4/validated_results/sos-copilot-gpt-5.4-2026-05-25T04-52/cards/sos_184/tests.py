"""Tests for SOS 184 — Dina's Guidance."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_184.card_impl import DinasGuidance
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestDinasGuidanceProperties:
    """Static card data should match the SOS 184 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(DinasGuidance(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = DinasGuidance(owner=None)

        assert card.name == "Dina's Guidance"
        assert card.mana_cost == ManaCost.parse("{1}{B}{G}")


class TestDinasGuidanceResolution:
    """Dina's Guidance should find a creature and move it to the chosen zone."""

    def test_searches_for_a_creature_reveals_it_puts_it_into_your_hand_and_shuffles(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom = CardImpl(name="Bottom Notes", owner=p1, controller=p1)
        target = Creature(
            name="Chosen Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        top = CardImpl(name="Top Notes", owner=p1, controller=p1)
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(target)
        game.get_library(p1).add(top)
        game.queue_shuffle_order(top, bottom)
        p1._script.extend([target, Zone.HAND])

        card = DinasGuidance(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_hand(p1).contains(target)
        assert not game.get_library(p1).contains(target)
        assert game.reveal_history[-1].cards == [target]
        assert game.shuffle_history[-1].after == [top, bottom]

    def test_searches_for_a_creature_reveals_it_puts_it_into_your_graveyard_and_shuffles(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom = CardImpl(name="Bottom Notes", owner=p1, controller=p1)
        target = Creature(
            name="Chosen Creature",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        top = CardImpl(name="Top Notes", owner=p1, controller=p1)
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(target)
        game.get_library(p1).add(top)
        game.queue_shuffle_order(top, bottom)
        p1._script.extend([target, Zone.GRAVEYARD])

        card = DinasGuidance(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_graveyard(p1).contains(target)
        assert not game.get_library(p1).contains(target)
        assert game.reveal_history[-1].cards == [target]
        assert game.shuffle_history[-1].after == [top, bottom]

    def test_if_no_creature_card_is_found_it_only_shuffles(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom = CardImpl(name="Bottom Notes", owner=p1, controller=p1)
        top = CardImpl(name="Top Notes", owner=p1, controller=p1)
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(top)
        game.queue_shuffle_order(top, bottom)

        card = DinasGuidance(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_hand(p1).get_all() == []
        assert game.get_graveyard(p1).get_all() == []
        assert game.reveal_history == []
        assert game.shuffle_history[-1].after == [top, bottom]
