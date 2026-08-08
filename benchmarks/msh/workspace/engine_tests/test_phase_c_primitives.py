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

from engine.card import Creature, Instant, Sorcery
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
from engine.state_based_actions import check_state_based_actions
from engine.triggers import TriggerRegistration
from engine.turn import cleanup_mechanical
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state


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
        opponent's creatures."""
        from cards.fdn.fdn_258.card_impl import SwiftfootBoots

        game = create_game()
        p1, p2 = game.players
        their_bear = _creature("Their Bear", p2, 2, 2)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[boots])
        set_board_state(game, 1, battlefield=[their_bear])
        ability = boots.get_activated_abilities()[0]
        ability.effect(game)  # no creature you control -> no attach
        assert boots.attached_to is None

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
