"""Tests for SOS 14 — Ennis, Debate Moderator."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_14.card_impl import EnnisDebateModerator
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestEnnisDebateModeratorProperties:
    """Static card data should match the SOS 14 spec."""

    def test_is_legendary_human_cleric(self) -> None:
        card = EnnisDebateModerator(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Human" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = EnnisDebateModerator(owner=None)
        assert card.name == "Ennis, Debate Moderator"
        assert card.mana_cost == ManaCost.parse("{1}{W}")
        assert card.base_power == 1
        assert card.base_toughness == 1


class TestEnnisDebateModeratorTargeting:
    """The ETB ability should target up to one other creature you control."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = EnnisDebateModerator(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_other_creature_you_control_only(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EnnisDebateModerator(owner=p1, controller=p1)
        req = card.get_targets(game)[0]

        ally = Creature(
            name="Ally Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opponent_creature = Creature(
            name="Enemy Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        assert req.filter_fn(ally) is True
        assert req.filter_fn(card) is False
        assert req.filter_fn(opponent_creature) is False


class TestEnnisDebateModeratorResolution:
    """Ennis should flicker another creature and reward exile on your end step."""

    def test_no_target_is_allowed(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EnnisDebateModerator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        card.on_resolve(game)

        assert game.get_exile(p1).get_all() == []

    def test_exiles_target_and_returns_it_under_its_owners_control_at_next_end_step(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EnnisDebateModerator(owner=p1, controller=p1)
        stolen = Creature(
            name="Borrowed Bear",
            owner=p2,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(card)
        game.get_battlefield(p1).add(stolen)
        card.register_triggers(game)
        card.chosen_targets = [stolen]

        card.on_resolve(game)

        assert not game.get_battlefield(p1).contains(stolen)
        assert game.get_exile(p2).contains(stolen)

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        assert not game.get_exile(p2).contains(stolen)
        assert game.get_battlefield(p2).contains(stolen)
        assert stolen.controller is p2

    def test_puts_a_counter_on_ennis_at_your_end_step_if_a_card_was_exiled_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EnnisDebateModerator(owner=p1, controller=p1)
        ally = Creature(
            name="Helpful Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(card)
        game.get_battlefield(p1).add(ally)
        card.register_triggers(game)
        card.chosen_targets = [ally]

        card.on_resolve(game)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        assert card.plus_one_counters == 1
