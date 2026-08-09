"""Reference test for FDN 126 — Zimone, Paradox Sculptor.

Two targeted mechanisms fixed at stack-placement time, not at resolution:

* ``{G}{U}, {T}``: an activated ability targeting *up to two distinct*
  creatures/artifacts you control — genuinely optional (zero/one/two), chosen at
  activation, revalidated (stint + "you control") at resolution.
* Beginning-of-combat trigger: "up to two target creatures you control" whose
  targets are chosen as the trigger is put on the stack (the reusable
  ``TriggerRegistration.targeting`` channel).
"""

from __future__ import annotations

from cards.fdn.fdn_126.card_impl import ZimoneParadoxSculptor
from engine.card import Artifact, Creature
from engine.decisions import Decision, GameRef
from engine.events import BeginningOfCombatTriggeredEvent
from engine.game import add_counter
from engine.intent_player import Intent
from engine.types import CardType, ManaCost, ManaType, Zone
from engine.zones import move_to_zone
from test_utils import (
    activate_card_ability,
    create_game,
    resolve_stack,
    set_board_state,
)

ZIMONE = "Zimone, Paradox Sculptor"


def _creature(p, name):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _pref(game, obj):
    return Decision.obj(instance=game.refs.instance_id(obj, Zone.BATTLEFIELD.value))


def _activate_double(game, player, zimone, targets):
    prefs = tuple(_pref(game, t) for t in targets)
    player.start_intent("z", Intent(
        pattern=GameRef(card=frozenset({("name", ZIMONE)})),
        preferences=prefs,
    ))
    try:
        activate_card_ability(game, player, zimone)
    finally:
        player.end_intent("z")


class TestZimoneProperties:
    def test_static_data(self):
        z = ZimoneParadoxSculptor(owner=None)
        assert z.mana_cost == ManaCost.parse("{2}{G}{U}")
        assert (z.base_power, z.base_toughness) == (1, 4)

    def test_ability_signature_and_targeting(self):
        z = ZimoneParadoxSculptor(owner=None)
        abilities = z.get_activated_abilities()  # fixed (self)-only signature
        assert len(abilities) == 1
        assert abilities[0].targeting is not None


class TestZimoneDoubleAbility:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        z = ZimoneParadoxSculptor(owner=p1, controller=p1)
        a = _creature(p1, "Ally A")
        b = _creature(p1, "Ally B")
        set_board_state(game, 0, battlefield=[z, a, b],
                        mana={ManaType.GREEN: 1, ManaType.BLUE: 1})
        add_counter(game, a, "+1/+1", 2)
        add_counter(game, b, "+1/+1", 3)
        return game, p1, p2, z, a, b

    def test_two_distinct_targets_doubled(self):
        game, p1, p2, z, a, b = self._setup()
        _activate_double(game, p1, z, [a, b])
        top = game.stack.peek()
        assert set(top.targets) == {a, b}      # fixed at activation, distinct
        assert len(top.targets) == 2
        resolve_stack(game)
        assert a.plus_one_counters == 4        # 2 → 4
        assert b.plus_one_counters == 6        # 3 → 6

    def test_one_target(self):
        game, p1, p2, z, a, b = self._setup()
        _activate_double(game, p1, z, [a])     # decline the second pick
        assert game.stack.peek().targets == [a]
        resolve_stack(game)
        assert a.plus_one_counters == 4
        assert b.plus_one_counters == 3        # untouched

    def test_zero_targets_still_activates(self):
        game, p1, p2, z, a, b = self._setup()
        _activate_double(game, p1, z, [])      # genuinely optional: none chosen
        assert game.stack.peek().targets == []
        assert z.is_tapped                      # cost still paid ({T})
        resolve_stack(game)
        assert a.plus_one_counters == 2
        assert b.plus_one_counters == 3

    def test_can_target_artifact_you_control(self):
        game, p1, p2, z, a, b = self._setup()
        art = Artifact(name="Trinket", owner=p1, controller=p1)
        game.get_battlefield(p1).add(art)
        art.instance_id = game.refs.instance_id(art, Zone.BATTLEFIELD.value)
        add_counter(game, art, "charge", 2)
        _activate_double(game, p1, z, [art])
        resolve_stack(game)
        assert art.counters.get("charge") == 4

    def test_one_target_illegal_other_legal(self):
        """A targets loses "you control" before resolution; the other still
        resolves (rule 608.2b — each target revalidated independently)."""
        game, p1, p2, z, a, b = self._setup()
        _activate_double(game, p1, z, [a, b])
        a.controller = p2                       # no longer "you control"
        resolve_stack(game)
        assert a.plus_one_counters == 2         # illegal → not doubled
        assert b.plus_one_counters == 6         # legal → doubled

    def test_leave_and_return_target_rejected(self):
        """A target that leaves and returns is a new object (new stint) and is
        rejected by stint validation — its counters are not doubled."""
        game, p1, p2, z, a, b = self._setup()  # a starts with 2 counters
        _activate_double(game, p1, z, [a])
        move_to_zone(game, a, Zone.BATTLEFIELD, Zone.EXILE)
        move_to_zone(game, a, Zone.EXILE, Zone.BATTLEFIELD)
        resolve_stack(game)
        # The returned object is p1-controlled and a creature, so only stint
        # validation can reject it: its counters are left undoubled (2, not 4).
        assert a.plus_one_counters == 2


class TestZimoneCombatTrigger:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        z = ZimoneParadoxSculptor(owner=p1, controller=p1)
        a = _creature(p1, "Ally A")
        b = _creature(p1, "Ally B")
        set_board_state(game, 0, battlefield=[z, a, b])
        game.active_player_index = 0
        z.register_triggers(game)
        return game, p1, p2, z, a, b

    def test_trigger_registered_with_targeting(self):
        game, p1, p2, z, a, b = self._setup()
        regs = game.trigger_manager.get_triggers_for_source(z)
        assert len(regs) == 1
        assert regs[0].targeting is not None

    def _fire(self, game, player, targets):
        prefs = tuple(_pref(game, t) for t in targets)
        player.start_intent("zt", Intent(
            pattern=GameRef(card=frozenset({("name", ZIMONE)})),
            preferences=prefs,
        ))
        try:
            game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())
        finally:
            player.end_intent("zt")

    def test_two_targets_countered_at_trigger_time(self):
        game, p1, p2, z, a, b = self._setup()
        self._fire(game, p1, [a, b])
        top = game.stack.peek()
        assert set(top.targets) == {a, b}       # fixed as the trigger went up
        resolve_stack(game)
        assert a.plus_one_counters == 1
        assert b.plus_one_counters == 1

    def test_target_control_change_before_resolution(self):
        game, p1, p2, z, a, b = self._setup()
        self._fire(game, p1, [a, b])
        a.controller = p2                        # a leaves "you control"
        resolve_stack(game)
        assert a.plus_one_counters == 0          # illegal → no counter
        assert b.plus_one_counters == 1          # still legal
