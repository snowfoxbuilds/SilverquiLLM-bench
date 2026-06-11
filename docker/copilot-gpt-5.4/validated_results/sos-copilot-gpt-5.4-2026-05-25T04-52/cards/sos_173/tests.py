"""Tests for SOS 173 — Ark of Hunger."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_173.card_impl import ArkOfHunger
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Artifact, CardImpl, Sorcery
from benchmarks.sos.workspace.engine.events import GraveyardLeavesTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestArkOfHungerProperties:
    """Static card data should match the SOS 173 spec."""

    def test_is_artifact(self) -> None:
        assert isinstance(ArkOfHunger(owner=None), Artifact)

    def test_name_and_mana_cost(self) -> None:
        card = ArkOfHunger(owner=None)

        assert card.name == "Ark of Hunger"
        assert card.mana_cost == ManaCost.parse("{2}{R}{W}")


class TestArkOfHungerGraveyardLeavesTrigger:
    """Ark of Hunger should punish opponents when your graveyard empties."""

    def test_registers_a_graveyard_leaves_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ArkOfHunger(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is GraveyardLeavesTriggeredEvent

    def test_one_graveyard_leaves_event_deals_one_to_each_opponent_and_gains_one_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ark = ArkOfHunger(owner=p1, controller=p1)
        first = CardImpl(name="First Note", owner=p1, controller=p1)
        second = CardImpl(name="Second Note", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ark])
        ark.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            GraveyardLeavesTriggeredEvent(
                player=p1,
                cards=[first, second],
                destination=Zone.EXILE,
            ),
        )

        assert len(game.stack) == 1

        resolve_top(game)

        assert p1.life == 21
        assert p2.life == 19

    def test_opponents_graveyard_leaving_does_not_trigger_it(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ark = ArkOfHunger(owner=p1, controller=p1)
        departed = CardImpl(name="Lost Lesson", owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[ark])
        ark.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            GraveyardLeavesTriggeredEvent(
                player=p2,
                cards=[departed],
                destination=Zone.HAND,
            ),
        )

        assert game.stack.is_empty()
        assert p1.life == 20
        assert p2.life == 20


class TestArkOfHungerActivatedAbility:
    """Ark of Hunger should mill a card and let you play it this turn."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = ArkOfHunger(owner=None).get_activated_abilities()

        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_taps_the_artifact_and_fails_if_already_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ark = ArkOfHunger(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ark])
        ability = ark.get_activated_abilities()[0]

        assert ability.cost(game, ark) is True
        assert ark.is_tapped is True
        assert ability.cost(game, ark) is False

    def test_effect_mills_the_top_card_and_grants_controller_only_graveyard_play_permission(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        top = Sorcery(
            name="Recovered Lesson",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{R}"),
        )
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(top)
        ark = ArkOfHunger(owner=p1, controller=p1)
        ability = ark.get_activated_abilities()[0]

        ability.effect(game)

        assert game.get_graveyard(p1).contains(top)
        assert not game.get_library(p1).contains(top)
        assert game.can_player_play_graveyard_card(p1, top) is True
        assert game.can_player_play_graveyard_card(p2, top) is False

    def test_milled_sorcery_can_be_cast_from_graveyard_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        top = Sorcery(
            name="Recovered Lesson",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{R}"),
        )
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(top)
        ark = ArkOfHunger(owner=p1, controller=p1)
        ability = ark.get_activated_abilities()[0]

        ability.effect(game)
        p1.mana_pool.add(ManaType.RED, 1)
        cast_spell_paid(game, p1, top, from_zone=Zone.GRAVEYARD)

        assert game.stack.peek().source is top
        assert not game.get_graveyard(p1).contains(top)
        assert game.can_player_play_graveyard_card(p1, top) is False
