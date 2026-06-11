"""Tests for SOS 179 — Cauldron of Essence."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_179.card_impl import CauldronOfEssence
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Artifact, CardImpl, Creature
from benchmarks.sos.workspace.engine.events import CreatureDiesTriggeredEvent
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestCauldronOfEssenceProperties:
    """Static card data should match the SOS 179 spec."""

    def test_is_artifact(self) -> None:
        assert isinstance(CauldronOfEssence(owner=None), Artifact)

    def test_name_and_mana_cost(self) -> None:
        card = CauldronOfEssence(owner=None)

        assert card.name == "Cauldron of Essence"
        assert card.mana_cost == ManaCost.parse("{1}{B}{G}")


class TestCauldronOfEssenceDiesTrigger:
    """Cauldron of Essence should reward you when your creatures die."""

    def test_registers_a_creature_dies_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CauldronOfEssence(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert any(trigger.event_type is CreatureDiesTriggeredEvent for trigger in triggers)

    def test_when_your_creature_dies_each_opponent_loses_one_and_you_gain_one(self) -> None:
        game = create_game()
        p1, p2 = game.players
        cauldron = CauldronOfEssence(owner=p1, controller=p1)
        fodder = Creature(
            name="Disposable Apprentice",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[cauldron, fodder])
        cauldron.register_triggers(game)

        destroy(game, fodder)

        assert len(game.stack) == 1

        resolve_top(game)

        assert p1.life == 21
        assert p2.life == 19

    def test_opponents_creature_dying_does_not_trigger_it(self) -> None:
        game = create_game()
        p1, p2 = game.players
        cauldron = CauldronOfEssence(owner=p1, controller=p1)
        enemy = Creature(
            name="Enemy Apprentice",
            owner=p2,
            controller=p2,
            base_power=1,
            base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[cauldron])
        set_board_state(game, 1, battlefield=[enemy])
        cauldron.register_triggers(game)

        destroy(game, enemy)

        assert game.stack.is_empty()
        assert p1.life == 20
        assert p2.life == 20


class TestCauldronOfEssenceActivatedAbility:
    """Cauldron of Essence should reanimate at sorcery speed by tapping and sacrificing."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = CauldronOfEssence(owner=None).get_activated_abilities()

        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_requires_one_black_green_taps_it_and_sacrifices_a_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        cauldron = CauldronOfEssence(owner=p1, controller=p1)
        fodder = Creature(
            name="Disposable Apprentice",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        set_board_state(
            game,
            0,
            battlefield=[cauldron, fodder],
            mana={ManaType.COLORLESS: 1, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        p1._script.append(fodder)
        ability = cauldron.get_activated_abilities()[0]

        assert ability.cost(game, cauldron) is True
        assert cauldron.is_tapped is True
        assert game.get_graveyard(p1).contains(fodder)
        assert not game.get_battlefield(p1).contains(fodder)
        assert p1.mana_pool.total() == 0

    def test_activation_cost_fails_outside_sorcery_speed(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        cauldron = CauldronOfEssence(owner=p1, controller=p1)
        fodder = Creature(
            name="Disposable Apprentice",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        set_board_state(
            game,
            0,
            battlefield=[cauldron, fodder],
            mana={ManaType.COLORLESS: 1, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        ability = cauldron.get_activated_abilities()[0]

        assert ability.cost(game, cauldron) is False
        assert cauldron.is_tapped is False
        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)
        assert p1.mana_pool.total() == 3

    def test_effect_returns_the_chosen_creature_card_from_your_graveyard_to_the_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cauldron = CauldronOfEssence(owner=p1, controller=p1)
        target = Creature(
            name="Recovered Bear",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        filler = CardImpl(name="Unreturned Notes", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[cauldron], graveyard=[target, filler])
        cauldron.chosen_targets = [target]
        ability = cauldron.get_activated_abilities()[0]

        ability.effect(game)

        assert game.get_battlefield(p1).contains(target)
        assert not game.get_graveyard(p1).contains(target)
        assert game.get_graveyard(p1).contains(filler)

