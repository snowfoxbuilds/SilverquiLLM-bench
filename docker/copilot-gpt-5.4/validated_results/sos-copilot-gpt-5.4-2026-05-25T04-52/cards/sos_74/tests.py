"""Tests for SOS 74 — Arnyn, Deathbloom Botanist."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_74.card_impl import ArnynDeathbloomBotanist
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import CreatureDiesTriggeredEvent
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Supertype
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestArnynDeathbloomBotanistProperties:
    """Static card data should match the SOS 74 spec."""

    def test_is_legendary_vampire_druid_with_deathtouch(self) -> None:
        card = ArnynDeathbloomBotanist(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Vampire" in card.subtypes
        assert "Druid" in card.subtypes
        assert Keyword.DEATHTOUCH in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = ArnynDeathbloomBotanist(owner=None)
        assert card.name == "Arnyn, Deathbloom Botanist"
        assert card.mana_cost == ManaCost.parse("{2}{B}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestArnynDeathbloomBotanistTrigger:
    """Arnyn should trigger when your qualifying creatures die."""

    def test_registers_a_creature_dies_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ArnynDeathbloomBotanist(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert any(trigger.event_type is CreatureDiesTriggeredEvent for trigger in triggers)

    def test_when_your_power_one_creature_dies_target_opponent_loses_two_life_and_you_gain_two(self) -> None:
        game = create_game()
        p1, p2 = game.players
        arnyn = ArnynDeathbloomBotanist(owner=p1, controller=p1)
        small_creature = Creature(
            name="Frail Apprentice",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=3,
        )
        set_board_state(game, 0, battlefield=[arnyn, small_creature])
        p1.choose_target = lambda options, requirement: p2
        arnyn.register_triggers(game)

        destroy(game, small_creature)
        resolve_top(game)

        assert p2.life == 18
        assert p1.life == 22

    def test_when_your_toughness_one_creature_dies_target_opponent_loses_two_life_and_you_gain_two(self) -> None:
        game = create_game()
        p1, p2 = game.players
        arnyn = ArnynDeathbloomBotanist(owner=p1, controller=p1)
        small_creature = Creature(
            name="Glass Student",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[arnyn, small_creature])
        p1.choose_target = lambda options, requirement: p2
        arnyn.register_triggers(game)

        destroy(game, small_creature)
        resolve_top(game)

        assert p2.life == 18
        assert p1.life == 22

    def test_does_not_trigger_when_your_creature_has_neither_power_nor_toughness_one_or_less(self) -> None:
        game = create_game()
        p1, p2 = game.players
        arnyn = ArnynDeathbloomBotanist(owner=p1, controller=p1)
        medium_creature = Creature(
            name="Ordinary Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[arnyn, medium_creature])
        arnyn.register_triggers(game)

        destroy(game, medium_creature)

        assert game.stack.is_empty()
        assert p1.life == 20
        assert p2.life == 20

    def test_does_not_trigger_when_an_opponents_small_creature_dies(self) -> None:
        game = create_game()
        p1, p2 = game.players
        arnyn = ArnynDeathbloomBotanist(owner=p1, controller=p1)
        opposing_creature = Creature(
            name="Enemy Assistant",
            owner=p2,
            controller=p2,
            base_power=1,
            base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[arnyn])
        set_board_state(game, 1, battlefield=[opposing_creature])
        arnyn.register_triggers(game)

        destroy(game, opposing_creature)

        assert game.stack.is_empty()
        assert p1.life == 20
        assert p2.life == 20

