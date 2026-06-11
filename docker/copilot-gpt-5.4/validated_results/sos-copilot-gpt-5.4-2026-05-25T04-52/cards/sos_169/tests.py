"""Tests for SOS 169 — Zimone's Experiment."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_169.card_impl import ZimonesExperiment
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Land, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestZimonesExperimentProperties:
    """Static card data should match the SOS 169 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(ZimonesExperiment(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = ZimonesExperiment(owner=None)

        assert card.name == "Zimone's Experiment"
        assert card.mana_cost == ManaCost.parse("{3}{G}")


class TestZimonesExperimentResolution:
    """Zimone's Experiment should turn a top-five look into land and creature value."""

    def test_it_can_put_a_revealed_land_onto_the_battlefield_tapped_and_a_revealed_creature_into_your_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        deeper = CardImpl(name="Deeper Lesson", owner=p1, controller=p1)
        creature_card = Creature(
            name="Chosen Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        land_card = Land(name="Chosen Land", owner=p1, controller=p1)
        spell_a = CardImpl(name="Top Spell A", owner=p1, controller=p1)
        spell_b = CardImpl(name="Top Spell B", owner=p1, controller=p1)
        spell_c = CardImpl(name="Top Spell C", owner=p1, controller=p1)
        game.get_library(p1).add(deeper)
        game.get_library(p1).add(creature_card)
        game.get_library(p1).add(land_card)
        game.get_library(p1).add(spell_a)
        game.get_library(p1).add(spell_b)
        game.get_library(p1).add(spell_c)
        game.queue_bottom_order(spell_c, spell_a, spell_b)
        p1._script.extend([creature_card, land_card])

        card = ZimonesExperiment(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_hand(p1).contains(creature_card)
        assert game.get_battlefield(p1).contains(land_card)
        assert land_card.is_tapped is True
        assert not game.get_battlefield(p1).contains(creature_card)
        assert not game.get_hand(p1).contains(land_card)

        assert len(game.look_history) == 1
        look_record = game.look_history[-1]
        assert look_record.player_index == 0
        assert look_record.cards == [creature_card, land_card, spell_a, spell_b, spell_c]
        assert look_record.source is card
        assert look_record.reason == "Zimone's Experiment"

        assert len(game.reveal_history) == 1
        reveal_record = game.reveal_history[-1]
        assert reveal_record.player_index == 0
        assert reveal_record.cards == [creature_card, land_card]
        assert reveal_record.source is card
        assert reveal_record.reason == "Zimone's Experiment"

        assert len(game.bottom_order_history) == 1
        bottom_record = game.bottom_order_history[-1]
        assert bottom_record.player_index == 0
        assert bottom_record.cards == [spell_a, spell_b, spell_c]
        assert bottom_record.ordered_cards == [spell_c, spell_a, spell_b]
        assert bottom_record.source is card
        assert bottom_record.reason == "Zimone's Experiment"
        assert bottom_record.used_queued_order is True
        assert game.get_library(p1).get_all() == [spell_c, spell_a, spell_b, deeper]

    def test_you_may_take_only_one_eligible_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        deeper = CardImpl(name="Deeper Lesson", owner=p1, controller=p1)
        creature_card = Creature(
            name="Chosen Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        land_card = Land(name="Chosen Land", owner=p1, controller=p1)
        spell_a = CardImpl(name="Top Spell A", owner=p1, controller=p1)
        spell_b = CardImpl(name="Top Spell B", owner=p1, controller=p1)
        spell_c = CardImpl(name="Top Spell C", owner=p1, controller=p1)
        game.get_library(p1).add(deeper)
        game.get_library(p1).add(creature_card)
        game.get_library(p1).add(land_card)
        game.get_library(p1).add(spell_a)
        game.get_library(p1).add(spell_b)
        game.get_library(p1).add(spell_c)
        p1._script.extend([land_card, None])

        card = ZimonesExperiment(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_battlefield(p1).contains(land_card)
        assert land_card.is_tapped is True
        assert game.get_hand(p1).contains(creature_card) is False
        assert game.get_library(p1).contains(creature_card)
        assert len(game.reveal_history) == 1
        assert game.reveal_history[-1].cards == [land_card]

    def test_you_may_decline_to_reveal_any_eligible_cards_and_put_all_five_on_the_bottom(self) -> None:
        game = create_game()
        p1 = game.players[0]
        deeper = CardImpl(name="Deeper Lesson", owner=p1, controller=p1)
        creature_card = Creature(
            name="Chosen Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        land_card = Land(name="Chosen Land", owner=p1, controller=p1)
        spell_a = CardImpl(name="Top Spell A", owner=p1, controller=p1)
        spell_b = CardImpl(name="Top Spell B", owner=p1, controller=p1)
        spell_c = CardImpl(name="Top Spell C", owner=p1, controller=p1)
        game.get_library(p1).add(deeper)
        game.get_library(p1).add(creature_card)
        game.get_library(p1).add(land_card)
        game.get_library(p1).add(spell_a)
        game.get_library(p1).add(spell_b)
        game.get_library(p1).add(spell_c)
        game.queue_bottom_order(spell_b, creature_card, land_card, spell_c, spell_a)
        p1._script.append(None)

        card = ZimonesExperiment(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_hand(p1).get_all() == []
        assert game.get_battlefield(p1).get_all() == []
        assert len(game.reveal_history) == 0
        assert len(game.bottom_order_history) == 1
        assert game.bottom_order_history[-1].ordered_cards == [
            spell_b,
            creature_card,
            land_card,
            spell_c,
            spell_a,
        ]
        assert game.get_hand(p1).get_all() == []
        assert game.get_library(p1).get_all() == [
            spell_b,
            creature_card,
            land_card,
            spell_c,
            spell_a,
            deeper,
        ]
