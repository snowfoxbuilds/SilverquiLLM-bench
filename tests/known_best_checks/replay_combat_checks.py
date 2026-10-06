"""The replay executor drives query-based combat declarations (ADR-017).

Run inside a ported workspace (Known-Best or smoke) by
``tests/test_known_best_replay_combat.py``: the module imports that
workspace's ``engine``, which the repo suite cannot import in-process
alongside other workspaces.
"""

from __future__ import annotations

import pytest
from engine.card import Creature
from engine.types import Zone as EZone

from silverquillm.replay.executor import ReplayExecutor, StepResult
from silverquillm.replay.types import GameObject, GameSnapshot, PlayerInfo, ReplayGame, TurnInfo, Zone

BF = 13


def _snapshot(step: str, objects: dict[int, GameObject]) -> GameSnapshot:
    snap = GameSnapshot(
        game_state_id=1,
        turn_info=TurnInfo(phase="Phase_Combat", step=step, turn_number=1, active_player=1),
    )
    snap.players = {1: PlayerInfo(seat_id=1), 2: PlayerInfo(seat_id=2)}
    snap.zones[BF] = Zone(zone_id=BF, type="ZoneType_Battlefield", owner_seat_id=0,
                          object_instance_ids=list(objects))
    snap.game_objects.update(objects)
    return snap


def _obj(iid: int, seat: int, **kw) -> GameObject:
    return GameObject(instance_id=iid, grp_id=0, type="GameObjectType_Card", zone_id=BF,
                      owner_seat_id=seat, controller_seat_id=seat,
                      visibility="Visibility_Public", **kw)


class _Board:
    """An executor over an empty replay with engine creatures bound to GRE ids."""

    def __init__(self) -> None:
        replay = ReplayGame(seat_id=1, opponent_seat_id=2)
        empty = GameSnapshot(game_state_id=0, turn_info=TurnInfo(phase="Phase_Main1", turn_number=1,
                                                                 active_player=1))
        empty.players = {1: PlayerInfo(seat_id=1), 2: PlayerInfo(seat_id=2)}
        replay.snapshots = [empty]
        self.ex = ReplayExecutor(replay=replay, card_id_map={}, registry=None, simulate=True)
        self.ex.initialize(empty)
        game = self.ex.game
        game.active_player_index = game.priority_player_index = 0

    def creature(self, iid: int, seat: int, power: int = 2, toughness: int = 2) -> Creature:
        player = self.ex.players[seat]
        card = Creature(name=f"C{iid}", owner=player, controller=player,
                        base_power=power, base_toughness=toughness)
        card.summoning_sick = False
        player.zones[EZone.BATTLEFIELD].add(card)
        self.ex._engine_cards[iid] = card
        return card

    def step(self, snap: GameSnapshot) -> StepResult:
        result = StepResult(snapshot_id=snap.game_state_id)
        self.ex._simulate_combat_transitions(snap, result)
        return result


def test_observed_attackers_are_declared_through_the_query_and_deal_damage():
    board = _Board()
    attacker = board.creature(100, 1)
    attacking = {100: _obj(100, 1, attack_state="AttackState_Attacking")}
    result = board.step(_snapshot("Step_DeclareAttack", attacking))
    assert result.engine_failures == []
    assert board.ex.game.combat_state.attackers == {attacker: board.ex.players[2]}
    assert board.step(_snapshot("Step_CombatDamage", attacking)).engine_failures == []
    assert board.ex.players[2].life == 18


def test_a_blocker_that_blocks_two_observed_attackers_blocks_both():
    board = _Board()
    first, second = board.creature(100, 1), board.creature(101, 1)
    blocker = board.creature(200, 2, toughness=5)
    blocker._max_attackers_blocked = 2
    attacking = {100: _obj(100, 1, attack_state="AttackState_Attacking"),
                 101: _obj(101, 1, attack_state="AttackState_Attacking")}
    assert board.step(_snapshot("Step_DeclareAttack", attacking)).engine_failures == []
    blocking = {**attacking, 200: _obj(200, 2, blocking_attacker_ids=[100, 101])}
    result = board.step(_snapshot("Step_DeclareBlock", blocking))
    assert result.engine_failures == []
    assert {id(a) for a in board.ex.game.combat_state.blockers[blocker]} == {id(first), id(second)}


def test_two_observed_blockers_on_one_attacker_both_block_it():
    board = _Board()
    attacker = board.creature(100, 1, power=4, toughness=4)
    left, right = board.creature(200, 2), board.creature(201, 2)
    attacking = {100: _obj(100, 1, attack_state="AttackState_Attacking")}
    assert board.step(_snapshot("Step_DeclareAttack", attacking)).engine_failures == []
    blocking = {**attacking,
                200: _obj(200, 2, blocking_attacker_ids=[100]),
                201: _obj(201, 2, blocking_attacker_ids=[100])}
    result = board.step(_snapshot("Step_DeclareBlock", blocking))
    assert result.engine_failures == []
    blockers = board.ex.game.combat_state.attacker_blockers[attacker]
    assert {id(b) for b in blockers} == {id(left), id(right)}


def test_no_blocks_declares_nothing_and_damage_still_happens():
    board = _Board()
    board.creature(100, 1)
    attacking = {100: _obj(100, 1, attack_state="AttackState_Attacking")}
    board.step(_snapshot("Step_DeclareAttack", attacking))
    result = board.step(_snapshot("Step_CombatDamage", attacking))
    assert result.engine_failures == [] and board.ex.game.combat_state.blockers == {}
    assert board.ex.players[2].life == 18


def test_a_rejected_declaration_is_an_engine_failure_and_restores_the_script():
    board = _Board()
    attacker = board.creature(100, 1)
    attacker.summoning_sick = True
    active = board.ex.players[1]
    before = active.pending_entries
    attacking = {100: _obj(100, 1, attack_state="AttackState_Attacking")}
    result = board.step(_snapshot("Step_DeclareAttack", attacking))
    assert any("declare_attackers_step" in f for f in result.engine_failures)
    assert board.ex.game.combat_state.attackers == {}
    assert active.pending_entries == before and not active.acting


@pytest.mark.parametrize("seat", [1, 2])
def test_the_declaring_players_own_script_is_restored(seat):
    from test_utils import pass_priority

    board = _Board()
    board.creature(100, 1)
    board.creature(200, 2)
    player = board.ex.players[seat]
    player.set_script([pass_priority(label="own")])
    attacking = {100: _obj(100, 1, attack_state="AttackState_Attacking")}
    board.step(_snapshot("Step_DeclareAttack", attacking))
    board.step(_snapshot("Step_DeclareBlock",
                         {**attacking, 200: _obj(200, 2, blocking_attacker_ids=[100])}))
    assert [e.describe() for e in player.pending_entries] == ["own"]


def test_two_blockers_divide_damage_as_the_replay_shows():
    board = _Board()
    board.creature(100, 1, power=4, toughness=4)
    frail, sturdy = board.creature(200, 2), board.creature(201, 2, toughness=5)
    attacking = {100: _obj(100, 1, attack_state="AttackState_Attacking")}
    assert board.step(_snapshot("Step_DeclareAttack", attacking)).engine_failures == []
    blocking = {**attacking,
                200: _obj(200, 2, blocking_attacker_ids=[100]),
                201: _obj(201, 2, blocking_attacker_ids=[100])}
    assert board.step(_snapshot("Step_DeclareBlock", blocking)).engine_failures == []
    damage = _snapshot("Step_CombatDamage", blocking)
    after = _snapshot("Step_CombatDamage", {k: v for k, v in blocking.items() if k != 200})
    after.game_state_id = 2
    board.ex.replay.snapshots = [damage, after]
    board.ex._gsid_index = {1: 0, 2: 1}
    result = board.step(damage)
    assert result.engine_failures == []
    assert sturdy.damage_marked == 0
    assert not board.ex.players[2].zones[EZone.BATTLEFIELD].contains(frail)
