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

import test_interface
from cards.fdn.fdn_30.card_impl import ArchmageOfRunes, ArchmageOfRunesAbility2
from cards.fdn.fdn_40.card_impl import HighFaeTrickster
from cards.fdn.fdn_57.card_impl import BlasphemousEdict, BlasphemousEdictAbility1
from cards.fdn.fdn_71.card_impl import Stab
from cards.fdn.fdn_130.card_impl import QuickDrawKatana, QuickDrawKatanaAbility2
from cards.fdn.fdn_143.card_impl import MakeYourMove
from cards.fdn.fdn_144.card_impl import MischievousPup, MischievousPupAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_159.card_impl import MockingSprite
from cards.fdn.fdn_162.card_impl import RunAwayTogether
from cards.fdn.fdn_164.card_impl import SpectralSailor
from cards.fdn.fdn_188.card_impl import Abrade, AbradeAbility2, AbradeAbility3
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_209.card_impl import SureStrike
from cards.fdn.fdn_223.card_impl import GiantGrowth
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_244.card_impl import Progenitus
from cards.fdn.fdn_249.card_impl import (
    AdventuringGear,
    AdventuringGearAbility1,
    AdventuringGearAbility2,
)
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_276.card_impl import Swamp
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.fdn_280.card_impl import Forest
from test_interface import Side, card, player
from test_utils import (
    Intent,
    activate_card_ability,
    create_game,
    set_board_state,
)

from engine.card import Creature, Equipment, Instant, Sorcery, printed_class
from engine.casting import get_cost_reduction
from engine.continuous_effects import (
    DURATION_PERMANENT,
    ContinuousEffect,
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
from engine.game import add_counter, create_token, gain_life, lose_life
from engine.replacement_effects import ReplacementEffect
from engine.state_based_actions import check_state_based_actions
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, Zone
from engine.zones import move_to_zone
from table import (
    Table,
    appears,
    first_strike_damage,
    gains_control,
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
        """Adventuring Gear's landfall buff applies as soon as its trigger
        resolves: the equipped 1/1 Elves blocked by a 2/1 survives and kills it."""
        elves, gear, forest, blocker = card(LlanowarElves), card(AdventuringGear), card(Forest), card(SavannahLions)
        t = _table(Side(hand=[forest], battlefield=[elves, gear], mana={ManaType.COLORLESS: 1}), Side(battlefield=[blocker]))
        t.act(0, AdventuringGearAbility2, choices=[elves], then=[on_stack(AdventuringGearAbility2, 0)])
        _resolve(t, off_stack(AdventuringGearAbility2))
        t.act(0, forest, then=[moves(forest, Zone.BATTLEFIELD), on_stack(AdventuringGearAbility1, 0)])
        _resolve(t, off_stack(AdventuringGearAbility1))
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, elves, then=[taps(elves)])
        t.pass_(0)
        t.pass_(1)
        t.act(1, blocker, scoped={blocker: elves})
        t.pass_(0)
        t.pass_(1, then=[moves(blocker, Zone.GRAVEYARD)], note="the Elves is a 3/3 this turn")
        t.run()



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
        """Giant Growth resolves first, so the 2/1 Lions is a 5/4 when Burst
        Lightning's 2 damage is checked against it."""
        lions, growth, bolt = card(SavannahLions), card(GiantGrowth), card(BurstLightning)
        t = _table(
            Side(hand=[growth], battlefield=[lions], mana={ManaType.GREEN: 1}),
            Side(hand=[bolt], mana={ManaType.RED: 1}),
        )
        t.pass_(0)
        t.act(1, bolt, choices=[lions], then=[moves(bolt, Zone.STACK)])
        t.pass_(1)
        t.act(0, growth, choices=[lions], then=[moves(growth, Zone.STACK)])
        _resolve(t, moves(growth, Zone.GRAVEYARD))
        _resolve(t, moves(bolt, Zone.GRAVEYARD), note="the Lions survives 2 damage")
        t.run()

    def test_resolving_debuff_kills_creature_before_priority(self):
        stab, lions = card(Stab), card(SavannahLions)
        t = _table(Side(hand=[stab], mana={ManaType.BLACK: 1}), Side(battlefield=[lions]))
        t.act(0, stab, choices=[lions], then=[moves(stab, Zone.STACK)])
        _resolve(t, moves(stab, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD), note="the Lions is gone before anyone gets priority")
        t.run()

    def test_removing_last_effect_during_resolution_resets(self):
        """Abrade destroys the Quick-Draw Katana, and its +2/+0 is gone at once:
        the Lions then attacks for 2."""
        lions, katana, abrade = card(SavannahLions), card(QuickDrawKatana), card(Abrade)
        t = _table(
            Side(battlefield=[lions, katana], mana={ManaType.COLORLESS: 2}),
            Side(hand=[abrade], mana={ManaType.RED: 2}),
        )
        _equip(t, katana_on=lions)
        t.pass_(0)
        t.act(1, abrade, choices=[AbradeAbility3, katana], then=[moves(abrade, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(abrade, Zone.GRAVEYARD), moves(katana, Zone.GRAVEYARD)])
        _attack_unblocked(t, lions, life_after=18)
        t.run()

    def test_casting_resolve_top_matches_priority_loop_settlement(self):
        """The opponent's Stab settles the same way: the Lions dies before the
        active player gets priority again."""
        stab, lions = card(Stab), card(SavannahLions)
        t = _table(Side(battlefield=[lions]), Side(hand=[stab], mana={ManaType.BLACK: 1}))
        t.pass_(0)
        t.act(1, stab, choices=[lions], then=[moves(stab, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(stab, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)])
        t.run()

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
    def test_attach_buffs_then_detach_removes(self):
        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        axe = _TestAxe(owner=p1, controller=p1)
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
        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        axe = _TestAxe(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, axe])
        axe.equip(bear, game)
        move_to_zone(game, bear, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        check_state_based_actions(game)
        assert axe.attached_to is None

    def test_equip_ability_targets_only_your_creatures(self):
        """Only the opponent controls a creature, so equip cannot be activated;
        the mana stays to cast Abrade at that creature."""
        katana, theirs, abrade = card(QuickDrawKatana), card(SavannahLions), card(Abrade)
        t = _table(Side(hand=[abrade], battlefield=[katana], mana={ManaType.RED: 2}), Side(battlefield=[theirs]))
        t.act_illegal(0, QuickDrawKatanaAbility2, choices=[theirs], note="equip targets only a creature you control")
        t.act(0, abrade, choices=[AbradeAbility2, theirs], then=[moves(abrade, Zone.STACK)])
        _resolve(t, moves(abrade, Zone.GRAVEYARD), moves(theirs, Zone.GRAVEYARD))
        t.run()

    def test_equip_ability_is_sorcery_speed(self):
        """Equip cannot be activated in the opponent's end step, and can be in
        player 0's own main phase: the equipped Lions attacks for 4."""
        lions, katana = card(SavannahLions), card(QuickDrawKatana)
        plains = [card(Plains), card(Plains)]
        t = Table(test_interface.create_game(
            Side(battlefield=[lions, katana, *plains], library=[card(Plains)]),
            Side(),
            start=(Step.END, 1),
        ))
        t.pass_(1)
        for land in plains:
            t.act(0, land, then=[taps(land)])
        t.act_illegal(0, QuickDrawKatanaAbility2, choices=[lions], note="not player 0's main phase")
        t.pass_(0)
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        _equip(t, katana_on=lions, lands=plains)
        _attack_unblocked(t, lions, life_after=16, first_strike=True)
        t.run()

    # --- Equip activation targeting (real activate → stack → resolve path) ---

    def test_equip_zero_legal_targets_spends_no_mana(self):
        """With no creature to equip, equip cannot be activated, and both red
        mana stay to cast two Burst Lightnings."""
        katana, first, second = card(QuickDrawKatana), card(BurstLightning), card(BurstLightning)
        t = _table(Side(hand=[first, second], battlefield=[katana], mana={ManaType.RED: 2}), Side())
        t.act_illegal(0, QuickDrawKatanaAbility2, note="no creature to equip")
        for bolt, total in ((first, 18), (second, 16)):
            t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
            _resolve(t, moves(bolt, Zone.GRAVEYARD), life(1, total))
        t.run()

    def test_equip_target_disappears_before_resolution_no_retarget(self):
        """The chosen Lions dies before equip resolves; the Katana attaches to
        nothing, so the Elves attacks for 1."""
        chosen, bystander, katana, bolt = card(SavannahLions), card(LlanowarElves), card(QuickDrawKatana), card(BurstLightning)
        t = _table(Side(hand=[bolt], battlefield=[chosen, bystander, katana], mana={ManaType.RED: 3}), Side())
        t.act(0, QuickDrawKatanaAbility2, choices=[chosen], then=[on_stack(QuickDrawKatanaAbility2, 0)])
        t.act(0, bolt, choices=[chosen], then=[moves(bolt, Zone.STACK)])
        _resolve(t, moves(bolt, Zone.GRAVEYARD), moves(chosen, Zone.GRAVEYARD))
        _resolve(t, off_stack(QuickDrawKatanaAbility2))
        _attack_unblocked(t, bystander, life_after=19)
        t.run()

    def test_creature_appearing_after_activation_cannot_be_target(self):
        """Spectral Sailor enters while equip waits; the Katana still goes on
        the Lions, which attacks for 4."""
        chosen, katana, sailor, island = card(SavannahLions), card(QuickDrawKatana), card(SpectralSailor), card(Island)
        plains = [card(Plains), card(Plains)]
        t = _table(Side(hand=[sailor], battlefield=[chosen, katana, island, *plains]), Side())
        for land in plains:
            t.act(0, land, then=[taps(land)])
        t.act(0, QuickDrawKatanaAbility2, choices=[chosen], then=[on_stack(QuickDrawKatanaAbility2, 0)])
        t.act(0, island, then=[taps(island)])
        t.act(0, sailor, then=[moves(sailor, Zone.STACK)])
        _resolve(t, moves(sailor, Zone.BATTLEFIELD))
        _resolve(t, off_stack(QuickDrawKatanaAbility2))
        _attack_unblocked(t, chosen, life_after=16, first_strike=True)
        t.run()

    def test_equip_illegal_timing_raises_no_query_no_cost(self):
        """Equip cannot be activated in the beginning of combat step, and the
        mana stays to cast Sure Strike: the Lions attacks for 5."""
        lions, katana, strike = card(SavannahLions), card(QuickDrawKatana), card(SureStrike)
        t = Table(test_interface.create_game(
            Side(hand=[strike], battlefield=[lions, katana], mana={ManaType.RED: 2}),
            Side(),
            start=(Step.BEGIN_COMBAT, 0),
        ))
        t.act_illegal(0, QuickDrawKatanaAbility2, choices=[lions], note="not a main phase")
        t.act(0, strike, choices=[lions], then=[moves(strike, Zone.STACK)])
        _resolve(t, moves(strike, Zone.GRAVEYARD))
        _attack_unblocked(t, lions, life_after=15, first_strike=True)
        t.run()

    def test_equip_source_off_battlefield_rejected_before_query(self):
        """The Katana in hand has no equip to activate, and the mana stays to
        cast it."""
        lions, katana = card(SavannahLions), card(QuickDrawKatana)
        t = _table(Side(hand=[katana], battlefield=[lions], mana={ManaType.COLORLESS: 2}), Side())
        t.act_illegal(0, QuickDrawKatanaAbility2, choices=[lions], note="the Katana is not on the battlefield")
        t.act(0, katana, then=[moves(katana, Zone.STACK)])
        _resolve(t, moves(katana, Zone.BATTLEFIELD))
        t.run()

    def test_equipment_leaves_for_graveyard_before_resolution_no_attach(self):
        """Make Your Move destroys the Katana while equip waits; equip attaches
        nothing, and the Lions attacks for 2."""
        lions, katana, move = card(SavannahLions), card(QuickDrawKatana), card(MakeYourMove)
        t = _table(
            Side(battlefield=[lions, katana], mana={ManaType.COLORLESS: 2}),
            Side(hand=[move], mana={ManaType.WHITE: 3}),
        )
        t.act(0, QuickDrawKatanaAbility2, choices=[lions], then=[on_stack(QuickDrawKatanaAbility2, 0)])
        t.pass_(0)
        t.act(1, move, choices=[katana], then=[moves(move, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(move, Zone.GRAVEYARD), moves(katana, Zone.GRAVEYARD)])
        _resolve(t, off_stack(QuickDrawKatanaAbility2))
        _attack_unblocked(t, lions, life_after=18)
        t.run()

    def test_equipment_bounced_before_resolution_no_attach_in_hand(self):
        """Mischievous Pup returns the Katana to its owner's hand while equip
        waits: equip attaches nothing, and the Katana stays in hand."""
        lions, katana, pup = card(SavannahLions), card(QuickDrawKatana), card(MischievousPup)
        plains = [card(Plains) for _ in range(3)]
        t = _table(Side(hand=[pup], battlefield=[lions, katana, *plains], mana={ManaType.COLORLESS: 2}), Side())
        t.act(0, QuickDrawKatanaAbility2, choices=[lions], then=[on_stack(QuickDrawKatanaAbility2, 0)])
        for land in plains:
            t.act(0, land, then=[taps(land)])
        t.act(0, pup, then=[moves(pup, Zone.STACK)])
        t.pass_(0, choices=[katana])
        t.pass_(1, then=[moves(pup, Zone.BATTLEFIELD), on_stack(MischievousPupAbility2, 0)])
        _resolve(t, off_stack(MischievousPupAbility2), moves(katana, Zone.HAND))
        _resolve(t, off_stack(QuickDrawKatanaAbility2), note="the Katana is in hand: nothing attaches")
        final = t.run()
        assert final.where(katana) is Zone.HAND


    def test_target_leaves_and_returns_before_resolution_no_attach(self):
        """Run Away Together returns the chosen Spectral Sailor to hand and it
        is cast again before equip resolves; the returned Sailor is a new
        object, so it attacks next turn for 1."""
        sailor, katana, together, theirs, island = (
            card(SpectralSailor), card(QuickDrawKatana), card(RunAwayTogether), card(SavannahLions), card(Island)
        )
        t = _table(
            Side(hand=[together], battlefield=[sailor, katana, island], library=[card(Plains)], mana={ManaType.BLUE: 4}),
            Side(battlefield=[theirs], library=[card(Plains)]),
        )
        t.act(0, QuickDrawKatanaAbility2, choices=[sailor], then=[on_stack(QuickDrawKatanaAbility2, 0)])
        t.act(0, together, choices=[sailor, theirs], distinct=True, then=[moves(together, Zone.STACK)])
        _resolve(t, moves(together, Zone.GRAVEYARD), moves(sailor, Zone.HAND), moves(theirs, Zone.HAND))
        t.act(0, island, then=[taps(island)])
        t.act(0, sailor, then=[moves(sailor, Zone.STACK)])
        _resolve(t, moves(sailor, Zone.BATTLEFIELD))
        _resolve(t, off_stack(QuickDrawKatanaAbility2))
        t.pass_to(Step.END, 0)
        _attack_unblocked(t, sailor, life_after=19)
        t.run()


    def test_target_control_change_away_from_ability_controller_no_attach(self):
        """Player 1, with High Fae Trickster, casts Involuntary Employment on
        the Lions while equip waits: "creature you control" no longer holds,
        so equip attaches nothing, and the Lions, back with player 0 the next
        turn, attacks for 2."""
        lions, katana, employment = card(SavannahLions), card(QuickDrawKatana), card(InvoluntaryEmployment)
        mountains = [card(Mountain) for _ in range(4)]
        t = _table(
            Side(battlefield=[lions, katana], mana={ManaType.COLORLESS: 2}, library=[card(Plains)]),
            Side(hand=[employment], battlefield=[card(HighFaeTrickster), *mountains], library=[card(Plains)]),
        )
        t.act(0, QuickDrawKatanaAbility2, choices=[lions], then=[on_stack(QuickDrawKatanaAbility2, 0)])
        t.pass_(0)
        for mountain in mountains:
            t.act(1, mountain, then=[taps(mountain)])
        t.act(1, employment, choices=[lions], then=[moves(employment, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(employment, Zone.GRAVEYARD), gains_control(lions, 1), appears(1)])
        _resolve(t, off_stack(QuickDrawKatanaAbility2), note="the Lions is no longer player 0's: nothing attaches")
        t.pass_to(Step.END, 0)
        t.pass_(0)
        t.pass_(1, then=[gains_control(lions, 0)], note="Involuntary Employment's control ends at cleanup")
        _attack_unblocked(t, lions, life_after=18)
        t.run()

    def test_protected_creature_absent_from_activation_option_set(self):
        """Progenitus has protection from everything, so it cannot be equipped;
        both red mana stay to cast two Burst Lightnings."""
        katana, first, second = card(QuickDrawKatana), card(BurstLightning), card(BurstLightning)
        progenitus = card(Progenitus)
        t = _table(Side(hand=[first, second], battlefield=[progenitus, katana], mana={ManaType.RED: 2}), Side())
        t.act_illegal(0, QuickDrawKatanaAbility2, choices=[progenitus], note="protection from everything")
        for bolt, total in ((first, 18), (second, 16)):
            t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
            _resolve(t, moves(bolt, Zone.GRAVEYARD), life(1, total))
        t.run()



    # --- Equipment departure lifecycle ---

    def test_equipment_bounced_clears_state_and_re_equips(self):
        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        axe = _TestAxe(owner=p1, controller=p1)
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
        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        axe = _TestAxe(owner=p1, controller=p1)
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
        game = create_game()
        p1 = game.players[0]
        bear = _creature("Bear", p1, 2, 2)
        other = _creature("Other", p1, 2, 2)
        axe = _TestAxe(owner=p1, controller=p1)
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
        """In their own main phase player 1 cannot activate player 0's Katana;
        player 0's red mana stays to cast two Burst Lightnings."""
        katana, theirs = card(QuickDrawKatana), card(SavannahLions)
        first, second = card(BurstLightning), card(BurstLightning)
        t = Table(test_interface.create_game(
            Side(hand=[first, second], battlefield=[SavannahLions, katana], mana={ManaType.RED: 2}),
            Side(battlefield=[theirs], mana={ManaType.COLORLESS: 2}),
            start=(Phase.PRECOMBAT_MAIN, 1),
        ))
        t.act_illegal(1, QuickDrawKatanaAbility2, choices=[theirs], note="player 0 controls the Katana")
        for bolt, total in ((first, 18), (second, 16)):
            t.pass_(1)
            t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
            t.pass_(0)
            t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, total)])
        t.run()

    def test_mismatched_ability_controller_is_rejected(self):
        """While player 0's equip waits, player 1 cannot activate the same
        Katana for their own creature; player 0's equip resolves."""
        lions, katana, theirs = card(SavannahLions), card(QuickDrawKatana), card(SavannahLions)
        t = _table(
            Side(battlefield=[lions, katana], mana={ManaType.COLORLESS: 2}),
            Side(battlefield=[theirs], mana={ManaType.COLORLESS: 2}),
        )
        t.act(0, QuickDrawKatanaAbility2, choices=[lions], then=[on_stack(QuickDrawKatanaAbility2, 0)])
        t.pass_(0)
        t.act_illegal(1, QuickDrawKatanaAbility2, choices=[theirs], note="player 0 controls the Katana")
        t.pass_(1, then=[off_stack(QuickDrawKatanaAbility2)])
        _attack_unblocked(t, lions, life_after=16, first_strike=True)
        t.run()

    def test_valid_activation_targets_pays_and_resolves(self):
        lions, katana = card(SavannahLions), card(QuickDrawKatana)
        plains = [card(Plains), card(Plains)]
        t = _table(Side(battlefield=[lions, katana, *plains]), Side())
        _equip(t, katana_on=lions, lands=plains)
        _attack_unblocked(t, lions, life_after=16, first_strike=True)
        t.run()



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
        from cards.fdn.fdn_30.card_impl import ArchmageOfRunes
        from cards.fdn.fdn_159.card_impl import MockingSprite

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
        """With thirteen creatures out, four black and one red mana pay either
        of Blasphemous Edict's costs; choosing the {B} leaves the red to cast
        Burst Lightning."""
        edict, bolt = card(BlasphemousEdict), card(BurstLightning)
        mine, theirs = _creatures(7), _creatures(6)
        t = _table(
            Side(hand=[edict, bolt], battlefield=mine, mana={ManaType.BLACK: 4, ManaType.RED: 1}),
            Side(battlefield=theirs),
        )
        t.act(0, edict, choices=[BlasphemousEdictAbility1], then=[moves(edict, Zone.STACK)])
        _edict_resolves(t, edict, mine, theirs)
        t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
        _resolve(t, moves(bolt, Zone.GRAVEYARD), life(1, 18))
        t.run()

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
        """Twelve creatures leave Blasphemous Edict only its normal cost, which
        five black mana pay."""
        edict = card(BlasphemousEdict)
        mine, theirs = _creatures(6), _creatures(6)
        t = _table(Side(hand=[edict], battlefield=mine, mana={ManaType.BLACK: 5}), Side(battlefield=theirs))
        t.act(0, edict, then=[moves(edict, Zone.STACK)])
        _edict_resolves(t, edict, mine, theirs)
        t.run()

    def test_cast_only_alternative_cost_payable(self):
        edict = card(BlasphemousEdict)
        mine, theirs = _creatures(7), _creatures(6)
        t = _table(Side(hand=[edict], battlefield=mine, mana={ManaType.BLACK: 1}), Side(battlefield=theirs))
        t.act(0, edict, then=[moves(edict, Zone.STACK)], note="one black mana pays only the alternative cost")
        _edict_resolves(t, edict, mine, theirs)
        t.run()

    def test_cast_neither_cost_payable_raises(self):
        """With twelve creatures and one black mana neither cost can be paid;
        the Edict stays in hand and the mana casts Stab."""
        edict, stab = card(BlasphemousEdict), card(Stab)
        mine, theirs = _creatures(6), _creatures(6)
        t = _table(Side(hand=[edict, stab], battlefield=mine, mana={ManaType.BLACK: 1}), Side(battlefield=theirs))
        t.act_illegal(0, edict, note="neither {3}{B}{B} nor the alternative {B} is available")
        t.act(0, stab, choices=[theirs[0]], then=[moves(stab, Zone.STACK)])
        _resolve(t, moves(stab, Zone.GRAVEYARD), moves(theirs[0], Zone.GRAVEYARD))
        t.run()

    def test_alternative_cost_with_multiple_reducers_clamps_generic_only(self):
        """Archmage of Runes and Mocking Sprite take {2} off, but the
        alternative {B} has no generic to reduce: the Edict cannot be cast
        without black mana, and is cast once a Swamp, played from hand, is
        tapped."""
        edict, swamp, drawn = card(BlasphemousEdict), card(Swamp), card(Plains)
        mine = [card(ArchmageOfRunes), card(MockingSprite), *_creatures(5)]
        theirs = _creatures(6)
        t = _table(Side(hand=[edict, swamp], battlefield=mine, library=[drawn]), Side(battlefield=theirs))
        t.act_illegal(0, edict, note="the reduction never pays the {B}")
        t.act(0, swamp, then=[moves(swamp, Zone.BATTLEFIELD)])
        t.act(0, swamp, then=[taps(swamp)])
        t.act(0, edict, then=[moves(edict, Zone.STACK), on_stack(ArchmageOfRunesAbility2, 0)])
        _resolve(t, off_stack(ArchmageOfRunesAbility2), moves(drawn, Zone.HAND))
        _edict_resolves(t, edict, mine, theirs)
        t.run()

    def test_reduction_leaves_both_black_pips(self):
        """Archmage of Runes makes the Edict's normal cost {2}{B}{B}: with
        twelve creatures, one black and three white mana, and no other source,
        it cannot be cast."""
        edict = card(BlasphemousEdict)
        mine, theirs = [card(ArchmageOfRunes), *_creatures(5)], _creatures(6)
        t = _table(
            Side(hand=[edict], battlefield=mine, mana={ManaType.BLACK: 1, ManaType.WHITE: 3}),
            Side(battlefield=theirs),
        )
        t.act_illegal(0, edict, note="the reduction leaves both {B} pips")
        t.run()

    def test_reduction_applies_to_selected_normal_cost_pip_intact(self):
        """Archmage of Runes makes the Edict's normal cost {2}{B}{B}: with
        twelve creatures, exactly two black and two white mana cast it."""
        edict, drawn = card(BlasphemousEdict), card(Plains)
        mine, theirs = [card(ArchmageOfRunes), *_creatures(5)], _creatures(6)
        t = _table(
            Side(hand=[edict], battlefield=mine, library=[drawn], mana={ManaType.BLACK: 2, ManaType.WHITE: 2}),
            Side(battlefield=theirs),
        )
        t.act(0, edict, then=[moves(edict, Zone.STACK), on_stack(ArchmageOfRunesAbility2, 0)])
        _resolve(t, off_stack(ArchmageOfRunesAbility2), moves(drawn, Zone.HAND))
        _edict_resolves(t, edict, mine, theirs)
        t.run()

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
