"""End-to-end reference tests for FDN 248 — Thousand-Year Storm.

Exercises the real copy pipeline: Storm's trigger copies a spell already on the
stack, optionally re-choosing targets **through the shared cast-time target
machinery** (`_query_target`), and each copy stint-revalidates its targets at
resolution. The retargeting handles Fiery Annihilation's *dependent* Equipment
target (only Equipment attached to the newly-chosen creature is offered), and a
copy whose newly-chosen target leaves and returns before resolution is rejected.
"""

from __future__ import annotations

from cards.fdn.fdn_248.card_impl import ThousandYearStorm
from cards.fdn.fdn_86.card_impl import FieryAnnihilation
from engine.card import Creature, Equipment
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.events import SpellCastTriggeredEvent
from engine.intent_player import Intent
from engine.stack import resolve_top_of_stack
from engine.types import ManaCost, ManaType, Zone
from engine.zones import move_to_zone
from test_utils import create_game, resolve_stack, set_board_state


def _creature(p, name, toughness=12):
    # High toughness so double-damage (original + copy both hitting one creature)
    # doesn't trigger a lethal-damage SBA and complicate the assertions.
    return Creature(name=name, base_power=2, base_toughness=toughness, owner=p, controller=p)


def _equipment(p, name):
    return Equipment(name=name, owner=p, controller=p, equip_cost=ManaCost.parse("{1}"))


def _pref(game, obj):
    return Decision.obj(instance=game.refs.instance_id(obj, Zone.BATTLEFIELD.value))


def _cast_fiery(game, p1, fiery, targets):
    """Cast Fiery Annihilation (instant) choosing *targets*, WITHOUT resolving."""
    prefs = tuple(_pref(game, t) for t in targets)
    p1.start_intent("fiery", Intent(
        pattern=GameRef(card=frozenset({("name", "Fiery Annihilation")})),
        preferences=prefs,
    ))
    try:
        engine_cast_spell(game, p1, fiery)
    finally:
        p1.end_intent("fiery")


def _fire_storm(game, p1, pending_spell, storm_prefs):
    """Fire the spell-cast event so Storm's trigger goes on the stack, answering
    Storm's retarget prompt + target queries (when it resolves) via *storm_prefs*.
    Leaves the Storm trigger on the stack (not yet resolved)."""
    p1.start_intent("storm", Intent(
        pattern=GameRef(card=frozenset({("name", "Thousand-Year Storm")})),
        preferences=storm_prefs,
    ))
    game.trigger_manager.fire_event(
        game, SpellCastTriggeredEvent(spell=pending_spell, player=p1)
    )
    return "storm"  # intent name; caller ends it after the trigger resolves


def _setup():
    game = create_game()
    p1, p2 = game.players
    storm = ThousandYearStorm(owner=p1, controller=p1)
    c1 = _creature(p2, "Creature One")
    c2 = _creature(p2, "Creature Two")
    eq1 = _equipment(p2, "Sword One")
    eq2 = _equipment(p2, "Sword Two")
    eq1.attached_to = c1
    eq2.attached_to = c2
    fiery = FieryAnnihilation(owner=p1, controller=p1)
    set_board_state(game, 0, hand=[fiery], battlefield=[storm],
                    mana={ManaType.RED: 1, ManaType.COLORLESS: 2})
    set_board_state(game, 1, battlefield=[c1, c2, eq1, eq2])
    game.active_player_index = 0
    storm.register_triggers(game)
    # One prior instant/sorcery this turn → the next cast makes exactly one copy.
    storm._storm_count = 1
    storm._last_turn = game.turn_number
    return game, p1, p2, storm, fiery, c1, c2, eq1, eq2


class TestThousandYearStormProperties:
    def test_static_data(self):
        storm = ThousandYearStorm(owner=None)
        assert storm.name == "Thousand-Year Storm"
        assert storm.mana_cost == ManaCost.parse("{4}{U}{R}")


class TestThousandYearStormEndToEnd:
    def test_copy_retains_targets_and_resolves(self):
        """Baseline: with no retarget the copy keeps the original's target and
        the copy resolves (deals its damage)."""
        game, p1, p2, storm, fiery, c1, c2, eq1, eq2 = _setup()
        _cast_fiery(game, p1, fiery, [c1])            # original targets c1 only
        name = _fire_storm(game, p1, fiery, (Decision.no(),))  # decline retarget
        resolve_stack(game)
        p1.end_intent(name)
        assert c1.damage_marked == 10                 # original + copy both hit c1 (5 + 5)

    def test_copy_dependent_retarget_offers_only_matching_equipment(self):
        """The copy re-chooses new targets: a new creature (c2) and — via the
        shared dependent-target machinery — an Equipment attached to *that*
        creature (eq2). eq1 (attached to the other creature) is not a legal option
        and is not exiled; eq2 is."""
        game, p1, p2, storm, fiery, c1, c2, eq1, eq2 = _setup()
        _cast_fiery(game, p1, fiery, [c1])            # original: c1, no Equipment
        # Retarget the copy: yes, creature → c2, Equipment → eq2 (attached to c2).
        name = _fire_storm(game, p1, fiery, (Decision.yes(), _pref(game, c2), _pref(game, eq2)))
        resolve_stack(game)
        p1.end_intent(name)
        assert c2.damage_marked == 5                  # copy hit the new creature
        assert game.get_exile(p2).contains(eq2)       # copy exiled the dependent Equipment
        assert not game.get_exile(p2).contains(eq1)   # eq1 (other creature's) never targeted
        assert c1.damage_marked == 5                  # original still hit c1

    def test_copy_new_target_leave_and_return_rejected(self):
        """A copy's newly-chosen target leaves and returns AFTER the copy is
        created but before it resolves: the copy captured that target's stint, so
        the returned object (new stint) is rejected — the copy does nothing to it,
        while the original (a different, untouched target) still resolves."""
        game, p1, p2, storm, fiery, c1, c2, eq1, eq2 = _setup()
        _cast_fiery(game, p1, fiery, [c1])            # original targets c1
        # Retarget the copy's creature to c2 (decline the Equipment).
        name = _fire_storm(game, p1, fiery, (Decision.yes(), _pref(game, c2)))
        # Resolve ONLY the Storm trigger — it creates the copy (capturing c2's
        # current stint) and pushes it on top of the still-pending original.
        resolve_top_of_stack(game)
        p1.end_intent(name)
        # Now leave-and-return c2 before the copy resolves.
        move_to_zone(game, c2, Zone.BATTLEFIELD, Zone.EXILE)
        move_to_zone(game, c2, Zone.EXILE, Zone.BATTLEFIELD)  # new stint
        resolve_stack(game)
        assert c2.damage_marked == 0                  # copy rejected the returned c2
        assert c1.damage_marked == 5                  # original (unchanged) still hit c1
