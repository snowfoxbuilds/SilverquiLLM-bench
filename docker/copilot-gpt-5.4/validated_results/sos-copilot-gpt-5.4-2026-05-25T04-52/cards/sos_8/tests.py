"""Tests for SOS 8 — Ascendant Dustspeaker."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_8.card_impl import AscendantDustspeaker
from benchmarks.sos.workspace.engine.card import CardImpl, Creature
from benchmarks.sos.workspace.engine.events import BeginningOfCombatTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestAscendantDustspeakerProperties:
    """Static card data should match the SOS 8 spec."""

    def test_is_flying_orc_cleric(self) -> None:
        card = AscendantDustspeaker(owner=None)
        assert isinstance(card, Creature)
        assert Keyword.FLYING in card.keywords
        assert "Orc" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = AscendantDustspeaker(owner=None)
        assert card.name == "Ascendant Dustspeaker"
        assert card.mana_cost == ManaCost.parse("{4}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 4


class TestAscendantDustspeakerEnterEffect:
    """The ETB text should put a +1/+1 counter on another creature you control."""

    def test_on_resolve_puts_a_counter_on_another_chosen_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        other = Creature(
            name="Ally Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[other])

        card = AscendantDustspeaker(owner=p1, controller=p1)
        card.chosen_targets = [other]
        card.on_resolve(game)

        assert other.plus_one_counters == 1

    def test_on_resolve_does_not_put_the_counter_on_itself(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AscendantDustspeaker(owner=p1, controller=p1)

        card.chosen_targets = [card]
        card.on_resolve(game)

        assert card.plus_one_counters == 0


class TestAscendantDustspeakerBeginningOfCombatTrigger:
    """The beginning-of-combat trigger should register and exile up to one card."""

    def test_registers_a_beginning_of_combat_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AscendantDustspeaker(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is BeginningOfCombatTriggeredEvent

    def test_does_not_trigger_on_an_opponents_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AscendantDustspeaker(owner=p1, controller=p1)
        game.active_player_index = 1

        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())

        assert game.stack.is_empty()

    def test_beginning_of_combat_trigger_may_exile_a_card_from_a_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = AscendantDustspeaker(owner=p1, controller=p1)
        target = CardImpl(name="Spent Spell", owner=p2, controller=p2)
        set_board_state(game, 1, graveyard=[target])

        p1._script.append(target)
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert not game.get_graveyard(p2).contains(target)
        assert game.get_exile(p2).contains(target)

    def test_beginning_of_combat_trigger_allows_no_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = AscendantDustspeaker(owner=p1, controller=p1)
        target = CardImpl(name="Leave Me", owner=p2, controller=p2)
        set_board_state(game, 1, graveyard=[target])

        p1._script.append(None)
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.get_graveyard(p2).contains(target)
        assert not game.get_exile(p2).contains(target)

