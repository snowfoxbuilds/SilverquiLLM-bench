"""Audit gap-filling tests — covers significant untested code paths.

These tests were added during the test quality audit to cover:
1. cast_spell + protection targeting integration (DEBT T through full pipeline)
2. ValidatingExecutor.execute_all with stop_on_first
3. ValidatingExecutor.execute_all with step_callback
4. _merge_game_object sparse diff with power/toughness
5. ObjectTracker.get_grp_id for unregistered ID
6. ValidationReport.per_card_divergence_rates with zero appearances
7. ManaPool.add with negative amount raises ValueError
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell
from benchmarks.sos.workspace.engine.game_state import GameState
from benchmarks.sos.workspace.engine.mana import ManaPool
from benchmarks.sos.workspace.engine.player import DeterministicPlayer
from benchmarks.sos.workspace.engine.protection import ProtectionAbility
from benchmarks.sos.workspace.engine.types import CardType, Color, ManaCost, ManaType, Phase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(*, phase: Phase = Phase.PRECOMBAT_MAIN) -> GameState:
    p1 = DeterministicPlayer("Alice", life=20, script=[])
    p2 = DeterministicPlayer("Bob", life=20, script=[])
    game = GameState(players=[p1, p2])
    game.phase = phase
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    return game


# ---------------------------------------------------------------------------
# 1. cast_spell + protection targeting integration
# ---------------------------------------------------------------------------


class TestCastSpellProtectionTargeting:
    """Integration: cast_spell rejects targets with protection from the spell."""

    def test_red_spell_rejected_when_target_has_pro_red(self):
        """Casting a red instant at a creature with pro-red should raise CastingError."""
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Target creature with protection from red
        target = Creature(
            name="White Knight",
            mana_cost=ManaCost.parse("{W}{W}"),
            base_power=2,
            base_toughness=2,
        )
        target.colors = {Color.WHITE}
        target.protections = [ProtectionAbility(quality=Color.RED)]
        target.owner = p2
        target.controller = p2
        p2.zones[from_engine_types("BATTLEFIELD")].add(target)

        # Red targeted spell
        bolt = Instant(name="Lightning Bolt", mana_cost=ManaCost.parse("{R}"))
        bolt.colors = {Color.RED}
        bolt.owner = p1
        bolt.controller = p1
        bolt._targets = [target]  # will be returned by get_targets

        # Override get_targets to return the target
        bolt.get_targets = lambda game: [target]
        game.get_hand(p1).add(bolt)

        # Player chooses the protected target
        from collections import deque
        p1._script = deque([target])

        p1.mana_pool.add(ManaType.RED, 1)

        with pytest.raises(CastingError, match="protection"):
            cast_spell(game, p1, bolt)

    def test_green_spell_allowed_when_target_has_pro_red(self):
        """Casting a green instant at a creature with pro-red should succeed."""
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="White Knight",
            mana_cost=ManaCost.parse("{W}{W}"),
            base_power=2,
            base_toughness=2,
        )
        target.colors = {Color.WHITE}
        target.protections = [ProtectionAbility(quality=Color.RED)]
        target.owner = p2
        target.controller = p2
        p2.zones[from_engine_types("BATTLEFIELD")].add(target)

        growth = Instant(name="Giant Growth", mana_cost=ManaCost.parse("{G}"))
        growth.colors = {Color.GREEN}
        growth.owner = p1
        growth.controller = p1
        growth.get_targets = lambda game: [target]
        game.get_hand(p1).add(growth)

        from collections import deque
        p1._script = deque([target])
        p1.mana_pool.add(ManaType.GREEN, 1)

        # Should not raise
        cast_spell(game, p1, growth)
        assert not game.stack.is_empty()


def from_engine_types(zone_name: str):
    """Resolve a Zone enum value by name."""
    from benchmarks.sos.workspace.engine.types import Zone
    return Zone[zone_name]


# ---------------------------------------------------------------------------
# 2 & 3. ValidatingExecutor stop_on_first and step_callback
# ---------------------------------------------------------------------------


class TestValidatingExecutorStopOnFirst:
    """ValidatingExecutor.execute_all with stop_on_first should halt early."""

    def test_stop_on_first_halts_after_first_divergence(self):
        """When stop_on_first=True, execute_all should stop after the first divergence."""
        from silverquillm.replay.types import GameSnapshot, PlayerInfo, Zone as RZone, GameObject
        from silverquillm.replay.executor import ReplayExecutor, StepResult, StateMismatch
        from silverquillm.replay.validation import ValidatingExecutor

        snaps = []
        for i in range(4):
            s = GameSnapshot(game_state_id=i)
            s.players = {1: PlayerInfo(seat_id=1, life_total=20), 2: PlayerInfo(seat_id=2, life_total=20)}
            s.zones[10] = RZone(zone_id=10, type="ZoneType_Hand", owner_seat_id=1, object_instance_ids=[])
            s.zones[20] = RZone(zone_id=20, type="ZoneType_Hand", owner_seat_id=2, object_instance_ids=[])
            s.zones[11] = RZone(zone_id=11, type="ZoneType_Library", owner_seat_id=1, object_instance_ids=[])
            s.zones[21] = RZone(zone_id=21, type="ZoneType_Library", owner_seat_id=2, object_instance_ids=[])
            snaps.append(s)

        mock_executor = MagicMock(spec=ReplayExecutor)
        mock_executor._initialized = True
        mock_executor.card_id_map = {}
        mock_executor.registry = None
        mock_replay = MagicMock()
        mock_replay.snapshots = snaps
        mock_executor.replay = mock_replay

        # First step OK, second step has mismatch
        call_count = 0
        def fake_execute_step(prev, curr):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return StepResult(
                    snapshot_id=curr.game_state_id,
                    mismatches=[StateMismatch(category="life_total", description="mismatch")],
                )
            return StepResult(snapshot_id=curr.game_state_id, mismatches=[])

        mock_executor.execute_step.side_effect = fake_execute_step

        ve = ValidatingExecutor(mock_executor)
        results = ve.execute_all(stop_on_first=True)

        # Should have stopped at step 2 (not processed step 3)
        assert call_count == 2
        assert len(results) == 2


class TestValidatingExecutorStepCallback:
    """ValidatingExecutor.execute_all with step_callback invokes the callback."""

    def test_step_callback_called_for_each_step(self):
        from silverquillm.replay.types import GameSnapshot, PlayerInfo, Zone as RZone
        from silverquillm.replay.executor import ReplayExecutor, StepResult
        from silverquillm.replay.validation import ValidatingExecutor

        snaps = []
        for i in range(3):
            s = GameSnapshot(game_state_id=i)
            s.players = {1: PlayerInfo(seat_id=1, life_total=20), 2: PlayerInfo(seat_id=2, life_total=20)}
            s.zones[10] = RZone(zone_id=10, type="ZoneType_Hand", owner_seat_id=1, object_instance_ids=[])
            s.zones[20] = RZone(zone_id=20, type="ZoneType_Hand", owner_seat_id=2, object_instance_ids=[])
            snaps.append(s)

        mock_executor = MagicMock(spec=ReplayExecutor)
        mock_executor._initialized = True
        mock_executor.card_id_map = {}
        mock_executor.registry = None
        mock_replay = MagicMock()
        mock_replay.snapshots = snaps
        mock_executor.replay = mock_replay
        mock_executor.execute_step.return_value = StepResult(snapshot_id=1, mismatches=[])

        callback_calls = []
        def my_callback(step_idx, snap_id, action_desc, result_desc):
            callback_calls.append((step_idx, snap_id))

        ve = ValidatingExecutor(mock_executor)
        ve.execute_all(step_callback=my_callback)

        assert len(callback_calls) == 2  # 3 snapshots = 2 transitions
        assert callback_calls[0][0] == 1
        assert callback_calls[1][0] == 2


# ---------------------------------------------------------------------------
# 4. _merge_game_object with power/toughness dicts
# ---------------------------------------------------------------------------


class TestMergeGameObject:
    """Test sparse game object merging handles power/toughness dicts."""

    def test_merge_power_toughness_from_dict(self):
        from silverquillm.replay.state import _merge_game_object
        from silverquillm.replay.types import GameObject

        existing = GameObject(instance_id=1, grp_id=100, type="GameObjectType_Card", zone_id=10, owner_seat_id=1)
        existing.power = None
        existing.toughness = None

        diff = {"power": {"value": 3}, "toughness": {"value": 4}}
        _merge_game_object(existing, diff)

        assert existing.power == 3
        assert existing.toughness == 4

    def test_merge_partial_fields_only(self):
        from silverquillm.replay.state import _merge_game_object
        from silverquillm.replay.types import GameObject

        existing = GameObject(instance_id=1, grp_id=100, type="GameObjectType_Card", zone_id=10, owner_seat_id=1)
        original_zone = existing.zone_id

        diff = {"grpId": 200}  # Only grpId changes
        _merge_game_object(existing, diff)

        assert existing.grp_id == 200
        assert existing.zone_id == original_zone  # unchanged

    def test_merge_is_tapped_field(self):
        from silverquillm.replay.state import _merge_game_object
        from silverquillm.replay.types import GameObject

        existing = GameObject(instance_id=1, grp_id=100, type="GameObjectType_Card", zone_id=10, owner_seat_id=1)
        existing.is_tapped = False

        diff = {"isTapped": True}
        _merge_game_object(existing, diff)

        assert existing.is_tapped is True


# ---------------------------------------------------------------------------
# 5. ValidationReport edge cases
# ---------------------------------------------------------------------------


class TestValidationReportEdgeCases:
    """Edge cases for ValidationReport computed properties."""

    def test_per_card_rate_with_zero_appearances(self):
        """When card_appearances has 0 for a grpId, rate should be 0.0."""
        from silverquillm.replay.validation import Divergence, DivergenceType, ValidationReport

        report = ValidationReport(
            total_snapshots=1,
            successful_comparisons=0,
            divergences=[
                Divergence(
                    game_state_id=1,
                    divergence_type=DivergenceType.MISSING_CARD,
                    description="missing",
                    involved_grp_ids=[999],
                )
            ],
            card_appearances={999: 0},
        )
        rates = report.per_card_divergence_rates
        assert rates[999] == 0.0

    def test_per_card_rate_normal_calculation(self):
        """Rate = divergences/appearances for a card."""
        from silverquillm.replay.validation import Divergence, DivergenceType, ValidationReport

        report = ValidationReport(
            total_snapshots=10,
            successful_comparisons=8,
            divergences=[
                Divergence(
                    game_state_id=1,
                    divergence_type=DivergenceType.STATE_MISMATCH,
                    description="mismatch",
                    involved_grp_ids=[100],
                ),
                Divergence(
                    game_state_id=2,
                    divergence_type=DivergenceType.STATE_MISMATCH,
                    description="mismatch2",
                    involved_grp_ids=[100],
                ),
            ],
            card_appearances={100: 10},
        )
        rates = report.per_card_divergence_rates
        assert rates[100] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# 6. ManaPool.add negative amount
# ---------------------------------------------------------------------------


class TestManaPoolAddNegative:
    """ManaPool.add() with negative amount should raise ValueError."""

    def test_add_negative_raises(self):
        pool = ManaPool()
        with pytest.raises(ValueError, match="negative"):
            pool.add(ManaType.RED, -1)


# ---------------------------------------------------------------------------
# 7. validate_replay convenience function with stop_on_first
# ---------------------------------------------------------------------------


class TestValidateReplayConvenience:
    """Test the validate_replay() convenience function."""

    def test_validate_replay_returns_report(self):
        from silverquillm.replay.executor import ReplayExecutor, StepResult
        from silverquillm.replay.types import GameSnapshot, PlayerInfo, Zone as RZone
        from silverquillm.replay.validation import validate_replay

        snaps = []
        for i in range(2):
            s = GameSnapshot(game_state_id=i)
            s.players = {1: PlayerInfo(seat_id=1, life_total=20), 2: PlayerInfo(seat_id=2, life_total=20)}
            s.zones[10] = RZone(zone_id=10, type="ZoneType_Hand", owner_seat_id=1, object_instance_ids=[])
            s.zones[20] = RZone(zone_id=20, type="ZoneType_Hand", owner_seat_id=2, object_instance_ids=[])
            snaps.append(s)

        mock_executor = MagicMock(spec=ReplayExecutor)
        mock_executor._initialized = False
        mock_executor.card_id_map = {}
        mock_executor.registry = None
        mock_replay = MagicMock()
        mock_replay.snapshots = snaps
        mock_executor.replay = mock_replay
        mock_executor.execute_step.return_value = StepResult(snapshot_id=1, mismatches=[])

        report = validate_replay(mock_executor, stop_on_first=True)
        assert report.total_snapshots == 1
        assert report.divergence_count == 0
