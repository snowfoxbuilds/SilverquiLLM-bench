"""Tests for SOS 154 — Mindful Biomancer."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_154.card_impl import MindfulBiomancer
from benchmarks.sos.workspace.engine.abilities import AbilityError, ActivatedAbilityInstance, activate_ability
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.mana import ManaPool
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestMindfulBiomancerProperties:
    """Static card data should match the SOS 154 spec."""

    def test_is_dryad_druid_creature(self) -> None:
        card = MindfulBiomancer(owner=None)

        assert isinstance(card, Creature)
        assert "Dryad" in card.subtypes
        assert "Druid" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = MindfulBiomancer(owner=None)

        assert card.name == "Mindful Biomancer"
        assert card.mana_cost == ManaCost.parse("{1}{G}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestMindfulBiomancerEnters:
    """Mindful Biomancer should gain you 1 life when it enters."""

    def test_registers_an_enters_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MindfulBiomancer(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent

    def test_self_entry_puts_a_trigger_on_the_stack_and_gains_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MindfulBiomancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1

        resolve_top(game)

        assert p1.life == 21
        assert getattr(p1, "life_gained_this_turn", 0) == 1


class TestMindfulBiomancerActivatedAbility:
    """Mindful Biomancer should pump itself only once each turn."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = MindfulBiomancer(owner=None).get_activated_abilities()

        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_requires_two_generic_and_one_green_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MindfulBiomancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_activated_abilities()[0]

        p1.mana_pool = ManaPool()
        p1.mana_pool.add(ManaType.GREEN, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        assert ability.cost(game, card) is False
        assert p1.mana_pool.total() == 2

        p1.mana_pool = ManaPool()
        p1.mana_pool.add(ManaType.GREEN, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        assert ability.cost(game, card) is True
        assert p1.mana_pool.total() == 0

    def test_effect_gives_this_creature_plus_two_plus_two_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MindfulBiomancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_activated_abilities()[0]

        ability.effect(game)

        assert card.power == 4
        assert card.toughness == 4

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert card.power == 2
        assert card.toughness == 2

    def test_can_only_be_activated_once_each_turn_but_can_be_activated_again_on_a_later_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MindfulBiomancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_activated_abilities()[0]

        p1.mana_pool.add(ManaType.GREEN, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        activate_ability(
            game,
            p1,
            ActivatedAbilityInstance(
                source=card,
                controller=p1,
                cost=ability.cost,
                effect=ability.effect,
                description=ability.description,
            ),
        )
        assert len(game.stack) == 1
        resolve_top(game)

        p1.mana_pool.empty()
        p1.mana_pool.add(ManaType.GREEN, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        with pytest.raises(AbilityError):
            activate_ability(
                game,
                p1,
                ActivatedAbilityInstance(
                    source=card,
                    controller=p1,
                    cost=ability.cost,
                    effect=ability.effect,
                    description=ability.description,
                ),
            )

        game.turn_number += 1
        p1.mana_pool.empty()
        p1.mana_pool.add(ManaType.GREEN, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        activate_ability(
            game,
            p1,
            ActivatedAbilityInstance(
                source=card,
                controller=p1,
                cost=ability.cost,
                effect=ability.effect,
                description=ability.description,
            ),
        )

        assert len(game.stack) == 1
