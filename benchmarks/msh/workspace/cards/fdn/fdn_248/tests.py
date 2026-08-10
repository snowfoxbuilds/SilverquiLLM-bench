"""End-to-end reference tests for FDN 248 — Thousand-Year Storm.

Two invariants are exercised here through the *real* casting + trigger pipeline:

1. **Per-trigger immutable state (rule: "for each other instant and sorcery
   spell you've cast before it this turn").** Each Storm trigger captures, when it
   goes on the stack, which spell it copies and how many copies to make — the
   count of spells cast *before* the triggering one this turn. It is never derived
   from how many triggers have since resolved, nor read from a mutable
   source-level slot. So casting B *in response to* A's Storm trigger still makes
   B's trigger copy B once and A's trigger copy A zero times, in LIFO order.

2. **Protection-aware copy retargeting through the shared spell-retargeting
   path.** A copy re-choosing its targets applies the complete cast-time legality
   contract *for the copied spell*: zone, the (arity-aware, so dependent) target
   filter, distinctness, and **protection from the copied spell** — a protected
   permanent is absent from the option set, not merely rejected at resolution.
   Each copy stint-revalidates its targets, so a newly-chosen leave-and-return
   target is rejected.
"""

from __future__ import annotations

from typing import Any

from cards.fdn.fdn_248.card_impl import ThousandYearStorm
from cards.fdn.fdn_86.card_impl import FieryAnnihilation
from engine.card import Creature, Equipment, Instant
from engine.casting import cast_spell as engine_cast_spell, cast_spell_free
from engine.decisions import Decision, DecisionKind, GameRef
from engine.events import SpellCastTriggeredEvent
from engine.intent_player import Intent
from engine.protection import ProtectionAbility
from engine.stack import resolve_top_of_stack
from engine.types import (
    CardType,
    Color,
    ManaCost,
    ManaType,
    Phase,
    TargetRequirement,
    Zone,
)
from engine.zones import move_to_zone
from test_utils import create_game, resolve_stack, set_board_state


# ---------------------------------------------------------------------------
# Lightweight test spells (real cards, driven through the real cast pipeline)
# ---------------------------------------------------------------------------


def _is_creature(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


class _Signal(Instant):
    """A {0} instant with no targets — used to drive the cast/count pipeline
    without any target queries."""

    def __init__(self, name: str, **kwargs: Any) -> None:
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost.parse("{0}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list:
        return []

    def on_resolve(self, game: Any) -> None:
        return None


class _Bolt(Instant):
    """A {0} instant that deals 5 damage to target creature — used where a copy
    must choose a target so independent retargeting is observable."""

    def __init__(self, name: str, **kwargs: Any) -> None:
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost.parse("{0}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list:
        return [
            TargetRequirement(
                filter_fn=_is_creature,
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is not None and _is_creature(target):
            deal_damage(game, self, target, 5)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _creature(p, name, toughness=12):
    # High toughness so double damage does not trip a lethal-damage SBA and
    # complicate the assertions.
    return Creature(name=name, base_power=2, base_toughness=toughness, owner=p, controller=p)


def _equipment(p, name):
    return Equipment(name=name, owner=p, controller=p, equip_cost=ManaCost.parse("{1}"))


def _pref(game, obj):
    return Decision.obj(instance=game.refs.instance_id(obj, Zone.BATTLEFIELD.value))


def _cast(game, p1, spell, target_prefs=None):
    """Cast *spell* through the real pipeline, answering its cast-time target
    query (when it targets) with *target_prefs*, routed by the spell's own name."""
    if target_prefs is not None:
        p1.start_intent("cast", Intent(
            pattern=GameRef(card=frozenset({("name", spell.name)})),
            preferences=tuple(target_prefs),
        ))
        try:
            engine_cast_spell(game, p1, spell)
        finally:
            p1.end_intent("cast")
    else:
        engine_cast_spell(game, p1, spell)


def _fire(game, p1, spell):
    """Fire the spell-cast event so Storm's trigger (if any) goes on the stack —
    exactly what the game/replay pipeline does after a spell is cast."""
    game.trigger_manager.fire_event(
        game, SpellCastTriggeredEvent(spell=spell, player=p1)
    )


def _resolve_top_collect_new(game):
    """Resolve exactly the top stack object; return the objects it pushed."""
    before = list(game.stack._items)
    resolve_top_of_stack(game)
    return [so for so in game.stack._items if all(so is not b for b in before)]


def _storm_triggers(game, storm):
    return [so for so in game.stack._items if so.source is storm]


# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------


class TestThousandYearStormProperties:
    def test_static_data(self):
        storm = ThousandYearStorm(owner=None)
        assert storm.name == "Thousand-Year Storm"
        assert storm.mana_cost == ManaCost.parse("{4}{U}{R}")


# ---------------------------------------------------------------------------
# Required change 2 — per-trigger immutable copy count / spell (no manual seed)
# ---------------------------------------------------------------------------


class TestStormPerTriggerState:
    def _setup(self, hand):
        game = create_game()
        p1, _p2 = game.players
        storm = ThousandYearStorm(owner=p1, controller=p1)
        set_board_state(game, 0, hand=hand, battlefield=[storm])
        game.active_player_index = 0
        storm.register_triggers(game)  # count starts at 0, this turn — no seeding
        return game, p1, storm

    def test_response_order_B_copies_B_A_copies_nothing(self):
        """Cast A; then cast B *in response to* A's Storm trigger. Driven entirely
        through cast_spell + SpellCastTriggeredEvent (no seeded count):

        * B's trigger (on top) copies B exactly once.
        * A's trigger copies A exactly zero times.
        * Neither trigger copies the other spell.
        """
        a, b = _Signal("Spell A"), _Signal("Spell B")
        game, p1, storm = self._setup([a, b])

        _cast(game, p1, a)
        _fire(game, p1, a)                 # A's trigger: copies=0, spell=A
        _cast(game, p1, b)                 # B cast in response to A's trigger
        _fire(game, p1, b)                 # B's trigger: copies=1, spell=B

        # LIFO top→bottom: [StormB, B, StormA, A].
        new_from_b = _resolve_top_collect_new(game)   # resolve B's Storm trigger
        assert len(new_from_b) == 1
        assert new_from_b[0].source.name == "Spell B"  # copies B, not A
        assert new_from_b[0].source is not b           # a genuine copy

        resolve_top_of_stack(game)         # the copy of B resolves
        resolve_top_of_stack(game)         # B resolves
        new_from_a = _resolve_top_collect_new(game)   # resolve A's Storm trigger
        assert new_from_a == []            # A's trigger makes zero copies

    def test_three_spells_counts_zero_one_two(self):
        """A third spell: the per-trigger captured copy counts are 0, 1, 2 — read
        straight off each trigger's immutable event_state, which also records the
        exact spell each trigger copies."""
        a, b, c = _Signal("Spell A"), _Signal("Spell B"), _Signal("Spell C")
        game, p1, storm = self._setup([a, b, c])

        for spell in (a, b, c):
            _cast(game, p1, spell)
            _fire(game, p1, spell)

        counts = {
            so.event_state.spell.name: so.event_state.copies
            for so in _storm_triggers(game, storm)
        }
        assert counts == {"Spell A": 0, "Spell B": 1, "Spell C": 2}
        # Each trigger correlates to its OWN triggering spell's StackObject.
        for so in _storm_triggers(game, storm):
            assert so.event_state.stack_object.source is so.event_state.spell

    def test_turn_rollover_resets_count(self):
        """Spells cast in turn N do not inflate the copy count in turn N+1 — the
        controller's per-turn cast history resets at the turn boundary."""
        a, b = _Signal("Spell A"), _Signal("Spell B")
        game, p1, storm = self._setup([a, b])

        _cast(game, p1, a)
        _fire(game, p1, a)                 # turn 1: A → copies=0, history now [A]
        resolve_stack(game)

        game.turn_number += 1              # roll to the next turn

        _cast(game, p1, b)
        _fire(game, p1, b)                 # turn 2: B is the first spell → copies=0
        (trig_b,) = _storm_triggers(game, storm)
        assert trig_b.event_state.copies == 0

    def test_countered_triggering_spell_makes_no_copies_and_copies_no_other(self):
        """A trigger whose spell has left the stack (countered) makes no copies —
        and never falls back to copying a *different* pending spell."""
        b, a = _Signal("Spell B"), _Signal("Spell A")
        game, p1, storm = self._setup([b, a])

        # Cast B first (so B and its trigger sit lower on the stack), then A.
        _cast(game, p1, b)
        _fire(game, p1, b)                 # B → copies=0
        _cast(game, p1, a)
        _fire(game, p1, a)                 # A → copies=1, captured A's StackObject

        # "Counter" A — remove its spell StackObject from the stack. B's spell
        # StackObject is still there, below A's Storm trigger.
        a_so = next(so for so in game.stack._items if so.source is a)
        game.stack._items.remove(a_so)

        # A's Storm trigger is now on top. It must make zero copies (A is gone) —
        # not copy B (a different spell still pending).
        new = _resolve_top_collect_new(game)
        assert new == []

    def test_control_change_after_fire_retains_fire_time_controller(self):
        """The trigger's controller is fixed at fire time. Changing control of
        Thousand-Year Storm *after* the trigger fires does not shift "you": the
        copy is still controlled by the fire-time controller."""
        prior, a = _Signal("Prior"), _Signal("Spell A")
        game, p1, storm = self._setup([prior, a])
        p2 = game.players[1]
        # One prior qualifying spell this turn — cast through the real pipeline
        # (no manual count seeding) — so A's trigger makes exactly one copy.
        _cast(game, p1, prior)
        _cast(game, p1, a)
        _fire(game, p1, a)                 # fires with controller p1, copies == 1

        storm.controller = p2              # Storm changes hands before resolution

        new = _resolve_top_collect_new(game)   # resolve the Storm trigger
        assert len(new) == 1
        assert new[0].controller is p1     # fire-time controller, not p2

    def test_independent_targets_for_simultaneous_triggers(self):
        """Two Storm triggers pending at once, copying different spells, choose
        new targets independently — one trigger's retarget never leaks into the
        other's copies."""
        game = create_game()
        p1, p2 = game.players
        storm = ThousandYearStorm(owner=p1, controller=p1)
        c1, c2, c3 = (_creature(p2, n) for n in ("Creature One", "Creature Two", "Creature Three"))
        filler = _Signal("Filler")
        bolt_a, bolt_b = _Bolt("Bolt A"), _Bolt("Bolt B")
        set_board_state(game, 0, hand=[filler, bolt_a, bolt_b], battlefield=[storm])
        set_board_state(game, 1, battlefield=[c1, c2, c3])
        game.active_player_index = 0
        storm.register_triggers(game)

        _cast(game, p1, filler); _fire(game, p1, filler)          # count → 1
        _cast(game, p1, bolt_a, [_pref(game, c1)]); _fire(game, p1, bolt_a)  # A copies=1
        _cast(game, p1, bolt_b, [_pref(game, c1)]); _fire(game, p1, bolt_b)  # B copies=2

        # Retarget every copy: yes to Storm, Bolt A's copies → c3, Bolt B's → c2.
        p1.start_intent("storm", Intent(
            pattern=GameRef(card=frozenset({("name", "Thousand-Year Storm")})),
            preferences=(Decision.yes(),),
        ))
        p1.start_intent("a", Intent(
            pattern=GameRef(card=frozenset({("name", "Bolt A")})),
            preferences=(_pref(game, c3),),
        ))
        p1.start_intent("b", Intent(
            pattern=GameRef(card=frozenset({("name", "Bolt B")})),
            preferences=(_pref(game, c2),),
        ))

        # Bolt B's trigger is on top: two copies, both retargeted to c2.
        new_b = _resolve_top_collect_new(game)
        assert len(new_b) == 2
        assert all(so.source.name == "Bolt B" for so in new_b)
        assert all(so.targets == [c2] for so in new_b)

        # Drain B's copies + the original B to reach Bolt A's trigger.
        while any(so.source.name == "Bolt B" for so in game.stack._items):
            resolve_top_of_stack(game)

        new_a = _resolve_top_collect_new(game)
        assert len(new_a) == 1
        assert new_a[0].source.name == "Bolt A"
        assert new_a[0].targets == [c3]    # A's own choice, not B's c2

        for name in ("storm", "a", "b"):
            p1.end_intent(name)


# ---------------------------------------------------------------------------
# Required change 1 — protection-aware copy retargeting (Fiery Annihilation)
# ---------------------------------------------------------------------------


class TestStormCopyRetargeting:
    def _setup(self, extra_p2_battlefield=()):
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
        prior = _Signal("Prior Spell")
        set_board_state(game, 0, hand=[fiery, prior], battlefield=[storm],
                        mana={ManaType.RED: 1, ManaType.COLORLESS: 2})
        set_board_state(game, 1, battlefield=[c1, c2, eq1, eq2, *extra_p2_battlefield])
        game.active_player_index = 0
        storm.register_triggers(game)
        # One prior instant/sorcery this turn — cast through the real pipeline so
        # p1's turn history holds one qualifying spell → the next cast makes
        # exactly one copy. This suite is about retargeting, not counting, so no
        # manual count seeding is used. The prior spell (a {0} instant) is left
        # unresolved on the stack — Fiery Annihilation is an instant, so a
        # non-empty stack does not block it — deliberately avoiding a settle pass
        # (``apply_all``) here, which would clear a creature's protections before
        # the retargeting queries under test.
        _cast(game, p1, prior)
        return game, p1, p2, storm, fiery, c1, c2, eq1, eq2

    def _cast_fiery(self, game, p1, fiery, targets):
        _cast(game, p1, fiery, [_pref(game, t) for t in targets])

    def _fire_storm(self, game, p1, fiery, *, retarget, copy_target_prefs=()):
        """Fire Storm's trigger for *fiery*, routing the retarget yes/no to the
        Storm intent and the copy's target queries to a Fiery Annihilation intent
        (the copy's provenance is the copied spell, not the enchantment)."""
        p1.start_intent("storm", Intent(
            pattern=GameRef(card=frozenset({("name", "Thousand-Year Storm")})),
            preferences=(Decision.yes(),) if retarget else (Decision.no(),),
        ))
        p1.start_intent("copytarget", Intent(
            pattern=GameRef(card=frozenset({("name", "Fiery Annihilation")})),
            preferences=tuple(copy_target_prefs),
        ))
        _fire(game, p1, fiery)

    def _end_storm(self, p1):
        p1.end_intent("storm")
        p1.end_intent("copytarget")

    def test_copy_retains_targets_and_resolves(self):
        """Decline the retarget → the copy keeps the original's target and
        resolves (both original and copy hit c1)."""
        game, p1, p2, storm, fiery, c1, c2, eq1, eq2 = self._setup()
        self._cast_fiery(game, p1, fiery, [c1])
        self._fire_storm(game, p1, fiery, retarget=False)
        resolve_stack(game)
        self._end_storm(p1)
        assert c1.damage_marked == 10      # original + copy both hit c1

    def test_copy_dependent_retarget_offers_only_matching_equipment(self):
        """Retarget the copy to a new creature c2 and — via the shared dependent
        machinery — an Equipment attached to *that* creature (eq2). eq1 (on the
        other creature) is not a legal option; eq2 is."""
        game, p1, p2, storm, fiery, c1, c2, eq1, eq2 = self._setup()
        self._cast_fiery(game, p1, fiery, [c1])
        self._fire_storm(game, p1, fiery, retarget=True,
                         copy_target_prefs=(_pref(game, c2), _pref(game, eq2)))
        resolve_stack(game)
        self._end_storm(p1)
        assert c2.damage_marked == 5       # copy hit the new creature
        assert game.get_exile(p2).contains(eq2)      # dependent Equipment exiled
        assert not game.get_exile(p2).contains(eq1)  # other creature's, never targeted
        assert c1.damage_marked == 5       # original still hit c1

    def test_copy_new_target_leave_and_return_rejected(self):
        """A copy's newly-chosen target leaves and returns before the copy
        resolves: the copy captured its stint, so the returned object (new stint)
        is rejected, while the original (a different, untouched target) resolves."""
        game, p1, p2, storm, fiery, c1, c2, eq1, eq2 = self._setup()
        self._cast_fiery(game, p1, fiery, [c1])
        self._fire_storm(game, p1, fiery, retarget=True,
                         copy_target_prefs=(_pref(game, c2),))  # decline Equipment
        resolve_top_of_stack(game)         # resolve ONLY Storm's trigger → makes the copy
        self._end_storm(p1)
        move_to_zone(game, c2, Zone.BATTLEFIELD, Zone.EXILE)
        move_to_zone(game, c2, Zone.EXILE, Zone.BATTLEFIELD)   # new stint
        resolve_stack(game)
        assert c2.damage_marked == 0       # copy rejected the returned c2
        assert c1.damage_marked == 5       # original (unchanged) still hit c1

    def test_copy_cannot_target_protected_permanent(self):
        """A permanent with protection from the copied spell (Fiery Annihilation
        is red → protection from red) is **absent from the copy's option set**,
        not merely ignored at resolution; an unprotected creature remains
        selectable, so the copy targets it instead."""
        protected = _creature(None, "Protected One")
        protected.protections = [ProtectionAbility(quality=Color.RED)]
        game, p1, p2, storm, fiery, c1, c2, eq1, eq2 = self._setup(
            extra_p2_battlefield=[protected]
        )
        protected.owner = protected.controller = p2
        self._cast_fiery(game, p1, fiery, [c1])
        # Prefer c2 (unprotected). Even if a preference pointed at the protected
        # creature it could not be chosen — it is never offered.
        self._fire_storm(game, p1, fiery, retarget=True,
                         copy_target_prefs=(_pref(game, c2),))
        resolve_stack(game)                # the copy re-chooses its target here
        self._end_storm(p1)

        # Option-set invariant on the copy's creature-selection query (the most
        # recent one — the cast-time query, unprotected against, came first): it
        # offered the unprotected creature but never the protected one.
        creature_queries = [
            r for r in p1.transcript.queries(kind=DecisionKind.OBJECT)
            if any(("name", "Creature Two") in o.attrs for o in r.options)
        ]
        assert len(creature_queries) >= 2, "expected cast-time and copy queries"
        offered = creature_queries[-1].options
        assert not any(("name", "Protected One") in o.attrs for o in offered)
        assert any(("name", "Creature Two") in o.attrs for o in offered)

        assert protected.damage_marked == 0   # copy never targeted the protected one
        assert c2.damage_marked == 5           # copy hit the unprotected creature


# ---------------------------------------------------------------------------
# Copy count sourced from authoritative per-player turn history (lifecycle)
# ---------------------------------------------------------------------------
#
# The copy count for a Thousand-Year Storm trigger equals the number of instant
# and sorcery spells its fire-time controller cast earlier this turn. These
# end-to-end tests (through the real cast + trigger pipeline, no seeding) prove
# the count does NOT depend on: when this Storm entered, how long its trigger has
# been registered, whether control changed, how many Storms exist, or when
# pending triggers resolve — because the count lives in the player/turn
# lifecycle, not on the Storm source.


class TestStormAuthoritativeCount:
    def _storm(self, p):
        return ThousandYearStorm(owner=p, controller=p)

    def test_late_entering_storm_captures_full_prior_count(self):
        """P1 casts two qualifying spells; THEN Storm enters and registers; P1
        casts a third. The trigger captures a copy count of two — the count
        comes from P1's turn history, not from when this Storm began observing."""
        game = create_game()
        p1, _p2 = game.players
        s1, s2, s3 = (_Signal(n) for n in ("S1", "S2", "S3"))
        storm = self._storm(p1)
        set_board_state(game, 0, hand=[s1, s2, s3])
        game.active_player_index = 0

        _cast(game, p1, s1)                # history: [s1]  (no Storm present yet)
        _cast(game, p1, s2)                # history: [s1, s2]

        # Storm enters the battlefield and registers only now.
        set_board_state(game, 0, battlefield=[storm])
        storm.register_triggers(game)

        _cast(game, p1, s3)
        _fire(game, p1, s3)
        (trig,) = _storm_triggers(game, storm)
        assert trig.event_state.copies == 2       # not 0 — full prior history counts
        assert trig.event_state.spell is s3

    def test_control_change_reads_new_controllers_history(self):
        """P1 casts two qualifying spells while controlling Storm; P2 then gains
        control and casts P2's first qualifying spell that turn. The trigger
        captures zero (P2's history), not two (P1's)."""
        game = create_game()
        p1, p2 = game.players
        p1a, p1b = _Signal("P1a"), _Signal("P1b")
        p2a = _Signal("P2a")
        storm = self._storm(p1)
        set_board_state(game, 0, hand=[p1a, p1b], battlefield=[storm])
        set_board_state(game, 1, hand=[p2a])
        game.active_player_index = 0
        storm.register_triggers(game)

        _cast(game, p1, p1a); _fire(game, p1, p1a)   # P1's trigger: copies 0
        _cast(game, p1, p1b); _fire(game, p1, p1b)   # P1's trigger: copies 1

        storm.controller = p2                        # P2 gains control

        _cast(game, p2, p2a); _fire(game, p2, p2a)   # P2's first qualifying spell
        (p2_trig,) = [
            so for so in _storm_triggers(game, storm)
            if so.event_state.spell is p2a
        ]
        assert p2_trig.event_state.copies == 0       # P2's history, not P1's two

    def test_separate_player_histories_are_not_merged_by_control_change(self):
        """P1 and P2 cast different numbers of qualifying spells; a control
        change of Storm neither merges nor transfers their histories."""
        game = create_game()
        p1, p2 = game.players
        for n in ("A", "B", "C"):
            c = _Signal(f"P1-{n}")
            game.get_hand(p1).add(c)
            _cast(game, p1, c)             # P1 casts three
        c = _Signal("P2-A")
        game.get_hand(p2).add(c)
        _cast(game, p2, c)                 # P2 casts one

        t = game.turn_number
        assert len(p1.instant_or_sorcery_casts_this_turn(t)) == 3
        assert len(p2.instant_or_sorcery_casts_this_turn(t)) == 1

        storm = self._storm(p1)
        set_board_state(game, 0, battlefield=[storm])
        storm.register_triggers(game)
        storm.controller = p2             # control change touches neither history

        assert len(p1.instant_or_sorcery_casts_this_turn(t)) == 3
        assert len(p2.instant_or_sorcery_casts_this_turn(t)) == 1

    def test_two_storms_one_late_capture_same_count_without_double_increment(self):
        """Two Storms controlled by the same player — one that entered later —
        capture the same copy count for a single cast, and observing that cast
        through two triggers does not double-increment the underlying history."""
        game = create_game()
        p1, _p2 = game.players
        s1, s2, s3 = (_Signal(n) for n in ("S1", "S2", "S3"))
        storm_early = self._storm(p1)
        set_board_state(game, 0, hand=[s1, s2, s3], battlefield=[storm_early])
        game.active_player_index = 0
        storm_early.register_triggers(game)

        _cast(game, p1, s1)               # history [s1]
        _cast(game, p1, s2)               # history [s1, s2]

        # A second Storm enters and registers only after two spells were cast.
        storm_late = self._storm(p1)
        set_board_state(game, 0, battlefield=[storm_early, storm_late])
        storm_late.register_triggers(game)

        _cast(game, p1, s3)
        _fire(game, p1, s3)               # both Storms observe this one cast

        (early,) = _storm_triggers(game, storm_early)
        (late,) = _storm_triggers(game, storm_late)
        assert early.event_state.copies == 2
        assert late.event_state.copies == 2       # late Storm is NOT under-counted
        # The history was incremented exactly once for s3 (two observers, no
        # double-count): three qualifying spells this turn, s3 recorded once.
        history = p1.instant_or_sorcery_casts_this_turn(game.turn_number)
        assert len(history) == 3
        assert history.count(s3) == 1

    def test_earlier_casts_still_count_after_regaining_control(self):
        """A player's earlier qualifying casts still count after that player
        loses and then regains control of Storm."""
        game = create_game()
        p1, p2 = game.players
        s1, s2 = _Signal("S1"), _Signal("S2")
        storm = self._storm(p1)
        set_board_state(game, 0, hand=[s1, s2], battlefield=[storm])
        game.active_player_index = 0
        storm.register_triggers(game)

        _cast(game, p1, s1)               # P1 history [s1]
        storm.controller = p2             # Storm leaves P1...
        storm.controller = p1             # ...and returns to P1
        _cast(game, p1, s2)
        _fire(game, p1, s2)
        (trig,) = _storm_triggers(game, storm)
        assert trig.event_state.copies == 1       # s1 still counts for P1
        assert trig.event_state.spell is s2

    def test_turn_rollover_clears_both_players_histories(self):
        """Both players' prior-turn qualifying casts stop contributing in the
        next turn."""
        game = create_game()
        p1, p2 = game.players
        p1s, p1n = _Signal("P1-prev"), _Signal("P1-next")
        p2s, p2n = _Signal("P2-prev"), _Signal("P2-next")
        storm1 = self._storm(p1)
        storm2 = self._storm(p2)
        set_board_state(game, 0, hand=[p1s, p1n], battlefield=[storm1])
        set_board_state(game, 1, hand=[p2s, p2n], battlefield=[storm2])
        game.active_player_index = 0
        storm1.register_triggers(game)
        storm2.register_triggers(game)

        _cast(game, p1, p1s)              # turn N
        _cast(game, p2, p2s)             # turn N
        game.turn_number += 1             # roll over to turn N+1

        _cast(game, p1, p1n); _fire(game, p1, p1n)   # first spell of N+1 for P1
        _cast(game, p2, p2n); _fire(game, p2, p2n)   # first spell of N+1 for P2

        (t1,) = [so for so in _storm_triggers(game, storm1)
                 if so.event_state.spell is p1n]
        (t2,) = [so for so in _storm_triggers(game, storm2)
                 if so.event_state.spell is p2n]
        assert t1.event_state.copies == 0     # P1's prior-turn cast doesn't count
        assert t2.event_state.copies == 0     # P2's prior-turn cast doesn't count

    def test_nonqualifying_spell_does_not_add_to_copy_count(self):
        """A creature cast before an instant does not inflate the instant's
        Storm copy count — only instant and sorcery casts contribute."""
        game = create_game()
        p1, _p2 = game.players
        bear = Creature(name="Bear", base_power=1, base_toughness=1,
                        owner=p1, controller=p1, mana_cost=ManaCost.parse("{0}"))
        bolt = _Signal("Bolt")
        storm = self._storm(p1)
        set_board_state(game, 0, hand=[bear, bolt], battlefield=[storm])
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN    # sorcery-speed timing for the creature
        storm.register_triggers(game)

        _cast(game, p1, bear)             # nonqualifying — not recorded
        _cast(game, p1, bolt)
        _fire(game, p1, bolt)
        (trig,) = _storm_triggers(game, storm)
        assert trig.event_state.copies == 0       # the creature cast did not count
        assert trig.event_state.spell is bolt


# ---------------------------------------------------------------------------
# Recasting the same physical CardImpl object counts each cast as its own
# occurrence (occurrence-aware accounting)
# ---------------------------------------------------------------------------
#
# The copy count for a Storm trigger is the immutable prior-qualifying-cast
# count the casting pipeline stamps on *this cast's* StackObject — the stack
# representation of one occurrence. Recasting the same object this turn mints a
# new StackObject with its own stamp, so the counts climb 0, 1, 2 … and the
# current cast is excluded exactly once. An identity filter over raw cast history
# would instead drop *every* earlier occurrence of the recast object and
# undercount — the defect these tests pin down.


class TestStormRepeatedObjectCasts:
    def _setup(self, hand):
        game = create_game()
        p1, _p2 = game.players
        storm = ThousandYearStorm(owner=p1, controller=p1)
        set_board_state(game, 0, hand=hand, battlefield=[storm])
        game.active_player_index = 0
        storm.register_triggers(game)      # no seeding — count starts at 0 this turn
        return game, p1, storm

    def _captured_copies(self, game, storm, spell):
        """The copy count the (single) pending Storm trigger for *spell* captured.

        Exactly one Storm trigger is pending for *spell*: the tests resolve the
        stack between casts, so a prior occurrence's trigger is already gone.
        """
        (trig,) = [so for so in _storm_triggers(game, storm)
                   if so.event_state.spell is spell]
        return trig.event_state.copies

    def _return_to_hand(self, game, spell):
        """Resolve the stack (the just-cast instant goes to its graveyard) and
        move the very same object back to hand so it can be recast."""
        resolve_stack(game)
        move_to_zone(game, spell, Zone.GRAVEYARD, Zone.HAND)

    def test_recast_same_object_twice_first_zero_second_one(self):
        """Cast the same instant object twice this turn: the first trigger
        captures zero, the second captures one (not zero)."""
        a = _Signal("Spell A")
        game, p1, storm = self._setup([a])

        _cast(game, p1, a); _fire(game, p1, a)
        assert self._captured_copies(game, storm, a) == 0     # first cast: no prior

        self._return_to_hand(game, a)                          # A resolves, back to hand
        _cast(game, p1, a); _fire(game, p1, a)
        assert self._captured_copies(game, storm, a) == 1      # one prior cast of A

    def test_recast_same_object_three_times_zero_one_two(self):
        """Three casts of the same object: copy counts 0, 1, 2."""
        a = _Signal("Spell A")
        game, p1, storm = self._setup([a])

        captured = []
        for _ in range(3):
            _cast(game, p1, a); _fire(game, p1, a)
            captured.append(self._captured_copies(game, storm, a))
            self._return_to_hand(game, a)
        assert captured == [0, 1, 2]

    def test_mixed_repeated_and_distinct_final_A_captures_two(self):
        """Cast A, then B, then the *same* A object again: the final A has two
        prior qualifying casts (A and B), so its trigger captures two."""
        a, b = _Signal("Spell A"), _Signal("Spell B")
        game, p1, storm = self._setup([a, b])

        _cast(game, p1, a); _fire(game, p1, a)                 # A: 0
        assert self._captured_copies(game, storm, a) == 0
        self._return_to_hand(game, a)                          # A resolves, back to hand

        _cast(game, p1, b); _fire(game, p1, b)                 # B: 1 (A before it)
        assert self._captured_copies(game, storm, b) == 1

        _cast(game, p1, a); _fire(game, p1, a)                 # same A again: 2 (A, B)
        assert self._captured_copies(game, storm, a) == 2

    def test_free_recast_counts_prior_cast_and_records_once(self):
        """Through a free-cast path (cascade / exile casting): a previous normal
        cast of the same object still counts, and the free cast is recorded
        exactly once (the history gains a single occurrence)."""
        a = _Signal("Spell A")
        game, p1, storm = self._setup([a])

        _cast(game, p1, a); _fire(game, p1, a)                 # normal cast: 0
        assert self._captured_copies(game, storm, a) == 0
        self._return_to_hand(game, a)

        turn = game.turn_number
        before = len(p1.instant_or_sorcery_casts_this_turn(turn))
        cast_spell_free(game, p1, a, Zone.HAND)                # free cast of SAME object
        _fire(game, p1, a)
        assert self._captured_copies(game, storm, a) == 1      # the prior cast counts
        after = len(p1.instant_or_sorcery_casts_this_turn(turn))
        assert after - before == 1                             # recorded exactly once

    def test_two_storms_repeated_object_same_count_single_occurrence(self):
        """Two Storms observing the repeated-object cast both capture the same
        prior count, and the history gains only one occurrence for that cast (two
        observers do not double-increment it)."""
        a = _Signal("Spell A")
        game = create_game()
        p1, _p2 = game.players
        storm1 = ThousandYearStorm(owner=p1, controller=p1)
        storm2 = ThousandYearStorm(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[a], battlefield=[storm1, storm2])
        game.active_player_index = 0
        storm1.register_triggers(game)
        storm2.register_triggers(game)

        _cast(game, p1, a); _fire(game, p1, a)                 # first cast — both observe
        resolve_stack(game)                                    # drain both triggers + A
        move_to_zone(game, a, Zone.GRAVEYARD, Zone.HAND)

        turn = game.turn_number
        before = len(p1.instant_or_sorcery_casts_this_turn(turn))
        _cast(game, p1, a); _fire(game, p1, a)                 # recast — both observe again
        assert self._captured_copies(game, storm1, a) == 1
        assert self._captured_copies(game, storm2, a) == 1     # neither under-counts
        after = len(p1.instant_or_sorcery_casts_this_turn(turn))
        assert after - before == 1                             # ONE new occurrence

    def test_turn_rollover_earlier_occurrence_of_same_object_does_not_count(self):
        """An earlier-turn cast of the same object does not contribute after the
        turn rolls over: the recast in the new turn captures zero."""
        a = _Signal("Spell A")
        game, p1, storm = self._setup([a])

        _cast(game, p1, a); _fire(game, p1, a)                 # turn N
        assert self._captured_copies(game, storm, a) == 0
        self._return_to_hand(game, a)

        game.turn_number += 1                                  # roll to the next turn
        _cast(game, p1, a); _fire(game, p1, a)                 # same object, new turn
        assert self._captured_copies(game, storm, a) == 0      # prior-turn cast ignored
