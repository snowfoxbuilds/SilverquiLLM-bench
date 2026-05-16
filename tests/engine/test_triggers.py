"""Tests for engine/triggers.py — Triggered abilities system.

Verifies:
- EventType enum members and values.
- TriggerRegistration dataclass construction and fields.
- TriggerManager register/unregister/get_triggers/get_triggers_for_source/clear.
- TriggerManager.fire_event pushes StackObjects for matching triggers.
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
"""
from __future__ import annotations
import pytest
from engine.card import CardImpl, Creature
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.stack import StackObject
from engine.triggers import TriggerManager, TriggerRegistration
from engine.types import Zone
from engine.events import BeginningOfUpkeepTriggeredEvent, CreatureDiesTriggeredEvent, DealsDamageTriggeredEvent, EndOfTurnTriggeredEvent, EntersBattlefieldTriggeredEvent, GainsLifeTriggeredEvent

@pytest.fixture()
def players() -> list[DeterministicPlayer]:
    """Create two DeterministicPlayers."""
    return [DeterministicPlayer('Alice', script=[]), DeterministicPlayer('Bob', script=[])]

@pytest.fixture()
def game(players: list[DeterministicPlayer]) -> GameState:
    """Create a GameState with two players."""
    return GameState(players)

def _make_trigger(event_type: EventType, source: object, controller: DeterministicPlayer, *, condition=None, effect=None) -> TriggerRegistration:
    """Convenience to build a TriggerRegistration with sensible defaults."""
    return TriggerRegistration(event_type=event_type, condition=condition, effect=effect or (lambda g: None), source=source, controller=controller)

class TestEventType:
    """EventType enum covers all required game events."""

    @pytest.mark.parametrize('member, value', [('ENTERS_BATTLEFIELD', 'enters_battlefield'), ('LEAVES_BATTLEFIELD', 'leaves_battlefield'), ('DEALS_DAMAGE', 'deals_damage'), ('LOSES_LIFE', 'loses_life'), ('GAINS_LIFE', 'gains_life'), ('DRAWS_CARD', 'draws_card'), ('BEGINNING_OF_UPKEEP', 'beginning_of_upkeep'), ('BEGINNING_OF_COMBAT', 'beginning_of_combat'), ('END_OF_TURN', 'end_of_turn'), ('CREATURE_DIES', 'creature_dies'), ('SPELL_CAST', 'spell_cast'), ('ATTACKS', 'attacks'), ('BLOCKS', 'blocks')])
    def test_member_exists_with_value(self, member: str, value: str) -> None:
        """Each specified EventType member should exist with the expected string value."""
        assert hasattr(EventType, member)
        assert EventType[member].value == value

    def test_has_at_least_13_members(self) -> None:
        """EventType should have at least the 13 members from the spec."""
        assert len(EventType) >= 13

    def test_is_enum(self) -> None:
        """EventType members should be proper enum instances."""
        assert isinstance(EventType.ENTERS_BATTLEFIELD, EventType)

class TestTriggerRegistration:
    """TriggerRegistration dataclass stores all fields correctly."""

    def test_construction_with_all_fields(self, players: list[DeterministicPlayer]) -> None:
        """All five required fields are stored on construction."""
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        cond = lambda g, d: True
        effect = lambda g: None
        reg = TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=cond, effect=effect, source=source, controller=players[0])
        assert reg.event_type is EventType.ENTERS_BATTLEFIELD
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
        reg = _make_trigger(EventType.SPELL_CAST, source, players[0])
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
        reg = _make_trigger(EventType.ENTERS_BATTLEFIELD, source, players[0])
        tm.register(reg)
        assert len(tm.get_triggers()) == 1
        assert tm.get_triggers()[0] is reg

    def test_register_multiple_triggers(self, players: list[DeterministicPlayer]) -> None:
        """Multiple registrations should accumulate."""
        tm = TriggerManager()
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        r1 = _make_trigger(EventType.ENTERS_BATTLEFIELD, source, players[0])
        r2 = _make_trigger(EventType.CREATURE_DIES, source, players[0])
        tm.register(r1)
        tm.register(r2)
        assert len(tm.get_triggers()) == 2

    def test_get_triggers_returns_copy(self, players: list[DeterministicPlayer]) -> None:
        """get_triggers() should return a shallow copy — mutating it does not affect the manager."""
        tm = TriggerManager()
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        tm.register(_make_trigger(EventType.ENTERS_BATTLEFIELD, source, players[0]))
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
        tm.register(_make_trigger(EventType.ENTERS_BATTLEFIELD, bear, players[0]))
        tm.register(_make_trigger(EventType.CREATURE_DIES, bear, players[0]))
        tm.register(_make_trigger(EventType.ATTACKS, elf, players[0]))
        tm.unregister(bear)
        remaining = tm.get_triggers()
        assert len(remaining) == 1
        assert remaining[0].source is elf

    def test_unregister_is_identity_based(self, players: list[DeterministicPlayer]) -> None:
        """Unregister uses `is` (identity), not `==` (equality)."""
        tm = TriggerManager()
        bear1 = Creature(name='Bear', owner=players[0], controller=players[0])
        bear2 = Creature(name='Bear', owner=players[0], controller=players[0])
        tm.register(_make_trigger(EventType.ENTERS_BATTLEFIELD, bear1, players[0]))
        tm.register(_make_trigger(EventType.ENTERS_BATTLEFIELD, bear2, players[0]))
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
        tm.register(_make_trigger(EventType.ENTERS_BATTLEFIELD, bear, players[0]))
        tm.register(_make_trigger(EventType.ENTERS_BATTLEFIELD, elf, players[1]))
        tm.unregister(bear)
        assert len(tm.get_triggers()) == 1
        assert tm.get_triggers()[0].source is elf

class TestTriggerManagerGetTriggersForSource:
    """get_triggers_for_source filters by source identity."""

    def test_returns_only_matching_source(self, players: list[DeterministicPlayer]) -> None:
        tm = TriggerManager()
        bear = Creature(name='Bear', owner=players[0], controller=players[0])
        elf = Creature(name='Elf', owner=players[0], controller=players[0])
        tm.register(_make_trigger(EventType.ENTERS_BATTLEFIELD, bear, players[0]))
        tm.register(_make_trigger(EventType.CREATURE_DIES, bear, players[0]))
        tm.register(_make_trigger(EventType.ATTACKS, elf, players[0]))
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
        tm.register(_make_trigger(EventType.ENTERS_BATTLEFIELD, source, players[0]))
        tm.register(_make_trigger(EventType.CREATURE_DIES, source, players[0]))
        tm.clear()
        assert tm.get_triggers() == []

class TestFireEvent:
    """fire_event pushes matching triggers onto the game stack."""

    def test_matching_trigger_pushes_stack_object(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """A registered ETB trigger fires when ENTERS_BATTLEFIELD is fired."""
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(_make_trigger(EventType.ENTERS_BATTLEFIELD, source, players[0]))
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
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
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)
        assert calls == ['resolved']

    def test_non_matching_event_type_pushes_nothing(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Firing a different event type should not push any StackObject."""
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(_make_trigger(EventType.ENTERS_BATTLEFIELD, source, players[0]))
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent())
        assert game.stack.is_empty()

    def test_no_registered_triggers_pushes_nothing(self, game: GameState) -> None:
        """Firing an event with no registered triggers should leave the stack empty."""
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
        assert game.stack.is_empty()

    def test_condition_true_fires_trigger(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """When condition returns True, the trigger should fire."""
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=lambda g, event: True, effect=lambda g: None, source=source, controller=players[0]))
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(amount=3))
        assert not game.stack.is_empty()

    def test_condition_false_does_not_fire_trigger(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """When condition returns False, the trigger should NOT fire."""
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=lambda g, event: False, effect=lambda g: None, source=source, controller=players[0]))
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(amount=3))
        assert game.stack.is_empty()

    def test_condition_none_always_fires(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """A trigger with condition=None should always fire for matching event."""
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(_make_trigger(EventType.GAINS_LIFE, source, players[0], condition=None))
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent())
        assert not game.stack.is_empty()

    def test_condition_receives_data_dict(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """The condition callable should receive (game, data) where data is the dict passed to fire_event."""
        received_args: list[tuple] = []

        def cond(g, d):
            received_args.append((g, d))
            return True
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=cond, effect=lambda g: None, source=source, controller=players[0]))
        data = {'amount': 5, 'target': 'opponent'}
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent())
        assert len(received_args) == 1
        assert received_args[0][0] is game
        assert received_args[0][1] is data

    def test_fire_event_without_data_passes_empty_dict(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Calling fire_event without data should pass {} to condition."""
        received_data: list[dict] = []

        def cond(g, d):
            received_data.append(d)
            return True
        source = Creature(name='Bear', owner=players[0], controller=players[0])
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=cond, effect=lambda g: None, source=source, controller=players[0]))
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
        assert received_data == [{}]

    def test_multiple_triggers_same_event_all_pushed(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Three triggers for the same event → three StackObjects pushed."""
        sources = []
        for i in range(3):
            src = Creature(name=f'Bear{i}', owner=players[0], controller=players[0])
            sources.append(src)
            game.trigger_manager.register(_make_trigger(EventType.ENTERS_BATTLEFIELD, src, players[0]))
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
        assert len(game.stack.objects()) == 3

    def test_mixed_matching_and_nonmatching_only_matching_pushed(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Only triggers matching the fired event type should be pushed."""
        src_etb = Creature(name='ETB', owner=players[0], controller=players[0])
        src_die = Creature(name='DIE', owner=players[0], controller=players[0])
        game.trigger_manager.register(_make_trigger(EventType.ENTERS_BATTLEFIELD, src_etb, players[0]))
        game.trigger_manager.register(_make_trigger(EventType.CREATURE_DIES, src_die, players[0]))
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
        assert len(game.stack.objects()) == 1
        assert game.stack.peek().source is src_etb

    def test_condition_uses_data_to_filter(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Condition can inspect data dict to decide whether to fire."""
        source = Creature(name='Lifelinker', owner=players[0], controller=players[0])
        game.trigger_manager.register(TriggerRegistration(event_type=GainsLifeTriggeredEvent, condition=lambda g, event: event.amount >= 5, effect=lambda g: None, source=source, controller=players[0]))
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(amount=3))
        assert game.stack.is_empty()
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(amount=5))
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
        game.trigger_manager.register(_make_trigger(EventType.BEGINNING_OF_UPKEEP, active_src, active))
        game.trigger_manager.register(_make_trigger(EventType.BEGINNING_OF_UPKEEP, nap_src, non_active))
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
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
        game.trigger_manager.register(_make_trigger(EventType.END_OF_TURN, nap_src, non_active))
        game.trigger_manager.register(_make_trigger(EventType.END_OF_TURN, active_src, active))
        game.trigger_manager.fire_event(game, EndOfTurnTriggeredEvent())
        stack_objs = game.stack.objects()
        assert len(stack_objs) == 2
        assert stack_objs[0].controller is non_active
        assert stack_objs[1].controller is active

    def test_registration_order_preserved_within_same_player(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Triggers from the same player maintain registration order (pushed in that order)."""
        active = players[game.active_player_index]
        src1 = Creature(name='First', owner=active, controller=active)
        src2 = Creature(name='Second', owner=active, controller=active)
        game.trigger_manager.register(_make_trigger(EventType.BEGINNING_OF_UPKEEP, src1, active))
        game.trigger_manager.register(_make_trigger(EventType.BEGINNING_OF_UPKEEP, src2, active))
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
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
        game.trigger_manager.register(_make_trigger(EventType.END_OF_TURN, a1, active))
        game.trigger_manager.register(_make_trigger(EventType.END_OF_TURN, n1, non_active))
        game.trigger_manager.register(_make_trigger(EventType.END_OF_TURN, a2, active))
        game.trigger_manager.register(_make_trigger(EventType.END_OF_TURN, n2, non_active))
        game.trigger_manager.fire_event(game, EndOfTurnTriggeredEvent())
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
        game.trigger_manager.register(_make_trigger(EventType.ENTERS_BATTLEFIELD, source, players[0]))
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
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
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
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
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
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
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
        assert game.stack.is_empty()

    def test_etb_with_data_parameter(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """ETB trigger condition can inspect data dict to filter (e.g., which creature entered)."""
        fired: list[str] = []
        p = players[0]
        bear = Creature(name='Bear', owner=p, controller=p)
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=lambda g, event: event.creature is bear, effect=lambda g: fired.append('bear_entered'), source=bear, controller=p))
        other = Creature(name='Elf', owner=p, controller=p)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(creature=other))
        assert game.stack.is_empty()
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(creature=bear))
        assert not game.stack.is_empty()

class TestAutoTriggerRegistrationViaResolve:
    """Verify triggers are automatically registered when a permanent enters
    the battlefield through the real casting/resolution pipeline — NOT by
    manually calling card.register_triggers(game).
    """

    def test_resolve_spell_auto_registers_triggers(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Cast a creature with an ETB trigger, resolve it, fire event,
        verify the trigger fires and pushes a StackObject automatically.
        """
        from engine.casting import cast_spell
        from engine.types import ManaCost, ManaType, Phase
        etb_fired: list[str] = []

        class ETBBeast(Creature):

            def register_triggers(self, g: GameState) -> None:
                g.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=None, effect=lambda game: etb_fired.append(self.name), source=self, controller=self.controller))
        p = players[0]
        cost = ManaCost(generic=1)
        card = ETBBeast(name='Hollowhenge Beast', mana_cost=cost, owner=p, controller=p)
        game.get_hand(p).add(card)
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        p.mana_pool.add(ManaType.COLORLESS, 5)
        cast_spell(game, p, card)
        assert not game.stack.is_empty(), 'Spell should be on the stack after casting'
        spell_obj = game.stack.pop()
        spell_obj.on_resolve(game)
        assert game.get_battlefield(p).contains(card)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1, 'register_triggers should have been called automatically'
        assert triggers[0].event_type == EventType.ENTERS_BATTLEFIELD
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
        assert not game.stack.is_empty(), 'ETB trigger should push a StackObject'
        trigger_obj = game.stack.pop()
        assert trigger_obj.source is card
        assert trigger_obj.controller is p
        trigger_obj.on_resolve(game)
        assert etb_fired == ['Hollowhenge Beast']

    def test_play_land_auto_registers_triggers(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """Play a land with triggers via play_land, verify triggers are
        auto-registered without manual register_triggers call.
        """
        from engine.card import Land
        from engine.casting import play_land
        from engine.types import Phase
        etb_fired: list[str] = []

        class TriggerLand(Land):

            def register_triggers(self, g: GameState) -> None:
                g.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=None, effect=lambda game: etb_fired.append(self.name), source=self, controller=self.controller))
        p = players[0]
        land = TriggerLand(name='Valakut', owner=p, controller=p)
        game.get_hand(p).add(land)
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        p.land_plays_remaining = 1
        play_land(game, p, land)
        assert game.get_battlefield(p).contains(land)
        triggers = game.trigger_manager.get_triggers_for_source(land)
        assert len(triggers) == 1
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
        assert not game.stack.is_empty()

class TestAutoTriggerUnregistrationViaLeave:
    """Verify triggers are automatically unregistered when a permanent
    leaves the battlefield through the real engine paths (e.g., SBA
    moving a creature to the graveyard) — NOT by manually calling
    game.trigger_manager.unregister(card).
    """

    def test_sba_lethal_damage_auto_unregisters_triggers(self, game: GameState, players: list[DeterministicPlayer]) -> None:
        """A creature with triggers takes lethal damage → SBA moves it to
        graveyard → triggers should be automatically unregistered.
        """
        from engine.casting import cast_spell
        from engine.state_based_actions import check_state_based_actions
        from engine.types import ManaCost, ManaType, Phase

        class ETBCreature(Creature):

            def register_triggers(self, g: GameState) -> None:
                g.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=None, effect=lambda game: None, source=self, controller=self.controller))
        p = players[0]
        cost = ManaCost(generic=1)
        card = ETBCreature(name='Fragile Golem', mana_cost=cost, owner=p, controller=p, base_power=2, base_toughness=2)
        game.get_hand(p).add(card)
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        p.mana_pool.add(ManaType.COLORLESS, 5)
        cast_spell(game, p, card)
        spell_obj = game.stack.pop()
        spell_obj.on_resolve(game)
        assert len(game.trigger_manager.get_triggers_for_source(card)) == 1
        assert game.get_battlefield(p).contains(card)
        card.damage_marked = 5
        check_state_based_actions(game)
        assert not game.get_battlefield(p).contains(card)
        assert len(game.trigger_manager.get_triggers_for_source(card)) == 0
        assert len(game.trigger_manager.get_triggers()) == 0
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
        assert game.stack.is_empty(), 'Trigger should have been auto-unregistered when creature left battlefield'

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
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent())
        assert game.stack.is_empty()
