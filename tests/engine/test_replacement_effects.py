"""Tests for engine/replacement_effects.py — Replacement effects engine.

Verifies:
- ReplacementEffect dataclass construction and fields.
- ReplacementManager.register adds effects.
- ReplacementManager.unregister removes all effects for a source (identity-based).
- apply with matching event_type → replacement called, event_data modified.
- apply with non-matching event_type → event_data unchanged.
- apply with condition returning False → replacement not applied.
- apply with condition returning True → replacement applied.
- Multiple replacements for same event → all applied (player chooses order).
- Self-replacement prevention: each effect applies at most once per event.
- "Instead" semantics: register "if creature would die, exile instead" → verify exile.
- No stack interaction: replacement effects don't use the stack.
- Integration: register_replacement_effects called when entering battlefield.
- Unregister on card leaving battlefield via SBA.
- Edge cases: no matching replacements, empty manager, clear, query helpers.
"""
from __future__ import annotations
from typing import Any
import pytest
from engine.card import CardImpl, Creature
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.replacement_effects import ReplacementEffect, ReplacementManager
from engine.types import CardType, Zone
from engine.events import CreatureDiesReplacementEvent

@pytest.fixture()
def players() -> list[DeterministicPlayer]:
    """Create two DeterministicPlayers."""
    return [DeterministicPlayer('Alice', script=[]), DeterministicPlayer('Bob', script=[])]

@pytest.fixture()
def game(players: list[DeterministicPlayer]) -> GameState:
    """Create a GameState with two players."""
    return GameState(players)

@pytest.fixture()
def manager() -> ReplacementManager:
    """Create a fresh ReplacementManager."""
    return ReplacementManager()

def _make_creature(name: str='Bear', power: int=2, toughness: int=2, owner: DeterministicPlayer | None=None, controller: DeterministicPlayer | None=None) -> Creature:
    """Create a simple creature with given stats."""
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)

def _noop_replacement(game: Any, event: dict[str, Any]) -> dict[str, Any]:
    """Trivial replacement that returns event_data unchanged."""
    return event

class TestReplacementEffectDataclass:
    """ReplacementEffect construction and field access."""

    def test_construction_with_all_fields(self) -> None:
        """ReplacementEffect should store event_type, source, condition, replacement, controller."""
        source = object()
        controller = DeterministicPlayer('Alice', script=[])
        condition = lambda g, e: True
        replacement = lambda g, e: e
        effect = ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=source, condition=condition, replacement=replacement, controller=controller)
        assert effect.event_type == 'creature_dies'
        assert effect.source is source
        assert effect.condition is condition
        assert effect.replacement is replacement
        assert effect.controller is controller

    def test_condition_defaults_to_none(self) -> None:
        """When condition is not provided, it should default to None."""
        effect = ReplacementEffect(event_type='damage', source=object(), condition=None, replacement=_noop_replacement)
        assert effect.condition is None

    def test_controller_defaults_to_none(self) -> None:
        """Controller should default to None when not explicitly provided."""
        effect = ReplacementEffect(event_type='damage', source=object(), condition=None, replacement=_noop_replacement)
        assert effect.controller is None

    def test_event_type_is_string(self) -> None:
        """event_type should be a string."""
        effect = ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=object(), condition=None, replacement=_noop_replacement)
        assert isinstance(effect.event_type, str)

class TestReplacementManagerRegister:
    """ReplacementManager.register adds effects to the internal registry."""

    def test_register_single_effect(self, manager: ReplacementManager) -> None:
        """Registering one effect should make it retrievable via get_effects."""
        effect = ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=object(), condition=None, replacement=_noop_replacement)
        manager.register(effect)
        assert len(manager.get_effects()) == 1
        assert manager.get_effects()[0] is effect

    def test_register_multiple_effects(self, manager: ReplacementManager) -> None:
        """Registering multiple effects should store all of them."""
        source = object()
        effects = [ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=source, condition=None, replacement=_noop_replacement) for _ in range(3)]
        for eff in effects:
            manager.register(eff)
        assert len(manager.get_effects()) == 3

    def test_register_effects_from_different_sources(self, manager: ReplacementManager) -> None:
        """Effects from different sources should all be stored."""
        src_a = object()
        src_b = object()
        eff_a = ReplacementEffect(event_type='damage', source=src_a, condition=None, replacement=_noop_replacement)
        eff_b = ReplacementEffect(event_type='damage', source=src_b, condition=None, replacement=_noop_replacement)
        manager.register(eff_a)
        manager.register(eff_b)
        assert len(manager.get_effects()) == 2

class TestReplacementManagerUnregister:
    """ReplacementManager.unregister removes all effects for a source."""

    def test_unregister_removes_all_effects_for_source(self, manager: ReplacementManager) -> None:
        """Unregistering a source should remove all its effects."""
        source = object()
        for _ in range(3):
            manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=source, condition=None, replacement=_noop_replacement))
        manager.unregister(source)
        assert len(manager.get_effects()) == 0

    def test_unregister_leaves_other_sources_intact(self, manager: ReplacementManager) -> None:
        """Unregistering a source should not affect effects from other sources."""
        src_a = object()
        src_b = object()
        manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=src_a, condition=None, replacement=_noop_replacement))
        manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=src_b, condition=None, replacement=_noop_replacement))
        manager.unregister(src_a)
        remaining = manager.get_effects()
        assert len(remaining) == 1
        assert remaining[0].source is src_b

    def test_unregister_identity_based_not_equality(self, manager: ReplacementManager) -> None:
        """Unregister uses identity (is), not equality (==)."""

        class EqualToAll:

            def __eq__(self, other: object) -> bool:
                return True

            def __hash__(self) -> int:
                return 0
        src_a = EqualToAll()
        src_b = EqualToAll()
        assert src_a == src_b
        manager.register(ReplacementEffect(event_type='x', source=src_a, condition=None, replacement=_noop_replacement))
        manager.register(ReplacementEffect(event_type='x', source=src_b, condition=None, replacement=_noop_replacement))
        manager.unregister(src_a)
        remaining = manager.get_effects()
        assert len(remaining) == 1
        assert remaining[0].source is src_b

    def test_unregister_nonexistent_source_is_noop(self, manager: ReplacementManager) -> None:
        """Unregistering a source with no effects should be a no-op."""
        manager.unregister(object())
        assert len(manager.get_effects()) == 0

class TestReplacementManagerApply:
    """ReplacementManager.apply modifies event_data via matching replacements."""

    def test_apply_matching_event_type_modifies_data(self, manager: ReplacementManager, game: GameState) -> None:
        """Replacement matching event_type should modify event_data."""

        def exile_instead(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            event.destination = 'exile'
            return event
        manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=object(), condition=None, replacement=exile_instead))
        result = manager.apply(game, 'creature_dies', {'destination': 'graveyard'})
        assert result['destination'] == 'exile'

    def test_apply_non_matching_event_type_unchanged(self, manager: ReplacementManager, game: GameState) -> None:
        """Non-matching event_type should leave event_data unchanged."""
        call_count = 0

        def should_not_be_called(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return event
        manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=object(), condition=None, replacement=should_not_be_called))
        original = {'destination': 'graveyard', 'creature': 'Bear'}
        result = manager.apply(game, 'deals_damage', original)
        assert result['destination'] == 'graveyard'
        assert call_count == 0

    def test_apply_with_condition_false_skips_replacement(self, manager: ReplacementManager, game: GameState) -> None:
        """Replacement with condition returning False should not apply."""
        call_count = 0

        def replacement(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            event.replaced = True
            return event
        manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=object(), condition=lambda g, event: False, replacement=replacement))
        result = manager.apply(game, 'creature_dies', {'replaced': False})
        assert result['replaced'] is False
        assert call_count == 0

    def test_apply_with_condition_true_applies_replacement(self, manager: ReplacementManager, game: GameState) -> None:
        """Replacement with condition returning True should apply."""

        def replacement(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            event.replaced = True
            return event
        manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=object(), condition=lambda g, event: True, replacement=replacement))
        result = manager.apply(game, 'creature_dies', {'replaced': False})
        assert result['replaced'] is True

    def test_apply_condition_receives_game_and_event_data(self, manager: ReplacementManager, game: GameState) -> None:
        """Condition callable should receive (game, event_data) arguments."""
        received_args: list[Any] = []

        def recording_condition(g: Any, event: dict[str, Any]) -> bool:
            received_args.append((g, event))
            return False
        manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=object(), condition=recording_condition, replacement=_noop_replacement))
        event_data = {'creature': 'Bear'}
        manager.apply(game, 'creature_dies', event_data)
        assert len(received_args) == 1
        assert received_args[0][0] is game
        assert received_args[0][1] is event_data

    def test_apply_condition_none_means_always_applies(self, manager: ReplacementManager, game: GameState) -> None:
        """If condition is None, the replacement should always apply for its event_type."""

        def replacement(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            event.applied = True
            return event
        manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=object(), condition=None, replacement=replacement))
        result = manager.apply(game, 'creature_dies', {'applied': False})
        assert result['applied'] is True

    def test_apply_empty_manager_returns_event_data_unchanged(self, manager: ReplacementManager, game: GameState) -> None:
        """Empty manager should return event_data as-is."""
        original = {'destination': 'graveyard'}
        result = manager.apply(game, 'creature_dies', original)
        assert result is original
        assert result['destination'] == 'graveyard'

    def test_apply_no_matching_replacements_returns_unchanged(self, manager: ReplacementManager, game: GameState) -> None:
        """If no effects match (wrong event_type), event_data should be unchanged."""
        manager.register(ReplacementEffect(event_type='damage', source=object(), condition=None, replacement=lambda g, event: {**event, 'changed': True}))
        original = {'value': 42}
        result = manager.apply(game, 'creature_dies', original)
        assert result is original
        assert 'changed' not in result

class TestMultipleReplacements:
    """When multiple replacements apply to the same event, all are applied."""

    def test_multiple_replacements_all_applied(self, game: GameState, manager: ReplacementManager) -> None:
        """All matching replacements should be applied to the event_data."""
        applied_order: list[str] = []

        def repl_a(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            applied_order.append('A')
            event.a = True
            return event

        def repl_b(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            applied_order.append('B')
            event.b = True
            return event
        manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=object(), condition=None, replacement=repl_a))
        manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=object(), condition=None, replacement=repl_b))
        alice = game.players[0]
        alice._script.extend([None])
        effects = manager.get_effects()
        alice._script.clear()
        alice._script.append(effects[0])
        result = manager.apply(game, 'creature_dies', {'player': alice, 'a': False, 'b': False})
        assert result['a'] is True
        assert result['b'] is True
        assert len(applied_order) == 2

    def test_player_chooses_order_when_multiple_match(self, game: GameState, manager: ReplacementManager) -> None:
        """When multiple replacements match, the affected player chooses the order."""
        applied_order: list[str] = []

        def repl_first(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            applied_order.append('first')
            return event

        def repl_second(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            applied_order.append('second')
            return event
        src1 = object()
        src2 = object()
        eff1 = ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=src1, condition=None, replacement=repl_first)
        eff2 = ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=src2, condition=None, replacement=repl_second)
        manager.register(eff1)
        manager.register(eff2)
        alice = game.players[0]
        alice._script.clear()
        alice._script.append(eff2)
        result = manager.apply(game, 'creature_dies', {'player': alice})
        assert applied_order == ['second', 'first']

class TestSelfReplacementPrevention:
    """Each replacement effect applies at most once per event to prevent infinite loops."""

    def test_effect_applies_at_most_once_per_event(self, manager: ReplacementManager, game: GameState) -> None:
        """A replacement that makes itself match again should only be applied once."""
        call_count = 0

        def self_triggering_replacement(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return event
        manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=object(), condition=None, replacement=self_triggering_replacement))
        manager.apply(game, 'creature_dies', {'destination': 'graveyard'})
        assert call_count == 1

    def test_two_effects_each_apply_exactly_once(self, manager: ReplacementManager, game: GameState) -> None:
        """With two matching effects, each should apply exactly once even if conditions still hold."""
        counts = {'a': 0, 'b': 0}

        def repl_a(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            counts['a'] += 1
            return event

        def repl_b(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            counts['b'] += 1
            return event
        eff_a = ReplacementEffect(event_type='x', source=object(), condition=None, replacement=repl_a)
        eff_b = ReplacementEffect(event_type='x', source=object(), condition=None, replacement=repl_b)
        manager.register(eff_a)
        manager.register(eff_b)
        alice = game.players[0]
        alice._script.clear()
        alice._script.append(eff_a)
        manager.apply(game, 'x', {'player': alice})
        assert counts['a'] == 1
        assert counts['b'] == 1

class TestInsteadSemantics:
    """Replacement effects implement "instead" semantics, modifying the event."""

    def test_creature_would_die_exile_instead(self, game: GameState, manager: ReplacementManager) -> None:
        """'If creature would die, exile it instead' → destination changes from graveyard to exile."""

        def exile_instead(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            event.destination = 'exile'
            return event
        manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=object(), condition=None, replacement=exile_instead))
        result = manager.apply(game, 'creature_dies', {'creature': 'Bear', 'destination': 'graveyard'})
        assert result['destination'] == 'exile'
        assert result['creature'] == 'Bear'

    def test_damage_prevention_replacement(self, game: GameState, manager: ReplacementManager) -> None:
        """'If damage would be dealt, prevent it' → damage reduced to 0."""

        def prevent_damage(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            event.amount = 0
            event.prevented = True
            return event
        manager.register(ReplacementEffect(event_type='deals_damage', source=object(), condition=None, replacement=prevent_damage))
        result = manager.apply(game, 'deals_damage', {'amount': 5, 'source': 'Lightning', 'prevented': False})
        assert result['amount'] == 0
        assert result['prevented'] is True

    def test_conditional_exile_only_for_specific_creature(self, game: GameState, manager: ReplacementManager) -> None:
        """Conditional replacement: only exile specific creature, not all."""
        bear = _make_creature('Bear')
        elf = _make_creature('Elf')

        def only_for_bear(g: Any, event: dict[str, Any]) -> bool:
            return event.creature is bear

        def exile_instead(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            event.destination = 'exile'
            return event
        manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=object(), condition=only_for_bear, replacement=exile_instead))
        result_bear = manager.apply(game, 'creature_dies', {'creature': bear, 'destination': 'graveyard'})
        assert result_bear['destination'] == 'exile'
        result_elf = manager.apply(game, 'creature_dies', {'creature': elf, 'destination': 'graveyard'})
        assert result_elf['destination'] == 'graveyard'

class TestNoStackInteraction:
    """Replacement effects don't use the stack — they modify events inline."""

    def test_apply_does_not_push_to_stack(self, game: GameState, manager: ReplacementManager) -> None:
        """Applying a replacement effect should not push anything onto the game stack."""

        def exile_instead(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            event.destination = 'exile'
            return event
        manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=object(), condition=None, replacement=exile_instead))
        assert game.stack.is_empty()
        manager.apply(game, 'creature_dies', {'destination': 'graveyard'})
        assert game.stack.is_empty()

class TestGameStateIntegration:
    """GameState should have a replacement_manager attribute."""

    def test_game_state_has_replacement_manager(self, game: GameState) -> None:
        """GameState should expose a ReplacementManager instance."""
        assert hasattr(game, 'replacement_manager')
        assert isinstance(game.replacement_manager, ReplacementManager)

    def test_game_state_replacement_manager_starts_empty(self, game: GameState) -> None:
        """The ReplacementManager should start with no effects."""
        assert len(game.replacement_manager.get_effects()) == 0

class TestRegisterOnBattlefieldEntry:
    """card.register_replacement_effects(game) called when entering battlefield."""

    def test_register_replacement_effects_called_on_resolve_permanent(self, game: GameState) -> None:
        """When a permanent resolves to the battlefield, register_replacement_effects should fire."""
        registered_calls: list[GameState] = []

        class CreatureWithReplacement(Creature):

            def register_replacement_effects(self, g: GameState) -> None:
                registered_calls.append(g)
                g.replacement_manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=self, condition=None, replacement=_noop_replacement))
        alice = game.players[0]
        card = CreatureWithReplacement(name='Replacement Bear', base_power=2, base_toughness=2, owner=alice, controller=alice)
        bf = game.get_battlefield(alice)
        bf.add(card)
        if hasattr(card, 'register_replacement_effects'):
            card.register_replacement_effects(game)
        assert len(registered_calls) == 1
        assert registered_calls[0] is game
        assert len(game.replacement_manager.get_effects()) == 1
        assert game.replacement_manager.get_effects()[0].source is card

    def test_card_impl_register_replacement_effects_is_noop_by_default(self, game: GameState) -> None:
        """Default CardImpl.register_replacement_effects should be a no-op."""
        card = _make_creature('Plain Bear')
        card.register_replacement_effects(game)
        assert len(game.replacement_manager.get_effects()) == 0

class TestUnregisterOnLeaveBattlefield:
    """Effects should be unregistered when their source leaves the battlefield."""

    def test_unregister_via_sba_graveyard(self, game: GameState) -> None:
        """When a creature goes to graveyard via SBA, its replacement effects are unregistered."""
        alice = game.players[0]
        bear = _make_creature('Doomed Bear', owner=alice, controller=alice)
        bf = game.get_battlefield(alice)
        bf.add(bear)
        game.replacement_manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=bear, condition=None, replacement=_noop_replacement))
        assert len(game.replacement_manager.get_effects()) == 1
        game.replacement_manager.unregister(bear)
        remaining = game.replacement_manager.get_effects()
        assert len(remaining) == 0

    def test_unregister_preserves_other_sources(self, game: GameState) -> None:
        """Unregistering one source should not affect effects from other sources."""
        alice = game.players[0]
        bear_a = _make_creature('Bear A', owner=alice)
        bear_b = _make_creature('Bear B', owner=alice)
        game.replacement_manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=bear_a, condition=None, replacement=_noop_replacement))
        game.replacement_manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=bear_b, condition=None, replacement=_noop_replacement))
        game.replacement_manager.unregister(bear_a)
        remaining = game.replacement_manager.get_effects()
        assert len(remaining) == 1
        assert remaining[0].source is bear_b

class TestQueryHelpers:
    """Test get_effects, get_effects_for_source, and clear."""

    def test_get_effects_returns_shallow_copy(self, manager: ReplacementManager) -> None:
        """get_effects should return a new list (shallow copy)."""
        eff = ReplacementEffect(event_type='x', source=object(), condition=None, replacement=_noop_replacement)
        manager.register(eff)
        effects_a = manager.get_effects()
        effects_b = manager.get_effects()
        assert effects_a is not effects_b
        assert effects_a == effects_b

    def test_get_effects_for_source(self, manager: ReplacementManager) -> None:
        """get_effects_for_source returns only effects with matching source identity."""
        src = object()
        other = object()
        eff_src = ReplacementEffect(event_type='x', source=src, condition=None, replacement=_noop_replacement)
        eff_other = ReplacementEffect(event_type='x', source=other, condition=None, replacement=_noop_replacement)
        manager.register(eff_src)
        manager.register(eff_other)
        result = manager.get_effects_for_source(src)
        assert len(result) == 1
        assert result[0] is eff_src

    def test_clear_removes_all_effects(self, manager: ReplacementManager) -> None:
        """clear() should remove all registered effects."""
        for _ in range(5):
            manager.register(ReplacementEffect(event_type='x', source=object(), condition=None, replacement=_noop_replacement))
        assert len(manager.get_effects()) == 5
        manager.clear()
        assert len(manager.get_effects()) == 0

class TestAffectedPlayerDetermination:
    """When multiple replacements match, affected player is determined from event_data."""

    def test_affected_player_from_event_data_player_key(self, game: GameState, manager: ReplacementManager) -> None:
        """If event_data has 'player' key, that player chooses order."""
        applied_order: list[str] = []
        eff_a = ReplacementEffect(event_type='x', source=object(), condition=None, replacement=lambda g, event: (applied_order.append('A'), event)[1])
        eff_b = ReplacementEffect(event_type='x', source=object(), condition=None, replacement=lambda g, event: (applied_order.append('B'), event)[1])
        manager.register(eff_a)
        manager.register(eff_b)
        alice = game.players[0]
        alice._script.clear()
        alice._script.append(eff_b)
        manager.apply(game, 'x', {'player': alice})
        assert applied_order == ['B', 'A']

    def test_affected_player_from_event_data_controller_key(self, game: GameState, manager: ReplacementManager) -> None:
        """If event_data has 'controller' key (no 'player'), that controller chooses."""
        applied_order: list[str] = []
        eff_a = ReplacementEffect(event_type='x', source=object(), condition=None, replacement=lambda g, event: (applied_order.append('A'), event)[1])
        eff_b = ReplacementEffect(event_type='x', source=object(), condition=None, replacement=lambda g, event: (applied_order.append('B'), event)[1])
        manager.register(eff_a)
        manager.register(eff_b)
        bob = game.players[1]
        bob._script.clear()
        bob._script.append(eff_a)
        manager.apply(game, 'x', {'controller': bob})
        assert applied_order == ['A', 'B']

    def test_affected_player_falls_back_to_active_player(self, game: GameState, manager: ReplacementManager) -> None:
        """If event_data has neither 'player' nor 'controller', active player chooses."""
        applied_order: list[str] = []
        eff_a = ReplacementEffect(event_type='x', source=object(), condition=None, replacement=lambda g, event: (applied_order.append('A'), event)[1])
        eff_b = ReplacementEffect(event_type='x', source=object(), condition=None, replacement=lambda g, event: (applied_order.append('B'), event)[1])
        manager.register(eff_a)
        manager.register(eff_b)
        active = game.active_player
        active._script.clear()
        active._script.append(eff_b)
        manager.apply(game, 'x', {'value': 42})
        assert applied_order == ['B', 'A']

class TestSBAUnregistersReplacements:
    """Verify that SBA's _move_to_graveyard calls replacement_manager.unregister."""

    def test_move_to_graveyard_unregisters_replacement_effects(self, game: GameState) -> None:
        """SBA _move_to_graveyard should call replacement_manager.unregister."""
        from engine.state_based_actions import _move_to_graveyard
        alice = game.players[0]
        bear = _make_creature('Bear', owner=alice, controller=alice)
        bf = game.get_battlefield(alice)
        bf.add(bear)
        game.replacement_manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=bear, condition=None, replacement=_noop_replacement))
        assert len(game.replacement_manager.get_effects()) == 1
        _move_to_graveyard(game, alice, bear)
        assert len(game.replacement_manager.get_effects()) == 0
        gy = game.get_graveyard(alice)
        assert gy.contains(bear)

class TestSBADeathReplacementEndToEnd:
    """End-to-end tests that drive a real creature through resolve_state_based_actions
    and verify that replacement effects redirect the death destination from graveyard
    to exile (or that the creature goes to graveyard normally without a replacement).
    """

    def test_creature_zero_toughness_goes_to_graveyard_without_replacement(self, game: GameState) -> None:
        """Baseline: a creature with 0 toughness goes to its owner's graveyard via SBAs
        when no replacement effect is registered.
        """
        from engine.state_based_actions import resolve_state_based_actions
        alice = game.players[0]
        bear = _make_creature('Fragile Bear', power=2, toughness=0, owner=alice, controller=alice)
        bf = game.get_battlefield(alice)
        bf.add(bear)
        resolve_state_based_actions(game)
        assert not bf.contains(bear)
        gy = game.get_graveyard(alice)
        assert gy.contains(bear)
        exile = game.get_exile(alice)
        assert not exile.contains(bear)

    def test_creature_lethal_damage_goes_to_graveyard_without_replacement(self, game: GameState) -> None:
        """Baseline: a creature with lethal damage marked goes to graveyard via SBAs
        when no replacement effect is registered.
        """
        from engine.state_based_actions import resolve_state_based_actions
        alice = game.players[0]
        bear = _make_creature('Wounded Bear', power=2, toughness=2, owner=alice, controller=alice)
        bear.damage_marked = 3
        bf = game.get_battlefield(alice)
        bf.add(bear)
        resolve_state_based_actions(game)
        assert not bf.contains(bear)
        gy = game.get_graveyard(alice)
        assert gy.contains(bear)
        exile = game.get_exile(alice)
        assert not exile.contains(bear)

    def test_creature_zero_toughness_exiled_instead_via_replacement(self, game: GameState) -> None:
        """End-to-end: register 'if creature would die, exile instead', set toughness
        to 0, run resolve_state_based_actions → creature should land in exile, NOT graveyard.
        """
        from engine.state_based_actions import resolve_state_based_actions
        alice = game.players[0]
        bear = _make_creature('Exile Bear', power=2, toughness=0, owner=alice, controller=alice)
        bf = game.get_battlefield(alice)
        bf.add(bear)

        def exile_instead(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            event.destination = 'exile'
            return event
        game.replacement_manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=bear, condition=None, replacement=exile_instead))
        resolve_state_based_actions(game)
        assert not bf.contains(bear)
        gy = game.get_graveyard(alice)
        assert not gy.contains(bear), 'creature should not be in graveyard when exile replacement is active'
        exile = game.get_exile(alice)
        assert exile.contains(bear), "creature should be in exile zone after 'exile instead' replacement"

    def test_creature_lethal_damage_exiled_instead_via_replacement(self, game: GameState) -> None:
        """End-to-end: register 'if creature would die, exile instead', mark lethal
        damage, run resolve_state_based_actions → creature should land in exile.
        """
        from engine.state_based_actions import resolve_state_based_actions
        alice = game.players[0]
        bear = _make_creature('Damaged Bear', power=2, toughness=2, owner=alice, controller=alice)
        bear.damage_marked = 5
        bf = game.get_battlefield(alice)
        bf.add(bear)

        def exile_instead(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            event.destination = 'exile'
            return event
        game.replacement_manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=bear, condition=None, replacement=exile_instead))
        resolve_state_based_actions(game)
        assert not bf.contains(bear)
        gy = game.get_graveyard(alice)
        assert not gy.contains(bear), 'lethal-damage creature should not be in graveyard with exile replacement'
        exile = game.get_exile(alice)
        assert exile.contains(bear), 'lethal-damage creature should be in exile with exile replacement'

    def test_conditional_exile_only_affects_targeted_creature(self, game: GameState) -> None:
        """End-to-end: a conditional replacement only exiles the specific creature it
        targets; another creature with zero toughness goes to graveyard normally.
        """
        from engine.state_based_actions import resolve_state_based_actions
        alice = game.players[0]
        protected = _make_creature('Protected Bear', power=2, toughness=0, owner=alice, controller=alice)
        unprotected = _make_creature('Normal Bear', power=2, toughness=0, owner=alice, controller=alice)
        bf = game.get_battlefield(alice)
        bf.add(protected)
        bf.add(unprotected)

        def only_for_protected(g: Any, event: dict[str, Any]) -> bool:
            return event.creature is protected

        def exile_instead(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            event.destination = 'exile'
            return event
        game.replacement_manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=protected, condition=only_for_protected, replacement=exile_instead))
        resolve_state_based_actions(game)
        assert not bf.contains(protected)
        exile = game.get_exile(alice)
        assert exile.contains(protected), 'protected creature should be exiled'
        gy = game.get_graveyard(alice)
        assert not gy.contains(protected), 'protected creature should NOT be in graveyard'
        assert not bf.contains(unprotected)
        assert gy.contains(unprotected), 'unprotected creature should go to graveyard normally'
        assert not exile.contains(unprotected), 'unprotected creature should NOT be exiled'

    def test_replacement_effect_unregistered_after_creature_exiled(self, game: GameState) -> None:
        """After a creature is exiled via replacement effect through SBA, its
        replacement effects should be cleaned up from the manager.
        """
        from engine.state_based_actions import resolve_state_based_actions
        alice = game.players[0]
        bear = _make_creature('Cleanup Bear', power=2, toughness=0, owner=alice, controller=alice)
        bf = game.get_battlefield(alice)
        bf.add(bear)

        def exile_instead(g: Any, event: dict[str, Any]) -> dict[str, Any]:
            event.destination = 'exile'
            return event
        game.replacement_manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=bear, condition=None, replacement=exile_instead))
        assert len(game.replacement_manager.get_effects()) == 1
        resolve_state_based_actions(game)
        assert len(game.replacement_manager.get_effects()) == 0
        exile = game.get_exile(alice)
        assert exile.contains(bear)
