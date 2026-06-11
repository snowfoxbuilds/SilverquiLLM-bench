"""Tests for SOS 187 — Essenceknit Scholar."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_187.card_impl import EssenceknitScholar
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature
from benchmarks.sos.workspace.engine.events import (
    AttacksTriggeredEvent,
    EndStepTriggeredEvent,
    EntersBattlefieldTriggeredEvent,
)
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestEssenceknitScholarProperties:
    """Static card data should match the SOS 187 spec."""

    def test_is_dryad_warlock_creature(self) -> None:
        card = EssenceknitScholar(owner=None)

        assert isinstance(card, Creature)
        assert "Dryad" in card.subtypes
        assert "Warlock" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = EssenceknitScholar(owner=None)

        assert card.name == "Essenceknit Scholar"
        assert card.mana_cost == ManaCost.parse("{B}{B/G}{G}")
        assert card.base_power == 3
        assert card.base_toughness == 1


class TestEssenceknitScholarTriggers:
    """Essenceknit Scholar should make a Pest and draw after your deaths."""

    def test_registers_enter_and_end_step_triggers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EssenceknitScholar(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 2
        assert {trigger.event_type for trigger in triggers} == {
            EntersBattlefieldTriggeredEvent,
            EndStepTriggeredEvent,
        }

    def test_enters_trigger_creates_a_black_and_green_pest_token_whose_attack_trigger_gains_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EssenceknitScholar(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1
        resolve_top(game)

        tokens = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if getattr(permanent, "is_token", False)
        ]
        assert len(tokens) == 1

        token = tokens[0]
        assert isinstance(token, Creature)
        assert token.power == 1
        assert token.toughness == 1
        assert "Pest" in token.subtypes
        assert get_colors(token) == {Color.BLACK, Color.GREEN}

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=token, attacker=token),
        )

        assert len(game.stack) == 1
        resolve_top(game)
        assert p1.life == 21

    def test_your_end_step_after_a_creature_you_control_died_this_turn_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        scholar = EssenceknitScholar(owner=p1, controller=p1)
        fallen = Creature(
            name="Fallen Assistant",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        drawn = CardImpl(name="Recovered Theory", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[scholar, fallen])
        game.get_library(p1).add(drawn)
        scholar.register_triggers(game)

        destroy(game, fallen)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))

        assert len(game.stack) == 1
        resolve_top(game)

        assert game.get_hand(p1).contains(drawn)
        assert not game.get_library(p1).contains(drawn)

    def test_end_step_does_not_trigger_when_only_an_opponents_creature_died(self) -> None:
        game = create_game()
        p1, p2 = game.players
        scholar = EssenceknitScholar(owner=p1, controller=p1)
        opposing = Creature(
            name="Opposing Assistant",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        undrawn = CardImpl(name="Still Waiting", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[scholar])
        set_board_state(game, 1, battlefield=[opposing])
        game.get_library(p1).add(undrawn)
        scholar.register_triggers(game)

        destroy(game, opposing)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))

        assert game.stack.is_empty()
        assert game.get_library(p1).contains(undrawn)
        assert not game.get_hand(p1).contains(undrawn)
