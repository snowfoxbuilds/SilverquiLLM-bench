"""Cost-induced triggers wait above the completed activation (602.2, 603.3)."""

import pytest

from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature
from engine.events import CreatureDiesTriggeredEvent, EntersBattlefieldTriggeredEvent
from engine.game import draw_card, gain_life, sacrifice
from engine.game_state import GameState
from engine.intent_player import DeterministicPlayer
from engine.stack import resolve_top_of_stack
from engine.triggers import TriggerRegistration
from engine.types import Zone


@pytest.fixture
def game():
    return GameState([DeterministicPlayer("Alice"), DeterministicPlayer("Bob")])


def register_entry_trigger(game, controller, resolved):
    source = Creature(name="Watcher", owner=controller, controller=controller)
    game.trigger_manager.register(TriggerRegistration(
        event_type=EntersBattlefieldTriggeredEvent,
        condition=None,
        effect=lambda g: resolved.append(controller),
        source=source,
        controller=controller,
    ))
    return source


def test_trigger_waits_until_deferral_exits(game):
    resolved = []
    player = game.players[0]
    register_entry_trigger(game, player, resolved)

    with game.trigger_manager.defer_until_activated(game):
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
        assert game.stack.is_empty()
        assert resolved == []

    resolve_top_of_stack(game)
    assert resolved == [player]
    assert game.stack.is_empty()


def test_nested_deferrals_flush_once_at_outermost_exit(game):
    resolved = []
    player = game.players[0]
    register_entry_trigger(game, player, resolved)

    with game.trigger_manager.defer_until_activated(game):
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
        with game.trigger_manager.defer_until_activated(game):
            game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
            assert game.stack.is_empty()
        assert game.stack.is_empty()
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())

    for _ in range(3):
        resolve_top_of_stack(game)
    assert resolved == [player, player, player]
    assert game.stack.is_empty()
    with game.trigger_manager.defer_until_activated(game):
        pass
    assert game.stack.is_empty()


@pytest.mark.parametrize("active_index", [0, 1])
def test_deferred_batch_flushes_in_apnap_order(game, active_index):
    game.active_player_index = active_index
    active = game.active_player
    nonactive = game.players[1 - active_index]
    resolved = []
    register_entry_trigger(game, nonactive, resolved)
    register_entry_trigger(game, active, resolved)

    with game.trigger_manager.defer_until_activated(game):
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
        with game.trigger_manager.defer_until_activated(game):
            game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
        assert game.stack.is_empty()

    # APNAP applies to the whole pending batch, not separately to each event.
    for controller in (nonactive, nonactive, active, active):
        assert game.stack.peek().controller is controller
        resolve_top_of_stack(game)
    assert resolved == [nonactive, nonactive, active, active]
    assert game.stack.is_empty()


def test_exception_flushes_pending_triggers_and_resets_depth(game):
    resolved = []
    player = game.players[0]
    register_entry_trigger(game, player, resolved)

    with pytest.raises(RuntimeError, match="activation interrupted"):
        with game.trigger_manager.defer_until_activated(game):
            with game.trigger_manager.defer_until_activated(game):
                game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
                assert game.stack.is_empty()
                raise RuntimeError("activation interrupted")

    assert game.trigger_manager._deferral_depth == 0
    resolve_top_of_stack(game)
    assert resolved == [player]
    assert game.stack.is_empty()
    game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
    assert not game.stack.is_empty()
    resolve_top_of_stack(game)
    assert resolved == [player, player]
    assert game.stack.is_empty()


def test_trigger_outside_deferral_is_pushed_immediately(game):
    resolved = []
    player = game.players[0]
    source = register_entry_trigger(game, player, resolved)

    game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())

    assert game.stack.peek().source is source
    assert resolved == []
    resolve_top_of_stack(game)
    assert resolved == [player]
    assert game.stack.is_empty()


def test_sacrifice_cost_death_trigger_resolves_before_activated_draw(game):
    player = game.players[0]
    source = Creature(name="Sacrifice outlet", owner=player, controller=player,
                      base_power=1, base_toughness=1)
    victim = Creature(name="Death watcher", owner=player, controller=player,
                      base_power=1, base_toughness=1)
    for creature in (source, victim):
        game.get_battlefield(player).add(creature)
        creature.zone = Zone.BATTLEFIELD
    card = Creature(name="Drawn card", owner=player, controller=player)
    player.zones[Zone.LIBRARY].add(card)
    card.zone = Zone.LIBRARY
    game.trigger_manager.register(TriggerRegistration(
        event_type=CreatureDiesTriggeredEvent,
        condition=lambda g, event: event.creature is victim,
        effect=lambda g: gain_life(g, player, len(g.get_hand(player).get_all())),
        source=victim,
        controller=player,
    ))

    def pay_cost(g, ability_source):
        sacrifice(g, player, victim)
        return True

    ability = ActivatedAbilityInstance(
        source=source,
        controller=player,
        cost=pay_cost,
        effect=lambda g: draw_card(g, player),
    )
    starting_life = player.life

    activate_ability(game, player, ability)

    assert player.zones[Zone.GRAVEYARD].contains(victim)
    assert game.stack.peek().source is victim
    resolve_top_of_stack(game)
    assert player.life == starting_life
    assert game.get_hand(player).get_all() == []
    assert game.stack.peek().source is source
    resolve_top_of_stack(game)
    assert game.get_hand(player).get_all() == [card]
    assert player.life == starting_life
    assert game.stack.is_empty()
