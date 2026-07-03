"""Tests for SOS 26 — Primary Research."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_26.card_impl import PrimaryResearch
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Enchantment, Instant, Land
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestPrimaryResearchProperties:
    """Static card data should match the SOS 26 spec."""

    def test_is_enchantment(self) -> None:
        assert isinstance(PrimaryResearch(owner=None), Enchantment)

    def test_name_and_mana_cost(self) -> None:
        card = PrimaryResearch(owner=None)
        assert card.name == "Primary Research"
        assert card.mana_cost == ManaCost.parse("{4}{W}")


class TestPrimaryResearchTargeting:
    """Primary Research should target a small nonland permanent card in your graveyard."""

    def test_returns_single_graveyard_target_requirement(self) -> None:
        game = create_game()
        reqs = PrimaryResearch(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.GRAVEYARD

    def test_target_filter_accepts_nonland_permanent_cards_with_mana_value_3_or_less(self) -> None:
        game = create_game()
        req = PrimaryResearch(owner=None).get_targets(game)[0]

        acceptable = Creature(
            name="Recovered Assistant",
            mana_cost=ManaCost.parse("{3}"),
            base_power=2,
            base_toughness=2,
        )
        land = Land(name="Recovered Campus")
        expensive = Creature(
            name="Too Advanced",
            mana_cost=ManaCost.parse("{4}"),
            base_power=4,
            base_toughness=4,
        )
        nonpermanent = Instant(name="Study Notes", mana_cost=ManaCost.parse("{1}"))

        assert req.filter_fn(acceptable) is True
        assert req.filter_fn(land) is False
        assert req.filter_fn(expensive) is False
        assert req.filter_fn(nonpermanent) is False


class TestPrimaryResearchResolution:
    """Primary Research should return the chosen card from graveyard to battlefield."""

    def test_on_resolve_returns_the_chosen_target_to_the_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Recovered Assistant",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{3}"),
            base_power=2,
            base_toughness=2,
        )
        game.get_graveyard(p1).add(target)

        card = PrimaryResearch(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        assert not game.get_graveyard(p1).contains(target)
        assert game.get_battlefield(p1).contains(target)


class TestPrimaryResearchEndStep:
    """Primary Research should draw on your end step after your graveyard was depleted."""

    def test_your_end_step_after_a_card_left_your_graveyard_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        enchantment = PrimaryResearch(owner=p1, controller=p1)
        departed = CardImpl(name="Recovered Notes", owner=p1, controller=p1)
        drawn = CardImpl(name="Fresh Insight", owner=p1, controller=p1)

        game.get_battlefield(p1).add(enchantment)
        game.get_graveyard(p1).add(departed)
        game.get_library(p1).add(drawn)
        enchantment.register_triggers(game)

        move_to_zone(game, departed, Zone.GRAVEYARD, Zone.HAND)
        while not game.stack.is_empty():
            resolve_top(game)

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))

        assert len(game.stack) == 1

        resolve_top(game)

        assert game.get_hand(p1).contains(drawn)
        assert not game.get_library(p1).contains(drawn)

    def test_does_not_draw_when_no_card_left_your_graveyard_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        enchantment = PrimaryResearch(owner=p1, controller=p1)
        drawn = CardImpl(name="Fresh Insight", owner=p1, controller=p1)

        game.get_battlefield(p1).add(enchantment)
        game.get_library(p1).add(drawn)
        enchantment.register_triggers(game)

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))

        assert game.stack.is_empty()
        assert not game.get_hand(p1).contains(drawn)
        assert game.get_library(p1).contains(drawn)

    def test_does_not_draw_on_an_opponents_end_step_even_if_your_graveyard_was_depleted(self) -> None:
        game = create_game()
        p1, p2 = game.players
        enchantment = PrimaryResearch(owner=p1, controller=p1)
        departed = CardImpl(name="Recovered Notes", owner=p1, controller=p1)
        drawn = CardImpl(name="Fresh Insight", owner=p1, controller=p1)

        game.get_battlefield(p1).add(enchantment)
        game.get_graveyard(p1).add(departed)
        game.get_library(p1).add(drawn)
        enchantment.register_triggers(game)

        move_to_zone(game, departed, Zone.GRAVEYARD, Zone.HAND)
        while not game.stack.is_empty():
            resolve_top(game)

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p2))

        assert game.stack.is_empty()
        assert not game.get_hand(p1).contains(drawn)
        assert game.get_library(p1).contains(drawn)
