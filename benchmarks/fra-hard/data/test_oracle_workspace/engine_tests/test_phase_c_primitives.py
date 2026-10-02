"""Engine-primitive tests for the replay-gap Phase C work.

Covers the primitives introduced/repaired in this phase:

  1. Counters as a real primitive — base-shadow persistence across the
     apply_all reset cycle, generic-counter storage, replacement-before-trigger
     ordering, and annihilation persisting to the base fields.
  2. The two sanctioned life paths — ``gain_life`` / ``lose_life`` firing events.
  3. Continuous effects re-deriving on battlefield change (lord in/out).
  4. Equipment attach/detach lifecycle.
  5. Cost system — battlefield sweep, target-aware self-reduction, alternative
     costs, colored-pip clamp.
  6. Token creation replacement + identity hook.
"""

from __future__ import annotations

import pytest

from engine.abilities import AbilityError
from engine.card import Creature, Equipment, Instant, Land, Sorcery
from engine.casting import cast_spell, get_cost_reduction
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.decisions import Decision, GameRef
from engine.events import (
    AddCounterReplacementEvent,
    CounterAddedTriggeredEvent,
    CreateTokenReplacementEvent,
    GainsLifeTriggeredEvent,
    LosesLifeTriggeredEvent,
)
from engine.game import add_counter, create_token, gain_life, lose_life, remove_counter
from engine.intent_player import Intent
from engine.replacement_effects import ReplacementEffect
from engine.stack import priority_loop
from engine.state_based_actions import check_state_based_actions
from engine.triggers import TriggerRegistration
from engine.turn import cleanup_mechanical
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from engine.zones import move_to_zone
from test_utils import (
    activate_card_ability,
    create_game,
    resolve_stack,
    set_board_state,
)


def _equip_via_ability(game, player, equipment, target):
    """Drive *equipment*'s equip ability through the real activate → stack →
    resolve path, targeting *target* (chosen at activation)."""
    inst = game.refs.instance_id(target, Zone.BATTLEFIELD.value)
    player.start_intent("equip", Intent(
        pattern=GameRef(card=frozenset({("name", equipment.name)})),
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


def _spy_on_answer(player):
    """Replace ``player.answer`` with a spy; return (calls, restore) so a test
    can assert no Player Query was raised (``calls == []``)."""
    calls: list = []
    original = player.answer

    def _spy(query):
        calls.append(query)
        return original(query)

    player.answer = _spy
    return calls, (lambda: setattr(player, "answer", original))


def _creature(name, p, power=2, tough=2):
    return Creature(name=name, base_power=power, base_toughness=tough, owner=p, controller=p)


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

    def test_replacement_runs_before_trigger_and_doubles(self):
        game = create_game()
        p1 = game.players[0]
        c = _creature("X", p1, 0, 0)
        set_board_state(game, 0, battlefield=[c])

        def _double(g, e):
            e.amount *= 2
            return e

        game.replacement_manager.register(ReplacementEffect(
            event_type=AddCounterReplacementEvent, source=c,
            condition=None, replacement=_double,
        ))
        seen: list[tuple] = []

        def _cond(g, e):
            seen.append((e.counter_type, e.amount))
            return False  # record only; don't push anything to the stack

        game.trigger_manager.register(TriggerRegistration(
            event_type=CounterAddedTriggeredEvent, condition=_cond,
            effect=lambda g: None, source=c, controller=p1,
        ))
        add_counter(game, c, "+1/+1", 2)
        assert c.plus_one_counters == 4          # replacement doubled 2 -> 4
        assert seen == [("+1/+1", 4)]            # trigger saw the post-replacement amount

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

class TestLifePaths:
    def _watch(self, game, player, event_type):
        seen: list[int] = []
        game.trigger_manager.register(TriggerRegistration(
            event_type=event_type,
            condition=lambda g, e: (seen.append(e.amount) or False),
            effect=lambda g: None, source=object(), controller=player,
        ))
        return seen

    def test_gain_life_fires_event(self):
        game = create_game()
        p1 = game.players[0]
        seen = self._watch(game, p1, GainsLifeTriggeredEvent)
        start = p1.life
        gain_life(game, p1, 4)
        assert p1.life == start + 4
        assert seen == [4]

    def test_lose_life_fires_event(self):
        game = create_game()
        p1 = game.players[0]
        seen = self._watch(game, p1, LosesLifeTriggeredEvent)
        start = p1.life
        lose_life(game, p1, 3)
        assert p1.life == start - 3
        assert seen == [3]

    def test_zero_amount_is_noop(self):
        game = create_game()
        p1 = game.players[0]
        seen_g = self._watch(game, p1, GainsLifeTriggeredEvent)
        seen_l = self._watch(game, p1, LosesLifeTriggeredEvent)
        gain_life(game, p1, 0)
        lose_life(game, p1, -5)
        assert seen_g == [] and seen_l == []


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
    def test_lord_entering_midturn_buffs_team_immediately(self):
        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        set_board_state(game, 0, battlefield=[bear])
        lord = _Lord(name="Lord", base_power=2, base_toughness=2, owner=p1, controller=p1)
        set_board_state(game, 0, hand=[lord])
        move_to_zone(game, lord, Zone.HAND, Zone.BATTLEFIELD)
        assert bear.power == 3  # buffed now, without a turn-boundary cleanup

    def test_lord_leaving_removes_buff_immediately(self):
        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        set_board_state(game, 0, battlefield=[bear])
        lord = _Lord(name="Lord", base_power=2, base_toughness=2, owner=p1, controller=p1)
        set_board_state(game, 0, hand=[lord])
        move_to_zone(game, lord, Zone.HAND, Zone.BATTLEFIELD)  # registers the anthem
        assert bear.power == 3
        move_to_zone(game, lord, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        assert bear.power == 2  # departed source's effect removed engine-side

    def test_new_midturn_effect_applies_immediately_via_stack(self):
        """Adventuring Gear's landfall registers a mid-turn until-EOT buff when
        its trigger resolves. The engine re-derives after a stack object
        resolves, so the buff applies immediately — no manual apply_all."""
        from cards.fdn.fdn_249.card_impl import AdventuringGear

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        gear = AdventuringGear(owner=p1, controller=p1)
        land = Land(name="Forest", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, gear], hand=[land])
        gear.register_triggers(game)  # set_board_state does not fire ETB registration
        gear.equip(bear, game)
        assert (bear.power, bear.toughness) == (2, 2)  # Gear has no static buff

        move_to_zone(game, land, Zone.HAND, Zone.BATTLEFIELD)  # landfall -> stack
        assert (bear.power, bear.toughness) == (2, 2)  # trigger not resolved yet
        priority_loop(game)  # resolves the landfall trigger through the real stack
        assert (bear.power, bear.toughness) == (4, 4)  # applied without manual apply_all

    def test_turn_dependent_buff_drops_at_real_turn_transition(self):
        """Quick-Draw Katana buffs only during its controller's turn. Driven
        through a real controller-turn → opponent-turn transition, the buff is
        recalculated (and dropped) at the transition — not left stale."""
        from cards.fdn.fdn_130.card_impl import QuickDrawKatana

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


class TestResolutionOrder:
    def test_resolving_buff_saves_damaged_creature(self):
        """A 2/2 with two marked damage survives when a resolving ability creates
        an applicable +2/+2 continuous effect — re-derive precedes the
        lethal-damage SBA, so the creature is a 4/4 with 2 damage when checked."""
        from engine.stack import resolve_top_of_stack

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        set_board_state(game, 0, battlefield=[bear])
        bear.damage_marked = 2  # lethal for a 2/2 as-is

        game.stack.push(_resolving(
            lambda g: g.effect_manager.add(_pt_effect(bear, 2, 2))
        ))
        resolve_top_of_stack(game)

        assert game.get_battlefield(p1).contains(bear)  # survived
        assert (bear.power, bear.toughness) == (4, 4)
        assert bear.damage_marked == 2

    def test_resolving_debuff_kills_creature_before_priority(self):
        """A resolving -2/-2 continuous effect moves a 2/2 to the graveyard
        before priority returns — re-derive (→ 0/0) precedes the zero-toughness
        SBA."""
        from engine.stack import resolve_top_of_stack

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        set_board_state(game, 0, battlefield=[bear])

        game.stack.push(_resolving(
            lambda g: g.effect_manager.add(_pt_effect(bear, -2, -2))
        ))
        resolve_top_of_stack(game)

        assert not game.get_battlefield(p1).contains(bear)
        assert game.get_graveyard(p1).contains(bear)

    def test_removing_last_effect_during_resolution_resets(self):
        """Removing the last active effect during resolution resets the affected
        permanent rather than leaving stale modified characteristics — the
        resolver always re-derives, even when the effect manager becomes empty."""
        from engine.stack import resolve_top_of_stack

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        set_board_state(game, 0, battlefield=[bear])
        eff = game.effect_manager.add(_pt_effect(bear, 2, 2))
        game.effect_manager.apply_all(game)
        assert (bear.power, bear.toughness) == (4, 4)
        assert len(game.effect_manager) == 1

        game.stack.push(_resolving(lambda g: g.effect_manager.remove(eff)))
        resolve_top_of_stack(game)

        assert len(game.effect_manager) == 0
        assert (bear.power, bear.toughness) == (2, 2)  # reset, not left at 4/4

    def test_casting_resolve_top_matches_priority_loop_settlement(self):
        """engine.casting.resolve_top and priority_loop share one resolution
        primitive, so they settle a resolving -2/-2 identically (the creature
        dies before priority returns in both)."""
        from engine.casting import resolve_top
        from engine.stack import priority_loop

        def _scenario():
            game = create_game()
            p1 = game.players[0]
            bear = _creature("Bear", p1, 2, 2)
            set_board_state(game, 0, battlefield=[bear])
            game.stack.push(_resolving(
                lambda g: g.effect_manager.add(_pt_effect(bear, -2, -2))
            ))
            return game, p1, bear

        ga, pa, ba = _scenario()
        resolve_top(ga)
        gb, pb, bb = _scenario()
        priority_loop(gb)

        # Both settled the same way: creature dead, off the battlefield.
        assert ga.get_battlefield(pa).contains(ba) is False
        assert gb.get_battlefield(pb).contains(bb) is False
        assert ga.get_graveyard(pa).contains(ba)
        assert gb.get_graveyard(pb).contains(bb)


# ---------------------------------------------------------------------------
# 4. Equipment lifecycle
# ---------------------------------------------------------------------------

class TestEquipmentLifecycle:
    def test_attach_buffs_then_detach_removes(self):
        from cards.fdn.fdn_129.card_impl import LeylineAxe

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        axe = LeylineAxe(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, axe])
        axe.equip(bear, game)
        assert axe.attached_to is bear
        assert (bear.power, bear.toughness) == (3, 3)
        assert Keyword.DOUBLE_STRIKE in bear.keywords and Keyword.TRAMPLE in bear.keywords
        axe.detach(game)
        assert axe.attached_to is None
        assert (bear.power, bear.toughness) == (2, 2)
        assert Keyword.DOUBLE_STRIKE not in bear.keywords

    def test_sba_unattaches_when_creature_leaves(self):
        from cards.fdn.fdn_129.card_impl import LeylineAxe

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        axe = LeylineAxe(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, axe])
        axe.equip(bear, game)
        move_to_zone(game, bear, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        check_state_based_actions(game)
        assert axe.attached_to is None

    def test_equip_ability_targets_only_your_creatures(self):
        """Option-set invariant: equip finds no legal target among only the
        opponent's creatures, so activation is rejected before cost."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        from engine.abilities import AbilityError
        from test_utils import activate_card_ability

        game = create_game()
        p1, p2 = game.players
        their_bear = _creature("Their Bear", p2, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[boots], mana={ManaType.COLORLESS: 1})
        set_board_state(game, 1, battlefield=[their_bear])
        game.phase = Phase.PRECOMBAT_MAIN
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, boots)  # no creature you control
        assert boots.attached_to is None
        assert p1.mana_pool.total() == 1  # rejected before cost -> no mana spent

    def test_equip_ability_is_sorcery_speed(self):
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1 = game.players[0]
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[boots], mana={ManaType.COLORLESS: 1})
        ability = boots.get_activated_abilities()[0]
        game.phase = Phase.COMBAT
        assert ability.cost(game, boots) is False  # not sorcery speed
        game.phase = Phase.PRECOMBAT_MAIN
        assert ability.cost(game, boots) is True   # sorcery speed, cost paid

    # --- Equip activation targeting (real activate → stack → resolve path) ---

    def test_equip_zero_legal_targets_spends_no_mana(self):
        """No creature you control: activation is rejected before the cost is
        paid, so no mana leaves the pool and nothing goes on the stack."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1 = game.players[0]
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[boots], mana={ManaType.COLORLESS: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, boots)
        assert p1.mana_pool.total() == 1
        assert boots.attached_to is None
        assert game.stack.is_empty()

    def test_equip_target_disappears_before_resolution_no_retarget(self):
        """The equip target is chosen at activation. If it leaves before the
        ability resolves, the ability resolves without attaching and never
        retargets onto another creature."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1 = game.players[0]
        chosen = _creature("Chosen", p1, 2, 2)
        bystander = _creature("Bystander", p1, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(
            game, 0, battlefield=[chosen, bystander, boots],
            mana={ManaType.COLORLESS: 1},
        )
        game.phase = Phase.PRECOMBAT_MAIN
        _equip_via_ability(game, p1, boots, chosen)  # target = chosen, on stack
        assert not game.stack.is_empty()
        # The chosen target leaves before resolution.
        move_to_zone(game, chosen, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        resolve_stack(game)
        # No attach (target gone), and no retarget onto the bystander.
        assert boots.attached_to is None

    def test_creature_appearing_after_activation_cannot_be_target(self):
        """A creature that enters after activation cannot become the equip
        target: the ability attaches to the creature chosen at activation."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1 = game.players[0]
        chosen = _creature("Chosen", p1, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        newcomer = _creature("Newcomer", p1, 5, 5)
        set_board_state(
            game, 0, battlefield=[chosen, boots], hand=[newcomer],
            mana={ManaType.COLORLESS: 1},
        )
        game.phase = Phase.PRECOMBAT_MAIN
        _equip_via_ability(game, p1, boots, chosen)  # target = chosen
        # A new creature enters while the ability is on the stack.
        move_to_zone(game, newcomer, Zone.HAND, Zone.BATTLEFIELD)
        resolve_stack(game)
        assert boots.attached_to is chosen       # the activation-time target
        assert boots.attached_to is not newcomer

    def test_equip_illegal_timing_raises_no_query_no_cost(self):
        """Activation outside sorcery timing is rejected before any target query
        is raised — no query, no target intent consumed, no mana, nothing pushed."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, boots],
                        mana={ManaType.COLORLESS: 1})
        game.phase = Phase.COMBAT  # not sorcery speed
        calls, restore = _spy_on_answer(p1)
        try:
            with pytest.raises(AbilityError):
                _equip_via_ability(game, p1, boots, bear)
        finally:
            restore()
        assert calls == []                    # no target query raised
        assert p1.mana_pool.total() == 1      # no mana spent
        assert game.stack.is_empty()          # nothing pushed
        assert boots.attached_to is None

    def test_equip_source_off_battlefield_rejected_before_query(self):
        """Activation when the Equipment is not on the battlefield is rejected
        before querying or payment."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        # Boots in hand — not on the battlefield.
        set_board_state(game, 0, battlefield=[bear], hand=[boots],
                        mana={ManaType.COLORLESS: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        calls, restore = _spy_on_answer(p1)
        try:
            with pytest.raises(AbilityError):
                _equip_via_ability(game, p1, boots, bear)
        finally:
            restore()
        assert calls == []
        assert p1.mana_pool.total() == 1
        assert game.stack.is_empty()
        assert boots.attached_to is None

    def test_equipment_leaves_for_graveyard_before_resolution_no_attach(self):
        """Equipment leaves for the graveyard before resolution: the ability
        resolves without attaching; attached_to remains None."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, boots],
                        mana={ManaType.COLORLESS: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        _equip_via_ability(game, p1, boots, bear)
        assert not game.stack.is_empty()
        move_to_zone(game, boots, Zone.BATTLEFIELD, Zone.GRAVEYARD)  # source leaves
        resolve_stack(game)
        assert boots.attached_to is None
        assert game.get_graveyard(p1).contains(boots)

    def test_equipment_bounced_before_resolution_no_attach_in_hand(self):
        """Equipment is bounced before resolution: no attachment in hand."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, boots],
                        mana={ManaType.COLORLESS: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        _equip_via_ability(game, p1, boots, bear)
        move_to_zone(game, boots, Zone.BATTLEFIELD, Zone.HAND)  # bounce
        resolve_stack(game)
        assert boots.attached_to is None
        assert game.get_hand(p1).contains(boots)

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

    def test_target_leaves_and_returns_before_resolution_no_attach(self):
        """Target leaves and returns before resolution: no attachment to the new
        stint (the returned creature is a new object)."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, boots],
                        mana={ManaType.COLORLESS: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        _equip_via_ability(game, p1, boots, bear)
        move_to_zone(game, bear, Zone.BATTLEFIELD, Zone.GRAVEYARD)  # leaves
        move_to_zone(game, bear, Zone.GRAVEYARD, Zone.BATTLEFIELD)  # returns (new stint)
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

    def test_target_control_change_away_from_ability_controller_no_attach(self):
        """Target changes control away from the ability's controller before
        resolution: 'creature you control' no longer holds, so no attach."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1, p2 = game.players
        bear = _creature("Bear", p1, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, boots],
                        mana={ManaType.COLORLESS: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        _equip_via_ability(game, p1, boots, bear)  # ability controller = p1
        # The target changes control to the opponent (stint-preserving).
        bear.controller = p2
        resolve_stack(game)
        assert boots.attached_to is None

    def test_protected_creature_absent_from_activation_option_set(self):
        """A creature with protection from the Equipment is not in the activation
        option set, so with no other creature there is no legal target."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots
        from engine.protection import ProtectionAbility

        game = create_game()
        p1 = game.players[0]
        protected = _creature("Protected", p1, 2, 2)
        protected.protections = [ProtectionAbility(
            quality="artifacts",
            predicate=lambda src: CardType.ARTIFACT in getattr(src, "card_types", set()),
        )]
        boots = SwiftfootBoots(owner=p1, controller=p1)  # an artifact
        set_board_state(game, 0, battlefield=[protected, boots],
                        mana={ManaType.COLORLESS: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, boots)  # only creature is protected
        assert boots.attached_to is None
        assert p1.mana_pool.total() == 1  # no mana spent

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
        bear.protections = [ProtectionAbility(
            quality="artifacts",
            predicate=lambda src: CardType.ARTIFACT in getattr(src, "card_types", set()),
        )]
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

    def test_equipment_bounced_clears_state_and_re_equips(self):
        from cards.fdn.fdn_129.card_impl import LeylineAxe

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        axe = LeylineAxe(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, axe])
        axe.equip(bear, game)
        assert axe.attached_to is bear and bear.power == 3

        move_to_zone(game, axe, Zone.BATTLEFIELD, Zone.HAND)  # bounce
        assert axe.attached_to is None
        assert axe._equip_effect_refs == []
        assert bear.power == 2  # buff removed when the Equipment left

        # Replay it and re-equip normally.
        move_to_zone(game, axe, Zone.HAND, Zone.BATTLEFIELD)
        axe.equip(bear, game)
        assert axe.attached_to is bear and bear.power == 3

    def test_equipment_destroyed_then_exiled_then_blinked(self):
        """Destroy (→ graveyard), exile (graveyard → exile), and blink
        (exile → battlefield) all leave no stale attachment, and the blinked
        Equipment equips normally afterward."""
        from cards.fdn.fdn_129.card_impl import LeylineAxe

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        axe = LeylineAxe(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, axe])
        axe.equip(bear, game)

        move_to_zone(game, axe, Zone.BATTLEFIELD, Zone.GRAVEYARD)  # destroyed
        assert axe.attached_to is None and axe._equip_effect_refs == []
        assert bear.power == 2

        move_to_zone(game, axe, Zone.GRAVEYARD, Zone.EXILE)  # exiled from yard
        assert axe.attached_to is None

        move_to_zone(game, axe, Zone.EXILE, Zone.BATTLEFIELD)  # blinked back
        assert axe.attached_to is None
        axe.equip(bear, game)  # equips normally after the round trip
        assert axe.attached_to is bear and bear.power == 3

    def test_departure_runs_detach_hook_exactly_once(self):
        calls: list[int] = []

        class _CountingEquip(Equipment):
            def __init__(self, **kw):
                kw.setdefault("name", "Counting Rig")
                kw.setdefault("equip_cost", ManaCost())
                super().__init__(**kw)

            def on_detach(self, game):
                calls.append(1)

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        rig = _CountingEquip(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, rig])
        rig.equip(bear, game)
        move_to_zone(game, rig, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        check_state_based_actions(game)  # must not detach a second time
        assert calls == [1]
        assert rig.attached_to is None

    def test_equipped_creature_leaves_equipment_remains(self):
        from cards.fdn.fdn_129.card_impl import LeylineAxe

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        other = _creature("Other", p1, 2, 2)
        axe = LeylineAxe(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, other, axe])
        axe.equip(bear, game)

        move_to_zone(game, bear, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        check_state_based_actions(game)
        assert axe.attached_to is None
        assert game.get_battlefield(p1).contains(axe)  # Equipment stays
        assert axe._equip_effect_refs == []

        axe.equip(other, game)  # re-equips the surviving creature
        assert axe.attached_to is other and other.power == 3


# ---------------------------------------------------------------------------
# 4b. Activated-ability authorization
# ---------------------------------------------------------------------------

class TestActivationAuthorization:
    """The activating player is the ability's controller (rule 602.2), and only
    that player may activate it. Authorization is decided before any query,
    payment, source mutation, or stack push, and the authorized controller is
    captured on the stack object and never rewritten by a later control change
    of the source."""

    def test_opponent_cannot_activate_your_equipment(self):
        """Player B may not activate player A's Equipment. B controls a creature
        of its own and A has mana to pay — so under the pre-fix behaviour (derive
        the controller from ``source.controller``) the equip would have resolved,
        equipping A's creature out of A's pool at B's command. The control gate in
        ``can_activate`` now rejects it before any target query, mana, or push."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1, p2 = game.players
        a_bear = _creature("A's Bear", p1, 2, 2)          # p1's creature
        boots = SwiftfootBoots(owner=p1, controller=p1)   # p1 controls the Equipment
        b_bear = _creature("B's Bear", p2, 2, 2)          # p2 has its own creature
        set_board_state(game, 0, battlefield=[a_bear, boots],
                        mana={ManaType.COLORLESS: 1})
        set_board_state(game, 1, battlefield=[b_bear])
        game.phase = Phase.PRECOMBAT_MAIN
        calls1, restore1 = _spy_on_answer(p1)
        calls2, restore2 = _spy_on_answer(p2)
        try:
            with pytest.raises(AbilityError):
                activate_card_ability(game, p2, boots)  # B activates A's Equipment
        finally:
            restore1()
            restore2()
        assert calls1 == [] and calls2 == []   # no target query raised on anyone
        assert p1.mana_pool.total() == 1       # A's mana untouched
        assert game.stack.is_empty()           # nothing pushed
        assert boots.attached_to is None       # nothing attached

    def test_mismatched_ability_controller_is_rejected(self):
        """An ActivatedAbilityInstance whose declared controller differs from the
        activating player is rejected outright — the caller is not the ability's
        controller — before any query, payment, source mutation, or push. Under
        the pre-fix behaviour the declared controller was ignored (the source's
        current controller was used instead), so the stale/mismatched value went
        undetected."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        from engine.abilities import ActivatedAbilityInstance, activate_ability

        game = create_game()
        p1, p2 = game.players
        bear = _creature("Bear", p1, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, boots],
                        mana={ManaType.COLORLESS: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        ability = boots.get_activated_abilities()[0]
        instance = ActivatedAbilityInstance(
            source=boots,
            controller=p1,          # declared controller: p1 ...
            cost=ability.cost,
            effect=ability.effect,
            targeting=ability.targeting,
            can_activate=ability.can_activate,
            description=ability.description,
        )
        calls1, restore1 = _spy_on_answer(p1)
        calls2, restore2 = _spy_on_answer(p2)
        try:
            with pytest.raises(AbilityError):
                activate_ability(game, p2, instance)   # ... but the caller is p2
        finally:
            restore1()
            restore2()
        assert calls1 == [] and calls2 == []   # no target query raised
        assert p1.mana_pool.total() == 1       # no mana spent
        assert game.stack.is_empty()           # nothing pushed
        assert boots.attached_to is None       # source unmutated

    def test_valid_activation_targets_pays_and_resolves(self):
        """The happy path is unaffected: the controller activating their own
        Equipment raises the target query, pays the cost, pushes with the
        authorized controller on the stack object, and resolves into a real
        attachment."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, boots],
                        mana={ManaType.COLORLESS: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        calls, restore = _spy_on_answer(p1)
        try:
            _equip_via_ability(game, p1, boots, bear)   # activate + push
        finally:
            restore()
        assert calls != []                     # a target query WAS raised
        assert p1.mana_pool.total() == 0       # the cost was paid
        assert not game.stack.is_empty()       # object pushed
        top = game.stack.peek()
        assert top.controller is p1            # authorized controller on the stack
        assert top.activation_context.controller is p1
        resolve_stack(game)
        assert boots.attached_to is bear       # resolves into an attachment
        assert Keyword.HEXPROOF in bear.keywords  # ... with the buff applied

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

class TestCostSystem:
    def test_battlefield_reduction_sweep(self):
        from cards.fdn.fdn_30.card_impl import ArchmageOfRunes

        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[ArchmageOfRunes(owner=p1, controller=p1)])
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{2}{R}"), owner=p1, controller=p1)
        assert get_cost_reduction(game, bolt, p1) == 1

    def test_two_reducers_stack(self):
        from cards.fdn.fdn_159.card_impl import MockingSprite
        from cards.fdn.fdn_30.card_impl import ArchmageOfRunes

        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[
            ArchmageOfRunes(owner=p1, controller=p1),
            MockingSprite(owner=p1, controller=p1),
        ])
        sorc = Sorcery(name="S", mana_cost=ManaCost.parse("{4}"), owner=p1, controller=p1)
        assert get_cost_reduction(game, sorc, p1) == 2

    def test_reduction_never_touches_colored_pips(self):
        from cards.fdn.fdn_30.card_impl import ArchmageOfRunes

        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[ArchmageOfRunes(owner=p1, controller=p1)])
        pure = Instant(name="Pure", mana_cost=ManaCost.parse("{R}"), owner=p1, controller=p1)
        assert get_cost_reduction(game, pure, p1) == 0  # generic already 0

    def test_target_aware_self_reduction(self):
        from cards.fdn.fdn_20.card_impl import LuminousRebuke

        game = create_game()
        p1 = game.players[0]
        tapped = _creature("Tapped", p1, 1, 1)
        tapped.is_tapped = True
        untapped = _creature("Untapped", p1, 1, 1)
        set_board_state(game, 0, battlefield=[tapped, untapped])
        rebuke = LuminousRebuke(owner=p1, controller=p1)
        assert get_cost_reduction(game, rebuke, p1, targets=[tapped]) == 3
        assert get_cost_reduction(game, rebuke, p1, targets=[untapped]) == 0
        assert get_cost_reduction(game, rebuke, p1, targets=None) == 0

    def test_alternative_cost_offered_only_at_threshold(self):
        from cards.fdn.fdn_57.card_impl import BlasphemousEdict

        game = create_game()
        p1 = game.players[0]
        edict = BlasphemousEdict(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[_creature(f"C{i}", p1, 1, 1) for i in range(12)])
        assert edict.alternative_costs(game) == []
        set_board_state(game, 0, battlefield=[_creature(f"C{i}", p1, 1, 1) for i in range(13)])
        assert edict.alternative_costs(game) == [ManaCost.parse("{B}")]

    def test_cast_pays_chosen_alternative_cost(self):
        from cards.fdn.fdn_57.card_impl import BlasphemousEdict

        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        edict = BlasphemousEdict(owner=p1, controller=p1)
        set_board_state(
            game, 0,
            battlefield=[_creature(f"C{i}", p1, 1, 1) for i in range(13)],
            hand=[edict],
            mana={ManaType.BLACK: 1},
        )
        p1.start_intent("edict", Intent(
            pattern=GameRef(card=frozenset({("name", "Blasphemous Edict")})),
            preferences=(Decision.ability(index=1),),  # choose the {B} alternative
        ))
        cast_spell(game, p1, edict)
        p1.end_intent("edict")
        # {B} was paid (not {3}{B}{B}); the spell is on the stack.
        assert p1.mana_pool.total() == 0
        assert game.stack.peek().source is edict

    # --- Cost selection: normal vs alternative, payability, and reduction ---

    def _dual_cost_sorcery(self, p, *, normal="{2}{R}", alt="{G}{G}"):
        """A sorcery with a normal cost and a single alternative cost that is
        not a subset of it — so the three payability cases are distinguishable."""
        alt_cost = ManaCost.parse(alt)

        class _DualCostSorcery(Sorcery):
            def __init__(self, **kw):
                kw.setdefault("name", "Dual Cost Sorcery")
                kw.setdefault("mana_cost", ManaCost.parse(normal))
                super().__init__(**kw)

            def alternative_costs(self, game):
                return [alt_cost]

        return _DualCostSorcery(owner=p, controller=p)

    def test_cast_only_normal_cost_payable(self):
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        spell = self._dual_cost_sorcery(p1)  # {2}{R} normal, {G}{G} alt
        set_board_state(game, 0, hand=[spell],
                        mana={ManaType.RED: 1, ManaType.COLORLESS: 2})
        cast_spell(game, p1, spell)  # can pay {2}{R}, not {G}{G} -> pays normal
        assert p1.mana_pool.total() == 0
        assert game.stack.peek().source is spell

    def test_cast_only_alternative_cost_payable(self):
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        spell = self._dual_cost_sorcery(p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.GREEN: 2})
        cast_spell(game, p1, spell)  # can't pay {2}{R}, can pay {G}{G} -> pays alt
        assert p1.mana_pool.total() == 0
        assert game.stack.peek().source is spell

    def test_cast_neither_cost_payable_raises(self):
        from engine.casting import CastingError

        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        spell = self._dual_cost_sorcery(p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        with pytest.raises(CastingError):
            cast_spell(game, p1, spell)  # neither {2}{R} nor {G}{G} payable
        assert game.get_hand(p1).contains(spell)  # rolled back to hand
        assert game.stack.is_empty()

    def test_alternative_cost_with_multiple_reducers_clamps_generic_only(self):
        """Two battlefield reducers ({1} each) reduce whichever base cost is
        selected. Selecting the {2}{G} alternative, the {2} reduction is clamped
        to that cost's generic (→ {G}); the green pip is never reduced."""
        from cards.fdn.fdn_159.card_impl import MockingSprite
        from cards.fdn.fdn_30.card_impl import ArchmageOfRunes

        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        spell = self._dual_cost_sorcery(p1, normal="{4}{R}", alt="{2}{G}")
        set_board_state(game, 0, hand=[spell], mana={ManaType.GREEN: 1})
        # Reducers must be on the battlefield without disturbing the hand.
        game.get_battlefield(p1).add(ArchmageOfRunes(owner=p1, controller=p1))
        game.get_battlefield(p1).add(MockingSprite(owner=p1, controller=p1))
        # normal reduces to {2}{R} (unpayable — no red); alt reduces to {G}
        # (payable). Only the reduced alt is payable, so it is chosen.
        cast_spell(game, p1, spell)
        assert p1.mana_pool.total() == 0  # exactly {G} paid: generic gone, pip intact
        assert game.stack.peek().source is spell

    def test_reduction_applies_to_selected_normal_cost_pip_intact(self):
        """When the normal cost is the payable choice, the reduction lands on
        its generic component and leaves its colored pip untouched."""
        from cards.fdn.fdn_30.card_impl import ArchmageOfRunes

        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        spell = self._dual_cost_sorcery(p1, normal="{2}{R}", alt="{G}{G}")
        set_board_state(game, 0, hand=[spell],
                        mana={ManaType.RED: 1, ManaType.COLORLESS: 1})
        game.get_battlefield(p1).add(ArchmageOfRunes(owner=p1, controller=p1))
        # {2}{R} - {1} = {1}{R}; the player has exactly {1}{R} (no green for alt).
        cast_spell(game, p1, spell)
        assert p1.mana_pool.total() == 0
        assert game.stack.peek().source is spell


# ---------------------------------------------------------------------------
# 6. Token creation replacement + identity
# ---------------------------------------------------------------------------

class TestTokenCreation:
    def test_creation_replacement_doubles(self):
        game = create_game()
        p1 = game.players[0]

        def _double(g, e):
            e.count *= 2
            return e

        game.replacement_manager.register(ReplacementEffect(
            event_type=CreateTokenReplacementEvent, source=object(),
            condition=None, replacement=_double,
        ))
        token = _creature("Soldier", p1, 1, 1)
        placed = create_token(game, p1, token)
        assert len(placed) == 2
        soldiers = [o for o in game.get_battlefield(p1).get_all()
                    if getattr(o, "name", "") == "Soldier"]
        assert len(soldiers) == 2
        assert placed[0] is not placed[1]
        assert placed[0].object_id != placed[1].object_id  # distinct identity

    def test_identity_hook_grp_id(self):
        game = create_game()
        p1 = game.players[0]
        token = _creature("Beast", p1, 3, 3)
        create_token(game, p1, token, grp_id=98765)
        assert token._grp_id == 98765

    def test_factory_mints_distinct_tokens(self):
        game = create_game()
        p1 = game.players[0]
        placed = create_token(
            game, p1,
            factory=lambda: Creature(name="Elf", base_power=1, base_toughness=1),
            count=3,
        )
        assert len(placed) == 3
        assert len({o.object_id for o in placed}) == 3
