"""The replay executor drives query-based combat declarations (ADR-017).

Run inside a ported workspace (Known-Best or smoke) by
``tests/test_known_best_replay_combat.py``: the module imports that
workspace's ``engine``, which the repo suite cannot import in-process
alongside other workspaces.
"""

from __future__ import annotations

import pytest
from engine.card import Creature
from engine.types import Keyword
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

    def creature(self, iid: int, seat: int, power: int = 2, toughness: int = 2,
                 keywords: Keyword | None = None, name: str | None = None) -> Creature:
        player = self.ex.players[seat]
        card = Creature(name=name or f"C{iid}", owner=player, controller=player,
                        base_power=power, base_toughness=toughness, keywords=keywords)
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


def _combat(board: _Board, attackers: dict[int, list[int]], died: set[int] = frozenset(),
            step: str = "Step_CombatDamage") -> StepResult:
    """Declare *attackers* (attacker GRE id -> its blockers' ids), then run the
    damage step with the replay showing *died* leave the battlefield."""
    attacking = {a: _obj(a, 1, attack_state="AttackState_Attacking") for a in attackers}
    assert board.step(_snapshot("Step_DeclareAttack", attacking)).engine_failures == []
    blocking = {**attacking, **{b: _obj(b, 2, blocking_attacker_ids=[a])
                                for a, bs in attackers.items() for b in bs}}
    assert board.step(_snapshot("Step_DeclareBlock", blocking)).engine_failures == []
    damage = _snapshot(step, blocking)
    after = _snapshot(step, {k: v for k, v in blocking.items() if k not in died})
    after.game_state_id = 2
    board.ex.replay.snapshots = [damage, after]
    board.ex._gsid_index = {1: 0, 2: 1}
    return board.step(damage)


def _alive(board: _Board, card: Creature) -> bool:
    return board.ex.players[2].zones[EZone.BATTLEFIELD].contains(card)


def test_a_trampler_whose_blockers_both_survive_assigns_all_its_damage_to_them():
    board = _Board()
    board.creature(100, 1, power=6, toughness=6, keywords=Keyword.TRAMPLE)
    left, right = board.creature(200, 2, toughness=8), board.creature(201, 2, toughness=8)
    result = _combat(board, {100: [200, 201]})
    assert result.engine_failures == []
    assert left.damage_marked + right.damage_marked == 6
    assert _alive(board, left) and _alive(board, right) and board.ex.players[2].life == 20


def test_a_trampler_with_one_blocker_dying_keeps_its_survivor_below_lethal():
    board = _Board()
    board.creature(100, 1, power=6, toughness=6, keywords=Keyword.TRAMPLE)
    frail, sturdy = board.creature(200, 2), board.creature(201, 2, toughness=8)
    result = _combat(board, {100: [200, 201]}, died={200})
    assert result.engine_failures == []
    assert not _alive(board, frail) and _alive(board, sturdy)
    assert board.ex.players[2].life == 20


def test_same_name_tramplers_each_divide_their_own_damage():
    board = _Board()
    board.creature(100, 1, power=6, toughness=6, keywords=Keyword.TRAMPLE, name="Wurm")
    board.creature(101, 1, power=6, toughness=6, keywords=Keyword.TRAMPLE, name="Wurm")
    blockers = [board.creature(b, 2) for b in (200, 201, 202, 203)]
    result = _combat(board, {100: [200, 201], 101: [202, 203]}, died={200, 201, 202, 203})
    assert result.engine_failures == []
    assert not any(_alive(board, b) for b in blockers)
    assert board.ex.players[2].life == 20 - 2 * 2


def test_a_trampler_whose_blockers_all_die_tramples_the_rest_over():
    board = _Board()
    board.creature(100, 1, power=6, toughness=6, keywords=Keyword.TRAMPLE)
    left, right = board.creature(200, 2), board.creature(201, 2)
    result = _combat(board, {100: [200, 201]}, died={200, 201})
    assert result.engine_failures == []
    assert not _alive(board, left) and not _alive(board, right)
    assert board.ex.players[2].life == 18


def test_an_unobserved_division_is_still_legal_and_deterministic():
    board = _Board()
    board.creature(100, 1, power=6, toughness=6, keywords=Keyword.TRAMPLE)
    left, right = board.creature(200, 2, toughness=3), board.creature(201, 2, toughness=3)
    result = _combat(board, {100: [200, 201]})
    assert result.engine_failures == []
    assert not _alive(board, left) and not _alive(board, right)
    assert board.ex.players[2].life == 20


def test_deathtouch_assigns_one_lethal_damage_to_each_dying_blocker():
    board = _Board()
    board.creature(100, 1, power=3, toughness=3, keywords=Keyword.TRAMPLE | Keyword.DEATHTOUCH)
    left, right = board.creature(200, 2, toughness=5), board.creature(201, 2, toughness=5)
    result = _combat(board, {100: [200, 201]}, died={200, 201})
    assert result.engine_failures == []
    assert not _alive(board, left) and not _alive(board, right)
    assert board.ex.players[2].life == 19


def test_marked_damage_lowers_what_is_lethal():
    board = _Board()
    board.creature(100, 1, power=4, toughness=4, keywords=Keyword.TRAMPLE)
    hurt, fresh = board.creature(200, 2, toughness=4), board.creature(201, 2, toughness=4)
    hurt.damage_marked = 3
    result = _combat(board, {100: [200, 201]}, died={200})
    assert result.engine_failures == []
    assert not _alive(board, hurt) and _alive(board, fresh) and fresh.damage_marked == 0
    assert board.ex.players[2].life == 20


def test_a_first_strike_pass_divides_its_own_damage():
    board = _Board()
    board.creature(100, 1, power=4, toughness=4, keywords=Keyword.TRAMPLE | Keyword.FIRST_STRIKE)
    left, right = board.creature(200, 2), board.creature(201, 2, toughness=5)
    result = _combat(board, {100: [200, 201]}, died={200}, step="Step_FirstStrikeDamage")
    assert result.engine_failures == []
    assert not _alive(board, left) and right.damage_marked == 0


def test_a_rejected_division_is_an_engine_failure_and_its_intent_is_ended(monkeypatch):
    from silverquillm.replay import executor

    def illegal(*, power, trample, blockers, died, lethal):
        return {id(b): 0 for b in blockers}

    monkeypatch.setattr(executor, "_legal_division", illegal)
    board = _Board()
    attacker = board.creature(100, 1, power=6, toughness=6, keywords=Keyword.TRAMPLE)
    board.creature(200, 2)
    board.creature(201, 2)
    result = _combat(board, {100: [200, 201]})
    assert any("combat_damage_step" in f for f in result.engine_failures)
    assert attacker.controller._intents == {}
