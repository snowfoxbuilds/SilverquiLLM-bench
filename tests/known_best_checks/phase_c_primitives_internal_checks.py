"""Known-Best engine checks moved out of the Audited Engine Tests' test_phase_c_primitives.py:
they drive the engine directly or test its internals, in positions no
FDN card reaches through play, so they guard the Known-Best engine
without being graded against candidates (ADR-018)."""

from __future__ import annotations

import test_interface
from cards.fdn.fdn_130.card_impl import QuickDrawKatana, QuickDrawKatanaAbility2
from cards.fdn.fdn_227.card_impl import LlanowarElves
from engine.card import Creature, Equipment, printed_class
from engine.continuous_effects import (
    DURATION_PERMANENT,
    ContinuousEffect,
    Layer,
    SubLayer,
)
from engine.decisions import Decision, GameRef
from engine.game import add_counter, remove_counter
from engine.state_based_actions import check_state_based_actions
from engine.turn import cleanup_mechanical
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, Zone
from engine.zones import move_to_zone
from test_interface import Side, card
from test_utils import (
    Intent,
    activate_card_ability,
    create_game,
    resolve_stack,
    set_board_state,
)

from silverquillm.table import (
    Table,
    first_strike_damage,
    life,
    moves,
    off_stack,
    on_stack,
    taps,
)


def _equip_via_ability(game, player, equipment, target):
    """Drive *equipment*'s equip ability through the real activate → stack →
    resolve path, targeting *target* (chosen at activation)."""
    inst = game.refs.instance_id(target, Zone.BATTLEFIELD.value)
    player.start_intent("equip", Intent(
        pattern=GameRef(card=frozenset({("printed", printed_class(equipment))})),
        preferences=(Decision.obj(instance=inst),),
    ))
    try:
        activate_card_ability(game, player, equipment)
    finally:
        player.end_intent("equip")


def _push_equip_activation(game, player, equipment, target):
    """Push an equip activation onto the stack targeting *target*, capturing the
    activation context exactly as the engine does but bypassing the
    sorcery-speed/empty-stack timing gate — so two activations of the same
    Equipment can coexist on the stack (the scenario the per-activation context
    isolation must survive). Returns the pushed :class:`StackObject`."""
    from engine.stack import ActivationContext, StackObject

    bf = Zone.BATTLEFIELD.value
    ability = equipment.get_activated_abilities()[0]
    context = ActivationContext(
        controller=player,
        source_instance_id=game.refs.instance_id(equipment, bf),
        target_instance_ids=(game.refs.instance_id(target, bf),),
    )
    obj = StackObject(
        source=equipment, controller=player, targets=[target],
        activation_context=context,
    )
    effect = ability.effect
    obj.on_resolve = (
        lambda g, _o=obj, _e=effect: _e(g, _o.targets, _o.activation_context)
    )
    game.stack.push(obj)
    return obj


def _creature(name, p, power=2, tough=2):
    return Creature(name=name, base_power=power, base_toughness=tough, owner=p, controller=p)


# Tests written on the Test Interface build a position, play it from both
# players' scripts and judge what the table can see.


def _table(p0: Side, p1: Side) -> Table:
    """Player 0's precombat main phase, with player 0 to act."""
    return Table(test_interface.create_game(p0, p1, start=(Phase.PRECOMBAT_MAIN, 0)))


def _resolve(t: Table, *results, note: str = "") -> None:
    """Both players pass, and the top of the stack resolves."""
    t.pass_(0)
    t.pass_(1, then=list(results), note=note)


def _equip(t: Table, *, katana_on, lands=()) -> None:
    """Player 0 taps ``lands`` and equips the Quick-Draw Katana to
    ``katana_on``, and the ability resolves."""
    for land in lands:
        t.act(0, land, then=[taps(land)])
    t.act(0, QuickDrawKatanaAbility2, choices=[katana_on], then=[on_stack(QuickDrawKatanaAbility2, 0)])
    _resolve(t, off_stack(QuickDrawKatanaAbility2))


def _attack_unblocked(t: Table, attacker, *, life_after: int, first_strike: bool = False) -> None:
    """In player 0's next declare attackers step ``attacker`` attacks alone,
    player 1 declares no blockers, and player 1's life becomes ``life_after``
    — in a first-strike combat damage step when ``attacker`` has first strike
    (rule 510.4)."""
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, attacker, then=[taps(attacker)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1, then=[first_strike_damage()] if first_strike else [])  # declares no blockers
    t.pass_(0)
    t.pass_(1, then=[life(1, life_after)])
    if first_strike:
        t.pass_(0)
        t.pass_(1)


def _creatures(n: int) -> list:
    return [card(LlanowarElves) for _ in range(n)]


def _edict_resolves(t: Table, edict, mine: list, theirs: list) -> None:
    """Blasphemous Edict resolves: each player sacrifices every creature they
    have, choosing them one at a time."""
    t.pass_(0, choices=mine)
    t.pass_(1, choices=theirs, then=[moves(edict, Zone.GRAVEYARD), *(moves(c, Zone.GRAVEYARD) for c in mine + theirs)])


# ---------------------------------------------------------------------------
# 1. Counters
# ---------------------------------------------------------------------------

class TestCounterPrimitive:
    def test_plus_one_counter_persists_across_cleanup(self):
        game = create_game()
        p1 = game.players[0]
        c = _creature("X", p1, 1, 1)
        set_board_state(game, 0, battlefield=[c])
        add_counter(game, c, "+1/+1", 2)
        assert c.plus_one_counters == 2
        cleanup_mechanical(game)  # runs apply_all — previously reset counters to 0
        assert c.plus_one_counters == 2
        assert c.power == 3 and c.toughness == 3

    def test_generic_counter_store_retrieve_and_persist(self):
        game = create_game()
        p1 = game.players[0]
        c = _creature("X", p1)
        set_board_state(game, 0, battlefield=[c])
        add_counter(game, c, "charge", 3)
        assert c.counters["charge"] == 3
        remove_counter(game, c, "charge", 1)
        assert c.counters["charge"] == 2
        cleanup_mechanical(game)
        assert c.counters["charge"] == 2  # generic counters survive the reset


    def test_annihilation_persists_across_cleanup(self):
        game = create_game()
        p1 = game.players[0]
        c = _creature("X", p1, 2, 2)
        set_board_state(game, 0, battlefield=[c])
        add_counter(game, c, "+1/+1", 3)
        add_counter(game, c, "-1/-1", 1)
        check_state_based_actions(game)
        assert (c.plus_one_counters, c.minus_one_counters) == (2, 0)
        cleanup_mechanical(game)
        assert (c.plus_one_counters, c.minus_one_counters) == (2, 0)


# ---------------------------------------------------------------------------
# 2. Life paths
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# 3. Continuous effects re-derive on battlefield change
# ---------------------------------------------------------------------------

class _Lord(Creature):
    """+1/+1 to your other creatures while on the battlefield."""

    def register_replacement_effects(self, game):
        lord = self

        def _apply(g):
            for pl in g.players:
                for o in g.get_battlefield(pl).get_all():
                    if o is not lord and CardType.CREATURE in getattr(o, "card_types", set()):
                        o.modified_power += 1
                        o.modified_toughness += 1

        game.effect_manager.add(ContinuousEffect(
            source=lord, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT,
            apply=_apply, duration=DURATION_PERMANENT,
        ))


class TestEffectTiming:



    def test_turn_dependent_buff_drops_at_real_turn_transition(self):
        """Quick-Draw Katana buffs only during its controller's turn. Driven
        through a real controller-turn → opponent-turn transition, the buff is
        recalculated (and dropped) at the transition — not left stale."""

        game = create_game()
        p1, p2 = game.players
        bear = _creature("Bear", p1, 2, 2)
        katana = QuickDrawKatana(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, katana])
        assert game.active_player is p1
        katana.equip(bear, game)  # equip re-derives; p1 active -> buff on
        assert bear.power == 4 and Keyword.FIRST_STRIKE in bear.keywords

        guard = 0
        while game.active_player is p1 and guard < 60:
            game.advance_phase()
            guard += 1
        assert game.active_player is p2  # now the opponent's turn
        # advance_phase re-derived at the active-player change; the buff is gone
        # without any manual apply_all.
        assert bear.power == 2 and Keyword.FIRST_STRIKE not in bear.keywords


# ---------------------------------------------------------------------------
# 3b. Resolution settlement order: resolve → re-derive → SBA
# ---------------------------------------------------------------------------


def _pt_effect(target, dp, dt):
    """A permanent +dp/+dt continuous effect on *target* (layer 7c)."""
    def _apply(_g):
        target.modified_power += dp
        target.modified_toughness += dt

    return ContinuousEffect(
        source=object(), layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT,
        apply=_apply, duration=DURATION_PERMANENT,
    )


def _resolving(on_resolve):
    """A minimal StackObject that runs *on_resolve* when it resolves."""
    from engine.stack import StackObject

    return StackObject(source=object(), controller=None, on_resolve=on_resolve)



# ---------------------------------------------------------------------------
# 4. Equipment lifecycle
# ---------------------------------------------------------------------------

class _TestAxe(Equipment):
    """A test-local Equipment: equipped creature gets +1/+1 and has double
    strike and trample; equip {3}."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Test Axe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        kwargs.setdefault("equip_cost", ManaCost.parse("{3}"))
        super().__init__(**kwargs)

    def make_equip_effects(self, game):
        equipment = self

        def _pt(g):
            if equipment.is_equip_active(g):
                creature = equipment.attached_to
                creature.modified_power += 1
                creature.modified_toughness += 1

        def _kw(g):
            if equipment.is_equip_active(g):
                creature = equipment.attached_to
                creature.keywords |= Keyword.DOUBLE_STRIKE | Keyword.TRAMPLE

        return [
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_pt,
                duration=DURATION_PERMANENT,
            ),
            ContinuousEffect(
                source=self, layer=Layer.ABILITY, apply=_kw, duration=DURATION_PERMANENT,
            ),
        ]


class TestEquipmentLifecycle:




    # --- Equip activation targeting (real activate → stack → resolve path) ---








    def test_equipment_leaves_and_returns_before_resolution_no_attach(self):
        """Equipment leaves and returns before resolution: the old ability does
        not attach the new stint (the returned permanent is a new object)."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, boots],
                        mana={ManaType.COLORLESS: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        _equip_via_ability(game, p1, boots, bear)
        move_to_zone(game, boots, Zone.BATTLEFIELD, Zone.GRAVEYARD)  # leaves
        move_to_zone(game, boots, Zone.GRAVEYARD, Zone.BATTLEFIELD)  # returns (new stint)
        resolve_stack(game)
        assert boots.attached_to is None


    def test_equipment_controller_change_uses_ability_controller(self):
        """Equipment changes controller while its source stays the same stint:
        target legality remains relative to the ability's activation-time
        controller, so the ability still attaches to that player's creature."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1, p2 = game.players
        bear = _creature("Bear", p1, 2, 2)  # a creature p1 controls
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, boots],
                        mana={ManaType.COLORLESS: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        _equip_via_ability(game, p1, boots, bear)  # ability controller = p1
        # Control of the Equipment changes to the opponent (stint-preserving:
        # it stays on the same battlefield, so no new object stint).
        boots.controller = p2
        resolve_stack(game)
        # Evaluated relative to the ability controller (p1), bear is still legal.
        assert boots.attached_to is bear



    def test_target_gains_protection_before_resolution_no_attach(self):
        """Target gains protection from the Equipment before resolution: the
        ability fails to attach."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots
        from engine.protection import ProtectionAbility

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, boots],
                        mana={ManaType.COLORLESS: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        _equip_via_ability(game, p1, boots, bear)  # legal at activation
        # The target gains protection from artifacts before the ability resolves.
        protection = ProtectionAbility(
            quality="artifacts",
            predicate=lambda src: CardType.ARTIFACT in getattr(src, "card_types", set()),
        )
        game.effect_manager.add(ContinuousEffect(
            source=object(), layer=Layer.ABILITY,
            apply=lambda _g: setattr(
                bear, "protections", [*getattr(bear, "protections", []), protection]
            ),
            duration=DURATION_PERMANENT,
        ))
        resolve_stack(game)
        assert boots.attached_to is None

    def test_two_equip_activations_coexist_independent_context(self):
        """Two equip activations from the same Equipment carry independent
        activation contexts on their stack objects — neither clobbers the other,
        so each resolves against its own activation-time target."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots
        from engine.stack import resolve_top_of_stack

        game = create_game()
        p1 = game.players[0]
        a = _creature("A", p1, 2, 2)
        b = _creature("B", p1, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[a, b, boots])
        game.phase = Phase.PRECOMBAT_MAIN
        obj_a = _push_equip_activation(game, p1, boots, a)
        obj_b = _push_equip_activation(game, p1, boots, b)
        # The contexts are distinct per-activation snapshots, not a shared field.
        assert obj_a.activation_context is not obj_b.activation_context
        assert obj_a.targets == [a] and obj_b.targets == [b]
        # LIFO: obj_b resolves first (attaches b), then obj_a (attaches a). If the
        # context lived on a mutable Equipment field the second push would have
        # overwritten the first and both would target the same creature.
        resolve_top_of_stack(game)
        assert boots.attached_to is b
        resolve_top_of_stack(game)
        assert boots.attached_to is a

    # --- Equipment departure lifecycle ---






# ---------------------------------------------------------------------------
# 4b. Activated-ability authorization
# ---------------------------------------------------------------------------

class TestActivationAuthorization:
    """The activating player is the ability's controller (rule 602.2), and only
    that player may activate it. Authorization is decided before any query,
    payment, source mutation, or stack push, and the authorized controller is
    captured on the stack object and never rewritten by a later control change
    of the source."""




    def test_source_control_change_after_activation_keeps_captured_controller(self):
        """A control change of the source *after* a valid activation does not
        rewrite the captured activation-time controller: both
        ``StackObject.controller`` and ``ActivationContext.controller`` stay p1,
        and the ability resolves against p1's board (target legality is judged
        against the captured controller, not the Equipment's new one)."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1, p2 = game.players
        bear = _creature("Bear", p1, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, boots],
                        mana={ManaType.COLORLESS: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        _equip_via_ability(game, p1, boots, bear)   # activated by p1
        top = game.stack.peek()
        assert top is not None
        # Control of the Equipment changes to p2 while the ability waits.
        boots.controller = p2
        # The captured controller is untouched by the control change.
        assert top.controller is p1
        assert top.activation_context is not None
        assert top.activation_context.controller is p1
        resolve_stack(game)
        # Target legality judged against the captured controller (p1) — attaches.
        assert boots.attached_to is bear


# ---------------------------------------------------------------------------
# 5. Cost system
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 6. Token creation replacement + identity
# ---------------------------------------------------------------------------

