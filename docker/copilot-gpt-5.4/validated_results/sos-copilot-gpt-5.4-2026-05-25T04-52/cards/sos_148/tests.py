"""Tests for SOS 148 — Follow the Lumarets."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_148.card_impl import FollowTheLumarets
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Land, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestFollowTheLumaretsProperties:
    """Static card data should match the SOS 148 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(FollowTheLumarets(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = FollowTheLumarets(owner=None)

        assert card.name == "Follow the Lumarets"
        assert card.mana_cost == ManaCost.parse("{1}{G}")


class TestFollowTheLumaretsResolution:
    """Follow the Lumarets should turn top-four selection into card advantage."""

    def test_without_life_gain_it_puts_one_chosen_creature_or_land_from_the_top_four_into_your_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        deeper_card = CardImpl(name="Deeper Lesson", owner=p1, controller=p1)
        creature_card = Creature(
            name="Top Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        land_card = Land(name="Top Land", owner=p1, controller=p1)
        spell_a = CardImpl(name="Top Spell A", owner=p1, controller=p1)
        spell_b = CardImpl(name="Top Spell B", owner=p1, controller=p1)
        game.get_library(p1).add(deeper_card)
        game.get_library(p1).add(creature_card)
        game.get_library(p1).add(land_card)
        game.get_library(p1).add(spell_a)
        game.get_library(p1).add(spell_b)
        p1._script.append(land_card)

        card = FollowTheLumarets(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_hand(p1).contains(land_card)
        assert not game.get_library(p1).contains(land_card)
        assert game.get_library(p1).contains(creature_card)
        assert game.get_library(p1).contains(spell_a)
        assert game.get_library(p1).contains(spell_b)
        assert game.get_library(p1).contains(deeper_card)

    def test_with_life_gain_it_may_put_two_chosen_creature_and_or_land_cards_from_the_top_four_into_your_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        first_pick = Creature(
            name="First Pick",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        second_pick = Land(name="Second Pick", owner=p1, controller=p1)
        spare_creature = Creature(
            name="Spare Creature",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        noneligible = CardImpl(name="Lecture Notes", owner=p1, controller=p1)
        game.get_library(p1).add(first_pick)
        game.get_library(p1).add(second_pick)
        game.get_library(p1).add(noneligible)
        game.get_library(p1).add(spare_creature)
        p1.life_gained_this_turn = 1
        p1._script.extend([first_pick, second_pick])

        card = FollowTheLumarets(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_hand(p1).contains(first_pick)
        assert game.get_hand(p1).contains(second_pick)
        assert not game.get_library(p1).contains(first_pick)
        assert not game.get_library(p1).contains(second_pick)
        assert game.get_library(p1).contains(spare_creature)
        assert game.get_library(p1).contains(noneligible)

    def test_you_may_decline_to_take_any_eligible_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        deeper_card = CardImpl(name="Deeper Lesson", owner=p1, controller=p1)
        creature_card = Creature(
            name="Top Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        land_card = Land(name="Top Land", owner=p1, controller=p1)
        spell_a = CardImpl(name="Top Spell A", owner=p1, controller=p1)
        spell_b = CardImpl(name="Top Spell B", owner=p1, controller=p1)
        game.get_library(p1).add(deeper_card)
        game.get_library(p1).add(creature_card)
        game.get_library(p1).add(land_card)
        game.get_library(p1).add(spell_a)
        game.get_library(p1).add(spell_b)
        p1._script.append(None)

        card = FollowTheLumarets(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_hand(p1).get_all() == []
        assert game.get_library(p1).contains(creature_card)
        assert game.get_library(p1).contains(land_card)
        assert game.get_library(p1).contains(spell_a)
        assert game.get_library(p1).contains(spell_b)
        assert game.get_library(p1).get_all()[-1] is deeper_card

    def test_without_life_gain_it_records_the_look_reveal_and_bottom_order_observations(self) -> None:
        game = create_game()
        p1 = game.players[0]
        deeper_card = CardImpl(name="Deeper Lesson", owner=p1, controller=p1)
        creature_card = Creature(
            name="Top Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        land_card = Land(name="Top Land", owner=p1, controller=p1)
        spell_a = CardImpl(name="Top Spell A", owner=p1, controller=p1)
        spell_b = CardImpl(name="Top Spell B", owner=p1, controller=p1)
        game.get_library(p1).add(deeper_card)
        game.get_library(p1).add(creature_card)
        game.get_library(p1).add(land_card)
        game.get_library(p1).add(spell_a)
        game.get_library(p1).add(spell_b)
        game.queue_bottom_order(spell_b, creature_card, spell_a)
        p1._script.append(land_card)

        card = FollowTheLumarets(owner=p1, controller=p1)
        card.on_resolve(game)

        assert len(game.look_history) == 1
        look_record = game.look_history[-1]
        assert look_record.player_index == 0
        assert look_record.cards == [creature_card, land_card, spell_a, spell_b]
        assert look_record.source is card
        assert look_record.reason == "Follow the Lumarets"

        assert len(game.reveal_history) == 1
        reveal_record = game.reveal_history[-1]
        assert reveal_record.player_index == 0
        assert reveal_record.cards == [land_card]
        assert reveal_record.source is card
        assert reveal_record.reason == "Follow the Lumarets"

        assert len(game.bottom_order_history) == 1
        bottom_record = game.bottom_order_history[-1]
        assert bottom_record.player_index == 0
        assert bottom_record.cards == [creature_card, spell_a, spell_b]
        assert bottom_record.ordered_cards == [spell_b, creature_card, spell_a]
        assert bottom_record.source is card
        assert bottom_record.reason == "Follow the Lumarets"
        assert bottom_record.used_queued_order is True
        assert game.get_library(p1).get_all() == [spell_b, creature_card, spell_a, deeper_card]

    def test_with_life_gain_it_records_two_revealed_cards_and_the_bottom_order_observation(self) -> None:
        game = create_game()
        p1 = game.players[0]
        first_pick = Creature(
            name="First Pick",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        second_pick = Land(name="Second Pick", owner=p1, controller=p1)
        noneligible = CardImpl(name="Lecture Notes", owner=p1, controller=p1)
        spare_creature = Creature(
            name="Spare Creature",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        game.get_library(p1).add(first_pick)
        game.get_library(p1).add(second_pick)
        game.get_library(p1).add(noneligible)
        game.get_library(p1).add(spare_creature)
        game.queue_bottom_order(spare_creature, noneligible)
        p1.life_gained_this_turn = 1
        p1._script.extend([first_pick, second_pick])

        card = FollowTheLumarets(owner=p1, controller=p1)
        card.on_resolve(game)

        assert len(game.look_history) == 1
        look_record = game.look_history[-1]
        assert look_record.player_index == 0
        assert look_record.cards == [first_pick, second_pick, noneligible, spare_creature]
        assert look_record.source is card
        assert look_record.reason == "Follow the Lumarets"

        assert len(game.reveal_history) == 1
        reveal_record = game.reveal_history[-1]
        assert reveal_record.player_index == 0
        assert reveal_record.cards == [first_pick, second_pick]
        assert reveal_record.source is card
        assert reveal_record.reason == "Follow the Lumarets"

        assert len(game.bottom_order_history) == 1
        bottom_record = game.bottom_order_history[-1]
        assert bottom_record.player_index == 0
        assert bottom_record.cards == [noneligible, spare_creature]
        assert bottom_record.ordered_cards == [spare_creature, noneligible]
        assert bottom_record.source is card
        assert bottom_record.reason == "Follow the Lumarets"
        assert bottom_record.used_queued_order is True
        assert game.get_library(p1).get_all() == [spare_creature, noneligible]
