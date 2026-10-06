"""Tests for engine/triggers.py — Triggered abilities system.

Verifies:
- EventType enum members and values.
- TriggerRegistration dataclass construction and fields.
- TriggerManager register/unregister/get_triggers/get_triggers_for_source/clear.
- TriggerManager.fire_event queues matching triggers, and settling
  (put_pending_on_stack) pushes their StackObjects (rule 117.5, 603.3).
- fire_event with non-matching event type → nothing pushed.
- Condition filtering: triggers only fire when condition returns True.
- Condition filtering: triggers do NOT fire when condition returns False.
- fire_event data parameter passed to condition.
- APNAP ordering: active player triggers pushed first (bottom), non-active on top.
- Registration-order preserved within same player.
- Unregister removes all triggers for a source (identity-based).
- Integration: GameState.trigger_manager is TriggerManager instance.
- ETB scenario: card enters battlefield → register_triggers → fire event → StackObject.
- Unregister on leave → fire event → nothing.
- Multiple triggers from different sources for same event → all pushed.
- Data dict forwarded to condition callable.
- Played at the table: a permanent's triggers work once it is cast or played
  and stop when it dies; targets are fixed as a trigger goes on the stack; a
  trigger belongs to whoever controls its source when it triggers; and
  Thousand-Year Storm's pending triggers keep the facts each captured.
"""
from __future__ import annotations

import pytest
from cards.fdn.fdn_9.card_impl import DazzlingAngel, DazzlingAngelAbility2
from cards.fdn.fdn_31.card_impl import BigfinBouncer
from cards.fdn.fdn_40.card_impl import HighFaeTrickster
from cards.fdn.fdn_76.card_impl import VengefulBloodwitch, VengefulBloodwitchAbility1
from cards.fdn.fdn_117.card_impl import AshrootAnimist, AshrootAnimistAbility2
from cards.fdn.fdn_126.card_impl import ZimoneParadoxSculptor, ZimoneParadoxSculptorAbility1
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_180.card_impl import PhyrexianArena, PhyrexianArenaAbility1
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_248.card_impl import ThousandYearStorm, ThousandYearStormAbility1
from cards.fdn.fdn_270.card_impl import TranquilCove, TranquilCoveAbility2
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from test_interface import Decision, ManaType, Phase, Side, Step, card, create_game, player
from test_utils import DeterministicPlayer

from engine.card import Creature
from engine.events import (
    AttacksTriggeredEvent,
    BeginningOfUpkeepTriggeredEvent,
    CreatureDiesTriggeredEvent,
    DealsDamageTriggeredEvent,
    EndOfTurnTriggeredEvent,
    EntersBattlefieldTriggeredEvent,
    GainsLifeTriggeredEvent,
    SpellCastTriggeredEvent,
)
from engine.game_state import GameState
from engine.stack import StackObject
from engine.triggers import TriggerManager, TriggerRegistration
from engine.types import Zone
from silverquillm.table import (
    Table,
    appears,
    copied,
    gains_control,
    life,
    moves,
    off_stack,
    on_stack,
    taps,
    untaps,
)

MAIN = (Phase.PRECOMBAT_MAIN, 0)


@pytest.fixture()
def players() -> list[DeterministicPlayer]:
    """Create two DeterministicPlayers."""
    return [DeterministicPlayer('Alice'), DeterministicPlayer('Bob')]

@pytest.fixture()
def game(players: list[DeterministicPlayer]) -> GameState:
    """Create a GameState with two players."""
    return GameState(players)

def _fire(game: GameState, event: object) -> None:
    """Fire *event* and settle, putting what it triggered on the stack, as the
    game does before a player would receive priority (rule 117.5)."""
    game.trigger_manager.fire_event(game, event)
    game.trigger_manager.put_pending_on_stack(game)

def _make_trigger(event_type: type, source: object, controller: DeterministicPlayer, *, condition=None, effect=None) -> TriggerRegistration:
    """Convenience to build a TriggerRegistration with sensible defaults."""
    return TriggerRegistration(event_type=event_type, condition=condition, effect=effect or (lambda g: None), source=source, controller=controller)


def _cast_and_resolve(t, seat, spell, *, then=()):
    """``seat`` casts ``spell``; both players pass and it resolves, causing ``then``."""
    t.act(seat, spell, then=[moves(spell, Zone.STACK)])
    t.pass_(seat)
    t.pass_(1 - seat, then=list(then))


def _attack_unblocked(t, attacker, damage_then):
    """Player 0 attacks with ``attacker`` on its next combat, unblocked."""
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, attacker, then=[taps(attacker)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)  # declares no blockers
    t.pass_(0)
    t.pass_(1, then=damage_then)


class TestTriggerRegistration:
    """TriggerRegistration dataclass stores all fields correctly."""

    def test_construction_with_all_fields(self, players: list[DeterministicPlayer]) -> None:
        """All five required fields are stored on construction."""
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        cond = lambda g, d: True
        effect = lambda g: None
        reg = TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=cond, effect=effect, source=source, controller=players[0])
        assert reg.event_type is EntersBattlefieldTriggeredEvent
        assert reg.condition is cond
        assert reg.effect is effect
        assert reg.source is source
        assert reg.controller is players[0]

    def test_condition_none_allowed(self, players: list[DeterministicPlayer]) -> None:
        """condition=None means 'always fires for event type'."""
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        reg = TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=None, effect=lambda g: None, source=source, controller=players[0])
        assert reg.condition is None

    def test_source_can_be_any_object(self, players: list[DeterministicPlayer]) -> None:
        """source field accepts any game object (not just Creature)."""
        source = object()
        reg = _make_trigger(SpellCastTriggeredEvent, source, players[0])
        assert reg.source is source

class TestTriggerManagerBasic:
    """TriggerManager register, unregister, get_triggers, get_triggers_for_source, clear."""

    def test_initial_empty(self) -> None:
        """A new TriggerManager has no triggers."""
        tm = TriggerManager()
        assert tm.get_triggers() == []

    def test_register_adds_trigger(self, players: list[DeterministicPlayer]) -> None:
        """register() should add the trigger to the internal list."""
        tm = TriggerManager()
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        reg = _make_trigger(EntersBattlefieldTriggeredEvent, source, players[0])
        tm.register(reg)
        assert len(tm.get_triggers()) == 1
        assert tm.get_triggers()[0] is reg

    def test_register_multiple_triggers(self, players: list[DeterministicPlayer]) -> None:
        """Multiple registrations should accumulate."""
        tm = TriggerManager()
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        r1 = _make_trigger(EntersBattlefieldTriggeredEvent, source, players[0])
        r2 = _make_trigger(CreatureDiesTriggeredEvent, source, players[0])
        tm.register(r1)
        tm.register(r2)
        assert len(tm.get_triggers()) == 2

    def test_get_triggers_returns_copy(self, players: list[DeterministicPlayer]) -> None:
        """get_triggers() should return a shallow copy — mutating it does not affect the manager."""
        tm = TriggerManager()
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        tm.register(_make_trigger(EntersBattlefieldTriggeredEvent, source, players[0]))
        copy = tm.get_triggers()
        copy.clear()
        assert len(tm.get_triggers()) == 1

class TestTriggerManagerUnregister:
    """Unregister removes all triggers for a given source object."""

    def test_unregister_removes_all_triggers_for_source(self, players: list[DeterministicPlayer]) -> None:
        """unregister(source) should remove every trigger whose source is that object."""
        tm = TriggerManager()
        bear = Creature(name='Bear', owner=players[0], controller=players[0])
        elf = Creature(name='Elf', owner=players[0], controller=players[0])
        tm.register(_make_trigger(EntersBattlefieldTriggeredEvent, bear, players[0]))
        tm.register(_make_trigger(CreatureDiesTriggeredEvent, bear, players[0]))
        tm.register(_make_trigger(AttacksTriggeredEvent, elf, players[0]))
        tm.unregister(bear)
        remaining = tm.get_triggers()
        assert len(remaining) == 1
        assert remaining[0].source is elf

    def test_unregister_is_identity_based(self, players: list[DeterministicPlayer]) -> None:
        """Unregister uses `is` (identity), not `==` (equality)."""
        tm = TriggerManager()
        bear1 = Creature(name='Bear', owner=players[0], controller=players[0])
        bear2 = Creature(name='Bear', owner=players[0], controller=players[0])
        tm.register(_make_trigger(EntersBattlefieldTriggeredEvent, bear1, players[0]))
        tm.register(_make_trigger(EntersBattlefieldTriggeredEvent, bear2, players[0]))
        tm.unregister(bear1)
        assert len(tm.get_triggers()) == 1
        assert tm.get_triggers()[0].source is bear2

    def test_unregister_nonexistent_source_is_noop(self) -> None:
        """Unregistering a source with no triggers should not raise."""
        tm = TriggerManager()
        tm.unregister(object())
        assert tm.get_triggers() == []

    def test_unregister_leaves_other_sources_intact(self, players: list[DeterministicPlayer]) -> None:
        """After unregister, triggers from other sources must remain."""
        tm = TriggerManager()
        bear = Creature(name='Bear', owner=players[0], controller=players[0])
        elf = Creature(name='Elf', owner=players[1], controller=players[1])
        tm.register(_make_trigger(EntersBattlefieldTriggeredEvent, bear, players[0]))
        tm.register(_make_trigger(EntersBattlefieldTriggeredEvent, elf, players[1]))
        tm.unregister(bear)
        assert len(tm.get_triggers()) == 1
        assert tm.get_triggers()[0].source is elf

class TestTriggerManagerGetTriggersForSource:
    """get_triggers_for_source filters by source identity."""

    def test_returns_only_matching_source(self, players: list[DeterministicPlayer]) -> None:
        tm = TriggerManager()
        bear = Creature(name='Bear', owner=players[0], controller=players[0])
        elf = Creature(name='Elf', owner=players[0], controller=players[0])
        tm.register(_make_trigger(EntersBattlefieldTriggeredEvent, bear, players[0]))
        tm.register(_make_trigger(CreatureDiesTriggeredEvent, bear, players[0]))
        tm.register(_make_trigger(AttacksTriggeredEvent, elf, players[0]))
        bear_triggers = tm.get_triggers_for_source(bear)
        assert len(bear_triggers) == 2
        assert all((t.source is bear for t in bear_triggers))

    def test_returns_empty_for_unknown_source(self) -> None:
        tm = TriggerManager()
        assert tm.get_triggers_for_source(object()) == []

class TestTriggerManagerClear:
    """clear() removes all triggers."""

    def test_clear_empties_all(self, players: list[DeterministicPlayer]) -> None:
        tm = TriggerManager()
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        tm.register(_make_trigger(EntersBattlefieldTriggeredEvent, source, players[0]))
        tm.register(_make_trigger(CreatureDiesTriggeredEvent, source, players[0]))
        tm.clear()
        assert tm.get_triggers() == []

class TestFireEvent:
    """fire_event pushes matching triggers onto the game stack."""

    def test_matching_trigger_pushes_stack_object(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """A registered ETB trigger fires when ENTERS_BATTLEFIELD is fired."""
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(_make_trigger(EntersBattlefieldTriggeredEvent, source, players[0]))
        _fire(game, EntersBattlefieldTriggeredEvent())
        assert not game.stack.is_empty()
        stack_obj = game.stack.peek()
        assert isinstance(stack_obj, StackObject)
        assert stack_obj.source is source
        assert stack_obj.controller is players[0]

    def test_stack_object_on_resolve_invokes_effect(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """The StackObject's on_resolve should call the trigger's effect callback."""
        calls: list[str] = []
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=None, effect=lambda g: calls.append('resolved'), source=source, controller=players[0]))
        _fire(game, EntersBattlefieldTriggeredEvent())
        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)
        assert calls == ['resolved']

    def test_non_matching_event_type_pushes_nothing(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Firing a different event type should not push any StackObject."""
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(_make_trigger(EntersBattlefieldTriggeredEvent, source, players[0]))
        _fire(game, CreatureDiesTriggeredEvent())
        assert game.stack.is_empty()

    def test_no_registered_triggers_pushes_nothing(self, game: GameState) -> None:
        """Firing an event with no registered triggers should leave the stack empty."""
        _fire(game, EntersBattlefieldTriggeredEvent())
        assert game.stack.is_empty()

    def test_condition_true_fires_trigger(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """When condition returns True, the trigger should fire."""
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=lambda g, event: True, effect=lambda g: None, source=source, controller=players[0]))
        _fire(game, DealsDamageTriggeredEvent(amount=3))
        assert not game.stack.is_empty()

    def test_condition_false_does_not_fire_trigger(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """When condition returns False, the trigger should NOT fire."""
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=lambda g, event: False, effect=lambda g: None, source=source, controller=players[0]))
        _fire(game, DealsDamageTriggeredEvent(amount=3))
        assert game.stack.is_empty()

    def test_condition_none_always_fires(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """A trigger with condition=None should always fire for matching event."""
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(_make_trigger(GainsLifeTriggeredEvent, source, players[0], condition=None))
        _fire(game, GainsLifeTriggeredEvent())
        assert not game.stack.is_empty()

    def test_condition_receives_data_dict(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """The condition callable should receive (game, event) where event is the typed event object."""
        received_args: list[tuple] = []

        def cond(g, e):
            received_args.append((g, e))
            return True
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=cond, effect=lambda g: None, source=source, controller=players[0]))
        event = DealsDamageTriggeredEvent(amount=5)
        _fire(game, event)
        assert len(received_args) == 1
        assert received_args[0][0] is game
        assert received_args[0][1] is event

    def test_fire_event_without_data_passes_empty_dict(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Calling fire_event passes the typed event object to condition."""
        received_data: list = []

        def cond(g, e):
            received_data.append(e)
            return True
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=cond, effect=lambda g: None, source=source, controller=players[0]))
        _fire(game, EntersBattlefieldTriggeredEvent())
        assert len(received_data) == 1
        assert isinstance(received_data[0], EntersBattlefieldTriggeredEvent)

    def test_multiple_triggers_same_event_all_pushed(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Three triggers for the same event → three StackObjects pushed."""
        sources = []
        for i in range(3):
            src = Creature(name=f'Bear{i}', owner=players[0], controller=players[0])
            sources.append(src)
            game.trigger_manager.register(_make_trigger(EntersBattlefieldTriggeredEvent, src, players[0]))
        _fire(game, EntersBattlefieldTriggeredEvent())
        assert len(game.stack.objects()) == 3

    def test_mixed_matching_and_nonmatching_only_matching_pushed(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Only triggers matching the fired event type should be pushed."""
        src_etb = Creature(name='ETB', owner=players[0], controller=players[0])
        src_die = Creature(name='DIE', owner=players[0], controller=players[0])
        game.trigger_manager.register(_make_trigger(EntersBattlefieldTriggeredEvent, src_etb, players[0]))
        game.trigger_manager.register(_make_trigger(CreatureDiesTriggeredEvent, src_die, players[0]))
        _fire(game, EntersBattlefieldTriggeredEvent())
        assert len(game.stack.objects()) == 1
        assert game.stack.peek().source is src_etb

    def test_condition_uses_data_to_filter(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Condition can inspect data dict to decide whether to fire."""
        source = Creature(name='Lifelinker', owner=players[0], controller=players[0])
        game.trigger_manager.register(TriggerRegistration(event_type=GainsLifeTriggeredEvent, condition=lambda g, event: event.amount >= 5, effect=lambda g: None, source=source, controller=players[0]))
        _fire(game, GainsLifeTriggeredEvent(amount=3))
        assert game.stack.is_empty()
        _fire(game, GainsLifeTriggeredEvent(amount=5))
        assert not game.stack.is_empty()

class TestAPNAPOrdering:
    """APNAP: Active player's triggers pushed first (bottom), non-active player's on top."""

    def test_active_player_triggers_at_bottom_non_active_on_top(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Active player's triggers end up at the bottom of the stack batch;
        non-active player's triggers are on top (resolve first)."""
        active = players[game.active_player_index]
        non_active = players[1 - game.active_player_index]
        active_src = Creature(name='A', owner=active, controller=active)
        nap_src = Creature(name='N', owner=non_active, controller=non_active)
        game.trigger_manager.register(_make_trigger(BeginningOfUpkeepTriggeredEvent, active_src, active))
        game.trigger_manager.register(_make_trigger(BeginningOfUpkeepTriggeredEvent, nap_src, non_active))
        _fire(game, BeginningOfUpkeepTriggeredEvent())
        stack_objs = game.stack.objects()
        assert len(stack_objs) == 2
        assert stack_objs[0].controller is non_active
        assert stack_objs[1].controller is active

    def test_apnap_ordering_regardless_of_registration_order(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """APNAP ordering should hold even if non-active player's trigger is registered first."""
        active = players[game.active_player_index]
        non_active = players[1 - game.active_player_index]
        active_src = Creature(name='A', owner=active, controller=active)
        nap_src = Creature(name='N', owner=non_active, controller=non_active)
        game.trigger_manager.register(_make_trigger(EndOfTurnTriggeredEvent, nap_src, non_active))
        game.trigger_manager.register(_make_trigger(EndOfTurnTriggeredEvent, active_src, active))
        _fire(game, EndOfTurnTriggeredEvent())
        stack_objs = game.stack.objects()
        assert len(stack_objs) == 2
        assert stack_objs[0].controller is non_active
        assert stack_objs[1].controller is active

    def test_registration_order_preserved_within_same_player(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Triggers from the same player maintain registration order (pushed in that order)."""
        active = players[game.active_player_index]
        src1 = Creature(name='First', owner=active, controller=active)
        src2 = Creature(name='Second', owner=active, controller=active)
        game.trigger_manager.register(_make_trigger(BeginningOfUpkeepTriggeredEvent, src1, active))
        game.trigger_manager.register(_make_trigger(BeginningOfUpkeepTriggeredEvent, src2, active))
        _fire(game, BeginningOfUpkeepTriggeredEvent())
        stack_objs = game.stack.objects()
        assert len(stack_objs) == 2
        assert stack_objs[0].source is src2
        assert stack_objs[1].source is src1

    def test_apnap_with_multiple_triggers_per_player(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """With multiple triggers per player, all active player's come before non-active's."""
        active = players[game.active_player_index]
        non_active = players[1 - game.active_player_index]
        a1 = Creature(name='A1', owner=active, controller=active)
        a2 = Creature(name='A2', owner=active, controller=active)
        n1 = Creature(name='N1', owner=non_active, controller=non_active)
        n2 = Creature(name='N2', owner=non_active, controller=non_active)
        game.trigger_manager.register(_make_trigger(EndOfTurnTriggeredEvent, a1, active))
        game.trigger_manager.register(_make_trigger(EndOfTurnTriggeredEvent, n1, non_active))
        game.trigger_manager.register(_make_trigger(EndOfTurnTriggeredEvent, a2, active))
        game.trigger_manager.register(_make_trigger(EndOfTurnTriggeredEvent, n2, non_active))
        _fire(game, EndOfTurnTriggeredEvent())
        stack_objs = game.stack.objects()
        assert len(stack_objs) == 4
        assert stack_objs[0].controller is non_active
        assert stack_objs[1].controller is non_active
        assert stack_objs[2].controller is active
        assert stack_objs[3].controller is active

class TestGameStateIntegration:
    """GameState has a trigger_manager attribute."""

    def test_game_state_has_trigger_manager(self, game: GameState) -> None:
        """GameState should have a trigger_manager attribute that is a TriggerManager."""
        assert hasattr(game, 'trigger_manager')
        assert isinstance(game.trigger_manager, TriggerManager)

    def test_trigger_manager_starts_empty(self, game: GameState) -> None:
        """A fresh GameState's trigger_manager should have no registered triggers."""
        assert game.trigger_manager.get_triggers() == []

    def test_trigger_manager_usable_via_game_state(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Triggers registered via game.trigger_manager should fire via game.trigger_manager."""
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(_make_trigger(EntersBattlefieldTriggeredEvent, source, players[0]))
        _fire(game, EntersBattlefieldTriggeredEvent())
        assert not game.stack.is_empty()

class TestETBIntegration:
    """End-to-end: card with ETB trigger → battlefield → fire event → StackObject."""

    def test_etb_trigger_full_flow(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Simulate: card enters battlefield, registers trigger, fire ETB, verify StackObject, resolve."""
        etb_resolved: list[str] = []

        class ETBCreature(Creature):

            def register_triggers(self, g: GameState) -> None:
                reg = TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=None, effect=lambda game: etb_resolved.append(self.name), source=self, controller=self.controller)
                g.trigger_manager.register(reg)
        p = players[0]
        card = ETBCreature(name='Ravenous Chupacabra', owner=p, controller=p)
        game.get_battlefield(p).add(card)
        card.register_triggers(game)
        _fire(game, EntersBattlefieldTriggeredEvent())
        assert not game.stack.is_empty()
        stack_obj = game.stack.pop()
        assert stack_obj.source is card
        assert stack_obj.controller is p
        stack_obj.on_resolve(game)
        assert etb_resolved == ['Ravenous Chupacabra']

    def test_etb_trigger_card_is_on_battlefield(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """The card should actually be on the battlefield when the trigger fires."""
        on_battlefield_during_fire: list[bool] = []

        class ETBCreature(Creature):

            def register_triggers(self, g: GameState) -> None:
                card_ref = self

                def check_condition(game_state, event):
                    bf = game_state.get_battlefield(card_ref.controller)
                    on_battlefield_during_fire.append(bf.contains(card_ref))
                    return True
                g.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=check_condition, effect=lambda g: None, source=self, controller=self.controller))
        p = players[0]
        card = ETBCreature(name='Chup', owner=p, controller=p)
        game.get_battlefield(p).add(card)
        card.register_triggers(game)
        _fire(game, EntersBattlefieldTriggeredEvent())
        assert on_battlefield_during_fire == [True]

    def test_unregister_on_leave_battlefield(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """When a source leaves the battlefield and is unregistered, firing does nothing."""

        class ETBCreature(Creature):

            def register_triggers(self, g: GameState) -> None:
                g.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=None, effect=lambda g: None, source=self, controller=self.controller))
        p = players[0]
        card = ETBCreature(name='Chupacabra', owner=p, controller=p)
        game.get_battlefield(p).add(card)
        card.register_triggers(game)
        assert len(game.trigger_manager.get_triggers()) == 1
        game.get_battlefield(p).remove(card)
        game.trigger_manager.unregister(card)
        assert len(game.trigger_manager.get_triggers()) == 0
        _fire(game, EntersBattlefieldTriggeredEvent())
        assert game.stack.is_empty()

    def test_etb_with_data_parameter(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """ETB trigger condition can inspect data dict to filter (e.g., which creature entered)."""
        fired: list[str] = []
        p = players[0]
        bear = Creature(name='Bear', owner=p, controller=p)
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=lambda g, event: event.creature is bear, effect=lambda g: fired.append('bear_entered'), source=bear, controller=p))
        other = Creature(name='Elf', owner=p, controller=p)
        _fire(game, EntersBattlefieldTriggeredEvent(creature=other))
        assert game.stack.is_empty()
        _fire(game, EntersBattlefieldTriggeredEvent(creature=bear))
        assert not game.stack.is_empty()

class TestAutoTriggerRegistrationViaResolve:
    """Verify triggers are automatically registered when a permanent enters
    the battlefield through the real casting/resolution pipeline — NOT by
    manually calling card.register_triggers(game).
    """

    def test_resolve_spell_auto_registers_triggers(self):
        """A creature cast and resolved has its triggered ability working: Dazzling
        Angel gains its controller life when another creature enters."""
        angel, lions = card(DazzlingAngel), card(SavannahLions)
        game = create_game(Side(hand=[angel, lions], mana={ManaType.WHITE: 4}), Side(), start=MAIN)
        t = Table(game)
        _cast_and_resolve(t, 0, angel, then=[moves(angel, Zone.BATTLEFIELD)])
        _cast_and_resolve(t, 0, lions, then=[moves(lions, Zone.BATTLEFIELD), on_stack(DazzlingAngelAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(DazzlingAngelAbility2), life(0, 21)])
        t.run()

    def test_play_land_auto_registers_triggers(self):
        """A land played has its triggered ability working: Tranquil Cove's enters
        trigger gains 1 life."""
        cove = card(TranquilCove)
        game = create_game(Side(hand=[cove]), Side(), start=MAIN)
        t = Table(game)
        t.act(0, cove, then=[moves(cove, Zone.BATTLEFIELD), taps(cove), on_stack(TranquilCoveAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(TranquilCoveAbility2), life(0, 21)])
        t.run()

class TestAutoTriggerUnregistrationViaLeave:
    """Verify triggers are automatically unregistered when a permanent
    leaves the battlefield through the real engine paths (e.g., SBA
    moving a creature to the graveyard) — NOT by manually calling
    game.trigger_manager.unregister(card).
    """

    def test_sba_lethal_damage_auto_unregisters_triggers(self):
        """A creature destroyed by lethal damage takes its triggered ability with it:
        Dazzling Angel no longer gains life when another creature enters."""
        angel, lions, first, second = card(DazzlingAngel), card(SavannahLions), card(BurstLightning), card(BurstLightning)
        game = create_game(
            Side(hand=[lions, first, second], battlefield=[angel], mana={ManaType.WHITE: 1, ManaType.RED: 2}),
            Side(),
            start=MAIN,
        )
        t = Table(game)
        t.act(0, first, choices=[angel], then=[moves(first, Zone.STACK)])
        t.act(0, second, choices=[angel], then=[moves(second, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(second, Zone.GRAVEYARD)])
        t.pass_(0)
        t.pass_(1, then=[moves(first, Zone.GRAVEYARD), moves(angel, Zone.GRAVEYARD)], note="4 damage destroys the 2/3 Angel")
        _cast_and_resolve(t, 0, lions, then=[moves(lions, Zone.BATTLEFIELD)])
        t.run()


def _attack_unblocked(t, attacker, damage_then):
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, attacker, then=[taps(attacker)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)  # declares no blockers
    t.pass_(0)
    t.pass_(1, then=damage_then)


def _employ(t, seat, employment, creature, *, then):
    """``seat`` casts Involuntary Employment on ``creature``; both players
    pass and it resolves, causing ``then``."""
    t.act(seat, employment, choices=[creature], then=[moves(employment, Zone.STACK)])
    t.pass_(seat)
    t.pass_(1 - seat, then=list(then))


def _steal(t, employment, creature):
    """Player 0 casts Involuntary Employment on player 1's ``creature``: it
    moves to player 0's side of the table, and player 0 gets a Treasure."""
    t.act(0, employment, choices=[creature], then=[moves(employment, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(employment, Zone.GRAVEYARD), gains_control(creature, 0), appears(0)])

    def test_sba_zero_toughness_auto_unregisters_triggers(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """A creature with 0 toughness is removed by SBA → triggers auto-unregistered."""
        from engine.state_based_actions import check_state_based_actions

        class ETBCreature(Creature):

            def register_triggers(self, g: GameState) -> None:
                g.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=None, effect=lambda game: None, source=self, controller=self.controller))
        p = players[0]
        card = ETBCreature(name='Doomed Construct', owner=p, controller=p, base_power=3, base_toughness=1)
        game.get_battlefield(p).add(card)
        card.register_triggers(game)
        assert len(game.trigger_manager.get_triggers_for_source(card)) == 1
        card.minus_one_counters = 1
        assert card.toughness == 0
        check_state_based_actions(game)
        assert not game.get_battlefield(p).contains(card)
        assert len(game.trigger_manager.get_triggers_for_source(card)) == 0
        _fire(game, EntersBattlefieldTriggeredEvent())
        assert game.stack.is_empty()


class TestTriggeredTargetChannel:
    """The optional TriggerRegistration.targeting hook: targets are chosen as the
    trigger is put on the stack, captured with an ActivationContext, and passed
    to effect(game, targets, context) — never re-selected at resolution."""

    def test_targets_and_context_captured_on_fire(self):
        """Targets are chosen as the trigger goes on the stack, never again at
        resolution: Zimone's trigger aims at one Lions, which dies in
        response, and the other Lions gets no counter (it deals 2 in combat,
        not 3)."""
        zimone, chosen, other = card(ZimoneParadoxSculptor), card(SavannahLions), card(SavannahLions)
        bolt, mountain = card(BurstLightning), card(Mountain)
        game = create_game(
            Side(battlefield=[zimone, chosen, other]),
            Side(hand=[bolt], battlefield=[mountain], library=[Plains]),
            start=MAIN,
        )
        t = Table(game)
        t.pass_(0, choices=[chosen])
        t.pass_(1, then=[on_stack(ZimoneParadoxSculptorAbility1, 0)], note="Zimone's trigger targets one Lions as it goes on the stack")
        t.pass_(0)
        t.act(1, mountain, then=[taps(mountain)])
        t.act(1, bolt, choices=[chosen], then=[moves(bolt, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), moves(chosen, Zone.GRAVEYARD)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(ZimoneParadoxSculptorAbility1)], note="its target is gone: the other Lions gets no counter")
        _attack_unblocked(t, other, [life(1, 18)])
        t.run()

    def test_controller_determined_at_fire_time(self):
        """A trigger is controlled by whoever controls its source when it triggers (CR
        603.3a): with Vengeful Bloodwitch stolen, player 0's creature dying
        drains player 1 for player 0."""
        witch, employment, lions, bolt = card(VengefulBloodwitch), card(InvoluntaryEmployment), card(SavannahLions), card(BurstLightning)
        game = create_game(
            Side(hand=[employment, bolt], battlefield=[lions], mana={ManaType.RED: 5}),
            Side(battlefield=[witch]),
            start=MAIN,
        )
        t = Table(game)
        _steal(t, employment, witch)
        t.act(0, bolt, choices=[lions], then=[moves(bolt, Zone.STACK)])
        t.pass_(0, choices=[player(1)])
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD), on_stack(VengefulBloodwitchAbility1, 0)],
                note="the Bloodwitch's trigger is player 0's, who controls it now")
        t.pass_(0)
        t.pass_(1, then=[off_stack(VengefulBloodwitchAbility1), life(1, 19), life(0, 21)])
        t.run()

    def test_required_target_none_not_put_on_stack(self):
        """Bigfin Bouncer enters with no creature an opponent controls: its
        required target has no legal choice, so its trigger is not put on the
        stack (rule 603.3c), and the Bouncer stays on the battlefield."""
        bouncer = card(BigfinBouncer)
        game = create_game(Side(hand=[bouncer], mana={ManaType.BLUE: 4}), Side(), start=MAIN)
        t = Table(game)
        _cast_and_resolve(t, 0, bouncer, then=[moves(bouncer, Zone.BATTLEFIELD)])
        t.run()

    def test_empty_list_target_still_put_on_stack(self):
        """An "up to" targeted trigger with no target chosen still goes on the stack:
        Zimone's beginning-of-combat trigger with none chosen."""
        zimone = card(ZimoneParadoxSculptor)
        game = create_game(Side(battlefield=[zimone]), Side(), start=MAIN)
        t = Table(game)
        t.pass_(0)
        t.pass_(1, then=[on_stack(ZimoneParadoxSculptorAbility1, 0)], note="no target chosen: the trigger still goes on the stack")
        t.pass_(0)
        t.pass_(1, then=[off_stack(ZimoneParadoxSculptorAbility1)])
        t.run()

    def test_untargeted_trigger_unchanged(self):
        """An untargeted trigger goes on the stack and resolves: Phyrexian Arena draws
        a card and loses 1 life at its controller's upkeep."""
        drawn = card(Plains)
        game = create_game(Side(battlefield=[PhyrexianArena], library=[drawn, Plains]), Side(), start=(Step.END, 1))
        t = Table(game)
        t.pass_(1)
        t.pass_(0, then=[on_stack(PhyrexianArenaAbility1, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(PhyrexianArenaAbility1), moves(drawn, Zone.HAND), life(0, 19)])
        t.run()

class TestFireTimeControllerPipeline:
    """The fire-time controller (source's current controller) is used
    consistently across the whole trigger pipeline: APNAP grouping, targeted and
    untargeted stack objects, target selection, and the ActivationContext."""

    def test_untargeted_trigger_uses_fire_time_controller(self):
        """An untargeted trigger of a stolen source is its new controller's: the stolen
        Dazzling Angel gains player 0 life."""
        angel, employment, lions, plains = card(DazzlingAngel), card(InvoluntaryEmployment), card(SavannahLions), card(Plains)
        game = create_game(
            Side(hand=[employment, lions], battlefield=[plains], mana={ManaType.RED: 4}),
            Side(battlefield=[angel]),
            start=MAIN,
        )
        t = Table(game)
        _steal(t, employment, angel)
        t.act(0, plains, then=[taps(plains)])
        _cast_and_resolve(t, 0, lions, then=[moves(lions, Zone.BATTLEFIELD), on_stack(DazzlingAngelAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(DazzlingAngelAbility2), life(0, 21)], note="player 0 controls the Angel: player 0 gains the life")
        t.run()

    def test_apnap_grouping_uses_fire_time_controller(self):
        """Simultaneous triggers are grouped by their controllers when they trigger:
        with one Dazzling Angel stolen, both Angels' triggers are player
        0's, and player 0 gains 2."""
        mine, theirs, employment = card(DazzlingAngel), card(DazzlingAngel), card(InvoluntaryEmployment)
        lions, plains = card(SavannahLions), card(Plains)
        game = create_game(
            Side(hand=[employment, lions], battlefield=[mine, plains], mana={ManaType.RED: 4}),
            Side(battlefield=[theirs]),
            start=MAIN,
        )
        t = Table(game)
        _steal(t, employment, theirs)
        t.act(0, plains, then=[taps(plains)])
        t.act(0, lions, then=[moves(lions, Zone.STACK)])
        t.pass_(0, choices=[DazzlingAngelAbility2, DazzlingAngelAbility2])
        t.pass_(1, then=[moves(lions, Zone.BATTLEFIELD), on_stack(DazzlingAngelAbility2, 0), on_stack(DazzlingAngelAbility2, 0)],
                note="both Angels are player 0's: player 0 orders both triggers")
        t.pass_(0)
        t.pass_(1, then=[off_stack(DazzlingAngelAbility2), life(0, 21)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(DazzlingAngelAbility2), life(0, 22)])
        t.run()

    def test_untargeted_controller_effect_uses_immutable_fire_time_controller(self):
        """A controller-sensitive untargeted effect uses the controller from
        when it triggered. On player 1's turn player 1 takes player 0's
        Dazzling Angel and casts the Lions, so the Angel triggers for player 1;
        player 0, with High Fae Trickster, takes the Angel back before the
        trigger resolves, and player 1 still gains the life."""
        angel, trickster = card(DazzlingAngel), card(HighFaeTrickster)
        mine, theirs, lions, plains = card(InvoluntaryEmployment), card(InvoluntaryEmployment), card(SavannahLions), card(Plains)
        mountains = [card(Mountain) for _ in range(4)]
        game = create_game(
            Side(hand=[mine], battlefield=[angel, trickster, *mountains]),
            Side(hand=[theirs, lions], battlefield=[plains], mana={ManaType.RED: 4}),
            start=(Phase.PRECOMBAT_MAIN, 1),
        )
        t = Table(game)
        _employ(t, 1, theirs, angel, then=[moves(theirs, Zone.GRAVEYARD), gains_control(angel, 1), appears(1)])
        t.act(1, plains, then=[taps(plains)])
        _cast_and_resolve(t, 1, lions, then=[moves(lions, Zone.BATTLEFIELD), on_stack(DazzlingAngelAbility2, 1)])
        t.pass_(1)
        for mountain in mountains:
            t.act(0, mountain, then=[taps(mountain)])
        _employ(t, 0, mine, angel, then=[moves(mine, Zone.GRAVEYARD), gains_control(angel, 0), appears(0)])
        t.pass_(1)
        t.pass_(0, then=[off_stack(DazzlingAngelAbility2), life(1, 21)], note="the Angel triggered for player 1")
        t.run()

    def test_one_arg_untargeted_effect_still_called_with_game_only(self):
        """A plain untargeted trigger resolves: Dazzling Angel gains 1 life."""
        lions = card(SavannahLions)
        game = create_game(Side(hand=[lions], battlefield=[DazzlingAngel], mana={ManaType.WHITE: 1}), Side(), start=MAIN)
        t = Table(game)
        _cast_and_resolve(t, 0, lions, then=[moves(lions, Zone.BATTLEFIELD), on_stack(DazzlingAngelAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(DazzlingAngelAbility2), life(0, 21)])
        t.run()

class TestTriggerCaptureChannel:
    """The `capture` channel fixes per-fire event state on each trigger's own
    StackObject (rule 603.3) and passes it — with the fire-time controller — to
    the effect, so a source's later firings never clobber an earlier trigger's
    state. This is the mechanism Thousand-Year Storm uses to correlate a trigger
    to its triggering spell + copy count."""

    def test_capture_runs_at_fire_time_and_threads_state_and_controller(self):
        """A trigger fixes what it needs when it triggers: Thousand-Year Storm's
        trigger for the second spell cast this turn makes one copy."""
        first, second = card(BurstLightning), card(BurstLightning)
        game = create_game(
            Side(hand=[first, second], battlefield=[ThousandYearStorm], mana={ManaType.RED: 2}), Side(), start=MAIN
        )
        t = Table(game)
        t.act(0, first, choices=[player(1)], then=[moves(first, Zone.STACK), on_stack(ThousandYearStormAbility1, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(ThousandYearStormAbility1)], note="no spell was cast before it: no copy")
        t.pass_(0)
        t.pass_(1, then=[moves(first, Zone.GRAVEYARD), life(1, 18)])
        t.act(0, second, choices=[player(1)], then=[moves(second, Zone.STACK), on_stack(ThousandYearStormAbility1, 0)])
        t.pass_(0, choices=[Decision.no()])
        t.pass_(1, then=[off_stack(ThousandYearStormAbility1), copied(BurstLightning, 0)], note="one spell before it: one copy")
        t.pass_(0)
        t.pass_(1, then=[off_stack(BurstLightning), life(1, 16)])
        t.pass_(0)
        t.pass_(1, then=[moves(second, Zone.GRAVEYARD), life(1, 14)])
        t.run()

    def test_capture_uses_immutable_fire_time_controller(self):
        """A trigger with captured state resolves for the controller from
        when it triggered. Player 1 takes player 0's Ashroot Animist and
        attacks with it and the Lions; player 0, with High Fae Trickster,
        takes the Animist back while its attack trigger waits, and the trigger
        still gives player 1's Lions +4/+4: player 0 takes 6."""
        ashroot, trickster = card(AshrootAnimist), card(HighFaeTrickster)
        mine, theirs, lions = card(InvoluntaryEmployment), card(InvoluntaryEmployment), card(SavannahLions)
        mountains = [card(Mountain) for _ in range(4)]
        game = create_game(
            Side(hand=[mine], battlefield=[ashroot, trickster, *mountains]),
            Side(hand=[theirs], battlefield=[lions], mana={ManaType.RED: 4}),
            start=(Phase.PRECOMBAT_MAIN, 1),
        )
        t = Table(game)
        _employ(t, 1, theirs, ashroot, then=[moves(theirs, Zone.GRAVEYARD), gains_control(ashroot, 1), appears(1)])
        t.pass_to(Step.DECLARE_ATTACKERS, 1)
        # The declared creatures also answer the trigger's target: an engine
        # that offers the Animist itself and rejects it gets the Lions first.
        t.act(1, branches=[[ashroot, lions], [lions, ashroot]],
              then=[taps(ashroot), taps(lions), on_stack(AshrootAnimistAbility2, 1)])
        t.pass_(1)
        for mountain in mountains:
            t.act(0, mountain, then=[taps(mountain)])
        _employ(t, 0, mine, ashroot, then=[moves(mine, Zone.GRAVEYARD), gains_control(ashroot, 0), untaps(ashroot), appears(0)])
        t.pass_(1, choices=[lions])
        t.pass_(0, then=[off_stack(AshrootAnimistAbility2)], note="the trigger is still player 1's: the Lions gets +4/+4")
        t.pass_(1)
        t.pass_(0)
        t.pass_(0)  # declares no blockers
        t.pass_(1)
        t.pass_(0, then=[life(0, 14)])
        t.run()

    def test_two_pending_captures_are_independent(self):
        """Two pending triggers of one source keep their own facts: Storm's triggers
        for the first and second spells, both on the stack at once, copy
        zero and one times."""
        first, second = card(BurstLightning), card(BurstLightning)
        game = create_game(
            Side(hand=[first, second], battlefield=[ThousandYearStorm], mana={ManaType.RED: 2}), Side(), start=MAIN
        )
        t = Table(game)
        t.act(0, first, choices=[player(1)], then=[moves(first, Zone.STACK), on_stack(ThousandYearStormAbility1, 0)])
        t.act(0, second, choices=[player(1)], then=[moves(second, Zone.STACK), on_stack(ThousandYearStormAbility1, 0)],
              note="two Storm triggers wait on the stack at once")
        t.pass_(0, choices=[Decision.no()])
        t.pass_(1, then=[off_stack(ThousandYearStormAbility1), copied(BurstLightning, 0)], note="the second cast's trigger copies once")
        t.pass_(0)
        t.pass_(1, then=[off_stack(BurstLightning), life(1, 18)])
        t.pass_(0)
        t.pass_(1, then=[moves(second, Zone.GRAVEYARD), life(1, 16)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(ThousandYearStormAbility1)], note="the first cast's trigger still makes no copy")
        t.pass_(0)
        t.pass_(1, then=[moves(first, Zone.GRAVEYARD), life(1, 14)])
        t.run()

