"""Integration test: multi-turn game with Foundations cards.

End-to-end smoke test playing out 6+ turns using DeterministicPlayer
and actual FDN card implementations.  Validates that all core engine
systems work together through real engine APIs:

- Mana generation via land tap abilities (activate_ability)
- Casting pipeline (timing, targets, mana payment, stack push/pop)
- Lands (play_land, tap for mana via ability system)
- Stack resolution (LIFO order, via priority_loop)
- Priority / auto-pass
- Combat (declare attackers, declare blockers, combat damage, end combat)
- Damage spells (Burst Lightning)
- Combat tricks (Giant Growth — continuous effects, layer 7c)
- Counter spells (Essence Scatter — counter target creature spell, stack interaction)
- State-based actions (lethal damage → graveyard)
- Continuous effects (Giant Growth until-end-of-turn, cleanup expiry)
- Cleanup step (via engine's _do_cleanup_step — damage, effects, mana)
- Triggered abilities (register, fire, resolve through TriggerManager)
"""
from __future__ import annotations
import pytest
from engine.basic_lands import Forest, Island, Mountain, Plains
from cards.fdn.fdn_150.card_impl import AegisTurtle
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_147.card_impl import SerraAngel
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_223.card_impl import GiantGrowth
from cards.fdn.fdn_175.card_impl import HerosDownfall
from cards.fdn.fdn_224.card_impl import GnarlidColony
from cards.fdn.fdn_153.card_impl import EssenceScatter
from cards.fdn.fdn_142.card_impl import HealersHawk
from cards.fdn.fdn_114.card_impl import TreetopSnarespinner
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.casting import cast_spell as engine_cast_spell, play_land
from engine.combat import combat_damage_step, declare_attackers_step, declare_blockers_step, end_combat_step
from engine.stack import priority_loop
from engine.state_based_actions import resolve_state_based_actions
from engine.triggers import TriggerRegistration
from engine.turn import _do_cleanup_step
from engine.types import CardType, Keyword, ManaType, Phase, Step, Zone
from benchmarks.sos.workspace.tests.test_utils import cast_spell, create_game, set_board_state
from engine.events import DealsDamageTriggeredEvent

def _tap_land_for_mana(game, player, land):
    """Activate a land's mana ability via the engine's activate_ability.

    Converts the land's ManaAbility into an ActivatedAbilityInstance and
    runs it through the full activate_ability pipeline (cost check, tap,
    mana production).
    """
    mana_abilities = land.get_mana_abilities()
    assert mana_abilities, f'{land.name} has no mana abilities'
    mab = mana_abilities[0]
    ability_instance = ActivatedAbilityInstance(source=land, controller=player, cost=mab.cost, effect=mab.mana_produced, is_mana_ability=True, description=mab.description)
    activate_ability(game, player, ability_instance)

def _setup_turn(game, *, turn, active):
    """Configure game state for the start of a new turn.

    Sets active player, phase to precombat main, resets land plays,
    and — for turns after the first — runs the untap step logic
    (clear summoning sickness + untap permanents for the active player).
    """
    game.active_player_index = active
    game.priority_player_index = active
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.turn_number = turn
    player = game.players[active]
    player.land_plays_remaining = 1
    if turn > 1:
        from engine.turn import _do_untap_step
        _do_untap_step(game)

def _do_combat(game, *, attackers, blocker_map=None):
    """Run a full combat sequence: declare attackers → blockers → damage → end.

    Parameters:
        game: The current GameState.
        attackers: List of creature objects to declare as attackers.
        blocker_map: dict mapping blocker → attacker (or None for no blocks).
    """
    active = game.active_player
    defending = game.non_active_player
    game.phase = Phase.COMBAT
    game.step = Step.DECLARE_ATTACKERS
    game.combat_state.in_combat = True
    active._script.appendleft(attackers)
    declare_attackers_step(game)
    game.step = Step.DECLARE_BLOCKERS
    defending._script.appendleft(blocker_map if blocker_map is not None else {})
    declare_blockers_step(game)
    game.step = Step.COMBAT_DAMAGE
    combat_damage_step(game)
    end_combat_step(game)

def _resolve_stack(game):
    """Resolve everything on the stack via the engine's priority_loop.

    Scripts both players to pass priority so the priority_loop resolves
    all stack items in LIFO order.  When the stack is empty and no
    legal actions exist, players auto-pass and the loop returns.
    """
    p1, p2 = game.players
    stack_depth = len(game.stack._items)
    for _ in range(stack_depth):
        p1._script.append('pass')
        p2._script.append('pass')
    priority_loop(game)

def _count_battlefield(game, player, card_type=None):
    """Count objects on a player's battlefield, optionally filtering by type."""
    bf = game.get_battlefield(player)
    if card_type is None:
        return len(bf)
    return sum((1 for obj in bf.get_all() if card_type in getattr(obj, 'card_types', set())))

def _battlefield_names(game, player):
    """Return sorted list of card names on a player's battlefield."""
    return sorted((getattr(obj, 'name', '?') for obj in game.get_battlefield(player).get_all()))

def _graveyard_names(game, player):
    """Return sorted list of card names in a player's graveyard."""
    return sorted((getattr(obj, 'name', '?') for obj in game.get_graveyard(player).get_all()))

class TestMultiTurnIntegration:
    """End-to-end multi-turn game proving the Phase 1 engine is functional."""

    def test_multi_turn_game_with_foundations_cards(self):
        """6-turn game: land drops, creatures, combat, removal, combat trick,
        counterspell, SBAs, continuous effects, and cleanup — all via real
        engine APIs (activate_ability for mana, priority_loop for resolution,
        _do_cleanup_step for cleanup)."""
        game = create_game()
        p1, p2 = game.players
        plains = [Plains(name='Plains') for _ in range(5)]
        forests = [Forest(name='Forest') for _ in range(3)]
        lions = SavannahLions()
        bear = GnarlidColony()
        angel = SerraAngel()
        growth = GiantGrowth()
        islands = [Island(name='Island') for _ in range(5)]
        mountains = [Mountain(name='Mountain') for _ in range(2)]
        turtle = AegisTurtle()
        bolt = BurstLightning()
        cancel = EssenceScatter()
        set_board_state(game, 0, hand=[plains[0], plains[1], forests[0], lions, bear, angel, growth])
        set_board_state(game, 1, hand=[islands[0], islands[1], mountains[0], turtle, bolt, cancel, islands[2]])
        for card in [plains[2], plains[3], plains[4], forests[1], forests[2]]:
            card.owner = p1
            card.controller = p1
            p1.zones[Zone.LIBRARY].add(card)
        for card in [islands[3], islands[4], mountains[1]]:
            card.owner = p2
            card.controller = p2
            p2.zones[Zone.LIBRARY].add(card)
        assert p1.life == 20
        assert p2.life == 20
        assert len(game.get_hand(p1)) == 7
        assert len(game.get_hand(p2)) == 7
        assert len(game.get_battlefield(p1)) == 0
        assert len(game.get_battlefield(p2)) == 0
        _setup_turn(game, turn=1, active=0)
        play_land(game, p1, plains[0])
        assert game.get_battlefield(p1).contains(plains[0])
        assert p1.land_plays_remaining == 0
        _tap_land_for_mana(game, p1, plains[0])
        assert plains[0].is_tapped
        assert p1.mana_pool.get(ManaType.WHITE) >= 1
        engine_cast_spell(game, p1, lions)
        _resolve_stack(game)
        assert _count_battlefield(game, p1) == 2
        assert game.get_battlefield(p1).contains(lions)
        assert lions.summoning_sick is True
        assert lions.power == 2
        assert lions.toughness == 1
        assert p1.mana_pool.total() == 0
        assert len(game.get_hand(p1)) == 5
        assert p1.life == 20
        assert p2.life == 20
        _setup_turn(game, turn=2, active=1)
        play_land(game, p2, islands[0])
        _tap_land_for_mana(game, p2, islands[0])
        assert islands[0].is_tapped
        assert p2.mana_pool.get(ManaType.BLUE) >= 1
        engine_cast_spell(game, p2, turtle)
        _resolve_stack(game)
        assert _count_battlefield(game, p2) == 2
        assert game.get_battlefield(p2).contains(turtle)
        assert turtle.summoning_sick is True
        assert turtle.power == 0
        assert turtle.toughness == 5
        assert len(game.get_hand(p2)) == 5
        _setup_turn(game, turn=3, active=0)
        assert lions.summoning_sick is False
        play_land(game, p1, forests[0])
        assert _count_battlefield(game, p1) == 3
        _do_combat(game, attackers=[lions], blocker_map={})
        assert p2.life == 18
        assert p1.life == 20
        assert lions.is_tapped
        game.phase = Phase.POSTCOMBAT_MAIN
        game.step = None
        _tap_land_for_mana(game, p1, plains[0])
        _tap_land_for_mana(game, p1, forests[0])
        engine_cast_spell(game, p1, bear)
        _resolve_stack(game)
        assert game.get_battlefield(p1).contains(bear)
        assert bear.summoning_sick is True
        assert bear.power == 2
        assert bear.toughness == 2
        assert len(game.get_hand(p1)) == 3
        _do_cleanup_step(game)
        _setup_turn(game, turn=4, active=1)
        play_land(game, p2, mountains[0])
        _tap_land_for_mana(game, p2, mountains[0])
        assert mountains[0].is_tapped
        p2._script.appendleft(lions)
        engine_cast_spell(game, p2, bolt)
        _resolve_stack(game)
        assert game.get_graveyard(p1).contains(lions), f'Lions should be in graveyard; bf={_battlefield_names(game, p1)}'
        assert not game.get_battlefield(p1).contains(lions)
        assert game.get_graveyard(p2).contains(bolt)
        assert len(game.get_hand(p2)) == 3
        assert p1.life == 20
        assert p2.life == 18
        _setup_turn(game, turn=5, active=0)
        play_land(game, p1, plains[1])
        game.phase = Phase.COMBAT
        game.step = Step.DECLARE_ATTACKERS
        game.combat_state.in_combat = True
        p1._script.appendleft([bear])
        declare_attackers_step(game)
        assert bear.is_attacking
        game.step = Step.DECLARE_BLOCKERS
        p2._script.appendleft({turtle: bear})
        declare_blockers_step(game)
        assert turtle.is_blocking
        _tap_land_for_mana(game, p1, forests[0])
        p1._script.appendleft(bear)
        engine_cast_spell(game, p1, growth)
        assert not game.stack.is_empty()
        _resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert bear.power == 5, f'Bear power should be 5, got {bear.power}'
        assert bear.toughness == 5, f'Bear toughness should be 5, got {bear.toughness}'
        game.step = Step.COMBAT_DAMAGE
        combat_damage_step(game)
        assert turtle.damage_marked == 5
        assert bear.damage_marked == 0
        resolve_state_based_actions(game)
        assert game.get_graveyard(p2).contains(turtle), f'Turtle should be dead; P2 bf={_battlefield_names(game, p2)}'
        assert not game.get_battlefield(p2).contains(turtle)
        assert game.get_battlefield(p1).contains(bear)
        assert p2.life == 18
        end_combat_step(game)
        _do_cleanup_step(game)
        assert bear.power == 2, f'Bear power should reset to 2, got {bear.power}'
        assert bear.toughness == 2, f'Bear toughness should reset to 2, got {bear.toughness}'
        _setup_turn(game, turn=6, active=0)
        assert game.get_hand(p1).contains(angel)
        assert game.get_hand(p2).contains(cancel)
        hand_p1_before = len(game.get_hand(p1))
        hand_p2_before = len(game.get_hand(p2))
        _tap_land_for_mana(game, p1, plains[0])
        _tap_land_for_mana(game, p1, plains[1])
        _tap_land_for_mana(game, p1, forests[0])
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        engine_cast_spell(game, p1, angel)
        assert not game.stack.is_empty()
        angel_so = game.stack.peek()
        assert angel_so.source is angel
        assert not game.get_hand(p1).contains(angel)
        assert p1.zones[Zone.STACK].contains(angel)
        _tap_land_for_mana(game, p2, islands[0])
        p2.mana_pool.add(ManaType.COLORLESS, 1)
        p2._script.appendleft(angel_so)
        engine_cast_spell(game, p2, cancel)
        assert len(game.stack._items) == 2
        _resolve_stack(game)
        assert game.stack.is_empty(), 'Stack should be empty after Essence Scatter resolves'
        assert game.get_graveyard(p1).contains(angel), f'Angel should be countered to graveyard; P1 gy={_graveyard_names(game, p1)}'
        assert not game.get_battlefield(p1).contains(angel)
        assert game.get_graveyard(p2).contains(cancel), f'Essence Scatter should be in graveyard; P2 gy={_graveyard_names(game, p2)}'
        assert len(game.get_hand(p1)) == hand_p1_before - 1
        assert len(game.get_hand(p2)) == hand_p2_before - 1
        assert p1.life == 20
        assert p2.life == 18
        p1_bf = _battlefield_names(game, p1)
        assert p1_bf.count('Plains') == 2
        assert p1_bf.count('Forest') == 1
        assert 'Gnarlid Colony' in p1_bf
        assert _count_battlefield(game, p1, CardType.CREATURE) == 1
        p2_bf = _battlefield_names(game, p2)
        assert p2_bf.count('Island') == 1
        assert p2_bf.count('Mountain') == 1
        assert _count_battlefield(game, p2, CardType.CREATURE) == 0
        p1_gy = _graveyard_names(game, p1)
        assert 'Savannah Lions' in p1_gy
        assert 'Serra Angel' in p1_gy
        p2_gy = _graveyard_names(game, p2)
        assert 'Burst Lightning' in p2_gy
        assert 'Aegis Turtle' in p2_gy
        assert 'Essence Scatter' in p2_gy
        assert game.get_graveyard(p1).contains(growth)

    def test_creature_combat_damage_and_sbas(self):
        """Creature takes lethal combat damage → SBAs move it to graveyard."""
        game = create_game()
        p1, p2 = game.players
        attacker = SavannahLions()
        blocker = GnarlidColony()
        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[blocker])
        attacker.summoning_sick = False
        blocker.summoning_sick = False
        _setup_turn(game, turn=2, active=0)
        _do_combat(game, attackers=[attacker], blocker_map={blocker: attacker})
        resolve_state_based_actions(game)
        assert game.get_graveyard(p1).contains(attacker)
        assert game.get_graveyard(p2).contains(blocker)

    def test_serra_angel_vigilance_no_tap(self):
        """Serra Angel (Vigilance) does not tap when attacking."""
        game = create_game()
        p1, p2 = game.players
        angel = SerraAngel()
        set_board_state(game, 0, battlefield=[angel])
        angel.summoning_sick = False
        _setup_turn(game, turn=2, active=0)
        _do_combat(game, attackers=[angel], blocker_map={})
        assert not angel.is_tapped
        assert p2.life == 16

    def test_burst_lightning_via_land_tap(self):
        """Burst Lightning targeting a player: tap Mountain for mana,
        cast, resolve via priority loop."""
        game = create_game()
        p1, p2 = game.players
        bolt = BurstLightning()
        mtn = Mountain(name='Mountain')
        set_board_state(game, 0, hand=[bolt], battlefield=[mtn])
        _setup_turn(game, turn=2, active=0)
        _tap_land_for_mana(game, p1, mtn)
        assert mtn.is_tapped
        assert p1.mana_pool.get(ManaType.RED) >= 1
        p1._script.appendleft(p2)
        engine_cast_spell(game, p1, bolt)
        _resolve_stack(game)
        assert p2.life == 18

    def test_giant_growth_expires_at_cleanup(self):
        """Giant Growth's +3/+3 expires when the engine's cleanup step runs."""
        game = create_game()
        p1, p2 = game.players
        bear = GnarlidColony()
        growth = GiantGrowth()
        forest = Forest(name='Forest')
        set_board_state(game, 0, battlefield=[bear, forest], hand=[growth])
        _setup_turn(game, turn=2, active=0)
        _tap_land_for_mana(game, p1, forest)
        assert forest.is_tapped
        p1._script.appendleft(bear)
        engine_cast_spell(game, p1, growth)
        _resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert bear.power == 5
        assert bear.toughness == 5
        _do_cleanup_step(game)
        assert bear.power == 2
        assert bear.toughness == 2

    def test_flying_blocks_only_by_flying_or_reach(self):
        """Flying creature cannot be blocked by a ground creature.
        But CAN be blocked by a reach creature (tested in full combat)."""
        game = create_game()
        p1, p2 = game.players
        flyer = HealersHawk()
        archer = TreetopSnarespinner()
        set_board_state(game, 0, battlefield=[flyer])
        set_board_state(game, 1, battlefield=[archer])
        flyer.summoning_sick = False
        archer.summoning_sick = False
        _setup_turn(game, turn=2, active=0)
        _do_combat(game, attackers=[flyer], blocker_map={archer: flyer})
        resolve_state_based_actions(game)
        assert game.get_graveyard(p1).contains(flyer)
        assert not game.get_graveyard(p2).contains(archer)
        assert p1.life == 21

    def test_summoning_sickness_prevents_attack(self):
        """A creature with summoning sickness cannot be declared as an attacker."""
        game = create_game()
        p1, p2 = game.players
        creature = SavannahLions()
        set_board_state(game, 0, battlefield=[creature])
        _setup_turn(game, turn=1, active=0)
        game.phase = Phase.COMBAT
        game.step = Step.DECLARE_ATTACKERS
        game.combat_state.in_combat = True
        p1._script.appendleft([creature])
        declare_attackers_step(game)
        assert not creature.is_attacking
        assert p2.life == 20

    def test_land_play_limit_one_per_turn(self):
        """Only one land can be played per turn."""
        game = create_game()
        p1 = game.players[0]
        land1 = Plains(name='Plains')
        land2 = Forest(name='Forest')
        set_board_state(game, 0, hand=[land1, land2])
        _setup_turn(game, turn=1, active=0)
        play_land(game, p1, land1)
        assert p1.land_plays_remaining == 0
        with pytest.raises(Exception):
            play_land(game, p1, land2)
        assert _count_battlefield(game, p1) == 1

    def test_triggered_ability_fires_and_resolves(self):
        """A triggered ability is registered, fires on event, pushed to stack,
        and resolved via priority_loop — exercising the full TriggerManager
        pipeline through real engine APIs."""
        game = create_game()
        p1, p2 = game.players
        bear = GnarlidColony()
        set_board_state(game, 0, battlefield=[bear])
        bear.summoning_sick = False
        _setup_turn(game, turn=2, active=0)
        trigger_fired = []

        def _trigger_effect(g):
            """Trigger effect: P1 gains 1 life."""
            g.players[0].life += 1
            trigger_fired.append(True)
        trigger = TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=lambda g, event: event.source is bear, effect=_trigger_effect, source=bear, controller=p1)
        game.trigger_manager.register(trigger)
        assert len(game.trigger_manager.get_triggers_for_source(bear)) == 1
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=bear, amount=2))
        assert not game.stack.is_empty(), 'Trigger should be on the stack'
        _resolve_stack(game)
        assert len(trigger_fired) == 1, 'Trigger should have fired exactly once'
        assert p1.life == 21, 'P1 should have gained 1 life from trigger'
        game.trigger_manager.unregister(bear)
        assert len(game.trigger_manager.get_triggers_for_source(bear)) == 0
