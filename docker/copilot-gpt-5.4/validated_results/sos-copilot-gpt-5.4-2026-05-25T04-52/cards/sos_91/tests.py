"""Tests for SOS 91 — Moseo, Vein's New Dean."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_91.card_impl import MoseoVeinsNewDean
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import (
    AttacksTriggeredEvent,
    EndStepTriggeredEvent,
    EntersBattlefieldTriggeredEvent,
)
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, Supertype
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestMoseoVeinsNewDeanProperties:
    """Static card data should match the SOS 91 spec."""

    def test_is_legendary_bird_skeleton_warlock_with_flying(self) -> None:
        card = MoseoVeinsNewDean(owner=None)

        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Bird" in card.subtypes
        assert "Skeleton" in card.subtypes
        assert "Warlock" in card.subtypes
        assert Keyword.FLYING in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = MoseoVeinsNewDean(owner=None)

        assert card.name == "Moseo, Vein's New Dean"
        assert card.mana_cost == ManaCost.parse("{2}{B}")
        assert card.base_power == 2
        assert card.base_toughness == 1


class TestMoseoVeinsNewDeanTriggers:
    """Moseo should make a Pest on entry and reanimate on infused end steps."""

    def test_registers_enter_and_end_step_triggers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MoseoVeinsNewDean(owner=p1, controller=p1)

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
        card = MoseoVeinsNewDean(owner=p1, controller=p1)
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

    def test_infused_end_step_returns_a_creature_card_with_mana_value_at_most_life_gained(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MoseoVeinsNewDean(owner=p1, controller=p1)
        returned = Creature(
            name="Returned Pestkeeper",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}"),
            base_power=2,
            base_toughness=2,
        )
        too_expensive = Creature(
            name="Too Expensive",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{3}"),
            base_power=3,
            base_toughness=3,
        )
        set_board_state(game, 0, battlefield=[card], graveyard=[returned, too_expensive])
        p1.life_gained_this_turn = 2
        p1._script.append(returned)
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))

        assert len(game.stack) == 1
        resolve_top(game)

        assert game.get_battlefield(p1).contains(returned)
        assert not game.get_graveyard(p1).contains(returned)
        assert game.get_graveyard(p1).contains(too_expensive)

    def test_end_step_does_not_trigger_without_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MoseoVeinsNewDean(owner=p1, controller=p1)
        returned = Creature(
            name="Returned Pestkeeper",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}"),
            base_power=1,
            base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[card], graveyard=[returned])
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(returned)
        assert not game.get_battlefield(p1).contains(returned)
