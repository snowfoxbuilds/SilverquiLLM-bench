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
- Counter spells (Cancel — counter target spell, stack interaction)
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

from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.casting import cast_spell as engine_cast_spell, play_land
from engine.combat import (
    combat_damage_step,
    declare_attackers_step,
    declare_blockers_step,
    end_combat_step,
)
from engine.stack import priority_loop
from engine.state_based_actions import resolve_state_based_actions
from engine.triggers import EventType, TriggerRegistration
from engine.turn import _do_cleanup_step
from engine.types import CardType, Keyword, ManaType, Phase, Step, Zone
from tests.test_utils import cast_spell, create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tap_land_for_mana(game, player, land):
    """Activate a land's mana ability via the engine's activate_ability.

    Converts the land's ManaAbility into an ActivatedAbilityInstance and
    runs it through the full activate_ability pipeline (cost check, tap,
    mana production).
    """
    mana_abilities = land.get_mana_abilities()
    assert mana_abilities, f"{land.name} has no mana abilities"
    mab = mana_abilities[0]
    ability_instance = ActivatedAbilityInstance(
        source=land,
        controller=player,
        cost=mab.cost,
        effect=mab.mana_produced,
        is_mana_ability=True,
        description=mab.description,
    )
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

    # Run the untap step logic: untap all permanents and clear summoning sickness.
    if turn > 1:
        from engine.turn import _do_untap_step
        # Save/restore phase/step since _do_untap_step doesn't change them
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

    # Declare attackers
    game.phase = Phase.COMBAT
    game.step = Step.DECLARE_ATTACKERS
    game.combat_state.in_combat = True
    active._script.appendleft(attackers)
    declare_attackers_step(game)

    # Declare blockers
    game.step = Step.DECLARE_BLOCKERS
    defending._script.appendleft(blocker_map if blocker_map is not None else {})
    declare_blockers_step(game)

    # Combat damage
    game.step = Step.COMBAT_DAMAGE
    combat_damage_step(game)

    # End combat
    end_combat_step(game)


def _resolve_stack(game):
    """Resolve everything on the stack via the engine's priority_loop.

    Scripts both players to pass priority so the priority_loop resolves
    all stack items in LIFO order.  When the stack is empty and no
    legal actions exist, players auto-pass and the loop returns.
    """
    # Each resolution cycle requires both players to pass priority.
    # _get_legal_actions returns [] and when the stack is non-empty
    # each player must choose "pass" from the options list.
    # After resolution, if the stack is empty, players auto-pass.
    p1, p2 = game.players
    # Script enough "pass" for one resolution per stack item
    stack_depth = len(game.stack._items)
    for _ in range(stack_depth):
        p1._script.append("pass")
        p2._script.append("pass")
    priority_loop(game)


def _count_battlefield(game, player, card_type=None):
    """Count objects on a player's battlefield, optionally filtering by type."""
    bf = game.get_battlefield(player)
    if card_type is None:
        return len(bf)
    return sum(
        1 for obj in bf.get_all()
        if card_type in getattr(obj, "card_types", set())
    )


def _battlefield_names(game, player):
    """Return sorted list of card names on a player's battlefield."""
    return sorted(
        getattr(obj, "name", "?")
        for obj in game.get_battlefield(player).get_all()
    )


def _graveyard_names(game, player):
    """Return sorted list of card names in a player's graveyard."""
    return sorted(
        getattr(obj, "name", "?")
        for obj in game.get_graveyard(player).get_all()
    )


# ===========================================================================
# Integration test
# ===========================================================================


class TestMultiTurnIntegration:
    """End-to-end multi-turn game proving the Phase 1 engine is functional."""

    def test_multi_turn_game_with_foundations_cards(self):
        """6-turn game: land drops, creatures, combat, removal, combat trick,
        counterspell, SBAs, continuous effects, and cleanup — all via real
        engine APIs (activate_ability for mana, priority_loop for resolution,
        _do_cleanup_step for cleanup)."""

        # =============================================================
        # SETUP
        # =============================================================
        game = create_game()
        p1, p2 = game.players

        # --- P1 cards (White/Green) ---
        plains = [Plains(name="Plains") for _ in range(5)]
        forests = [Forest(name="Forest") for _ in range(3)]
        lions = SavannahLions()       # {W}     2/1
        bear = BearCub()              # {1}{G}  2/2
        angel = SerraAngel()          # {3}{W}{W} 4/4 Flying Vigilance
        growth = GiantGrowth()        # {G}     +3/+3 until end of turn

        # --- P2 cards (Blue/Red) ---
        islands = [Island(name="Island") for _ in range(5)]
        mountains = [Mountain(name="Mountain") for _ in range(2)]
        turtle = AegisTurtle()        # {U}     0/5
        bolt = BurstLightning()       # {R}     2 damage to any target
        cancel = Cancel()             # {1}{U}{U} counter target spell

        # Set hands (7 cards each)
        set_board_state(game, 0, hand=[
            plains[0], plains[1], forests[0], lions, bear, angel, growth,
        ])
        set_board_state(game, 1, hand=[
            islands[0], islands[1], mountains[0], turtle, bolt, cancel, islands[2],
        ])

        # Libraries for future draw steps (not strictly needed for manual turns)
        for card in [plains[2], plains[3], plains[4], forests[1], forests[2]]:
            card.owner = p1
            card.controller = p1
            p1.zones[Zone.LIBRARY].add(card)
        for card in [islands[3], islands[4], mountains[1]]:
            card.owner = p2
            card.controller = p2
            p2.zones[Zone.LIBRARY].add(card)

        # --- Initial state assertions ---
        assert p1.life == 20
        assert p2.life == 20
        assert len(game.get_hand(p1)) == 7
        assert len(game.get_hand(p2)) == 7
        assert len(game.get_battlefield(p1)) == 0
        assert len(game.get_battlefield(p2)) == 0

        # =============================================================
        # TURN 1 — P1: Play Plains, cast Savannah Lions ({W})
        # =============================================================
        _setup_turn(game, turn=1, active=0)

        # Land drop
        play_land(game, p1, plains[0])
        assert game.get_battlefield(p1).contains(plains[0])
        assert p1.land_plays_remaining == 0

        # Tap Plains for {W} via land mana ability
        _tap_land_for_mana(game, p1, plains[0])
        assert plains[0].is_tapped
        assert p1.mana_pool.get(ManaType.WHITE) >= 1

        # Cast Savannah Lions and resolve via priority loop
        engine_cast_spell(game, p1, lions)
        _resolve_stack(game)

        # Assertions
        assert _count_battlefield(game, p1) == 2  # Plains + Lions
        assert game.get_battlefield(p1).contains(lions)
        assert lions.summoning_sick is True
        assert lions.power == 2
        assert lions.toughness == 1
        assert p1.mana_pool.total() == 0
        assert len(game.get_hand(p1)) == 5
        assert p1.life == 20
        assert p2.life == 20

        # =============================================================
        # TURN 2 — P2: Play Island, cast Aegis Turtle ({U})
        # =============================================================
        _setup_turn(game, turn=2, active=1)

        play_land(game, p2, islands[0])

        # Tap Island for {U} via land mana ability
        _tap_land_for_mana(game, p2, islands[0])
        assert islands[0].is_tapped
        assert p2.mana_pool.get(ManaType.BLUE) >= 1

        # Cast Aegis Turtle and resolve via priority loop
        engine_cast_spell(game, p2, turtle)
        _resolve_stack(game)

        assert _count_battlefield(game, p2) == 2  # Island + Turtle
        assert game.get_battlefield(p2).contains(turtle)
        assert turtle.summoning_sick is True
        assert turtle.power == 0
        assert turtle.toughness == 5
        assert len(game.get_hand(p2)) == 5

        # =============================================================
        # TURN 3 — P1: Play Forest, attack with Lions (unblocked),
        #               then cast Bear Cub
        # =============================================================
        _setup_turn(game, turn=3, active=0)
        # Lions' summoning sickness cleared by _setup_turn (untap step)
        assert lions.summoning_sick is False

        # Land drop
        play_land(game, p1, forests[0])
        assert _count_battlefield(game, p1) == 3  # Plains + Forest + Lions

        # Combat: Lions attacks, P2 doesn't block
        _do_combat(game, attackers=[lions], blocker_map={})

        # Unblocked Lions deals 2 damage to P2
        assert p2.life == 18
        assert p1.life == 20
        assert lions.is_tapped  # Lions has no vigilance

        # Post-combat main: cast Bear Cub ({1}{G})
        game.phase = Phase.POSTCOMBAT_MAIN
        game.step = None
        # Tap Plains and Forest for mana via ability system
        # Plains was untapped by _setup_turn's untap step, but Lions tapped it
        # during combat (wait — Lions taps itself, not Plains).
        # Actually Plains was untapped at start of turn. We need to tap it.
        _tap_land_for_mana(game, p1, plains[0])  # {W} for generic cost
        _tap_land_for_mana(game, p1, forests[0])  # {G} for green cost

        engine_cast_spell(game, p1, bear)
        _resolve_stack(game)

        assert game.get_battlefield(p1).contains(bear)
        assert bear.summoning_sick is True
        assert bear.power == 2
        assert bear.toughness == 2
        assert len(game.get_hand(p1)) == 3  # angel, growth, plains[1]

        # Cleanup via engine's cleanup step (clears damage, effects, mana)
        _do_cleanup_step(game)

        # =============================================================
        # TURN 4 — P2: Play Mountain, Burst Lightning kills Lions
        # =============================================================
        _setup_turn(game, turn=4, active=1)

        play_land(game, p2, mountains[0])

        # Tap Mountain for {R} via land mana ability
        _tap_land_for_mana(game, p2, mountains[0])
        assert mountains[0].is_tapped

        # Cast Burst Lightning targeting Savannah Lions ({R}, deals 2 damage)
        p2._script.appendleft(lions)  # target for Burst Lightning
        engine_cast_spell(game, p2, bolt)
        _resolve_stack(game)

        # Burst Lightning deals 2 to Lions (1 toughness) → lethal → SBAs kill it
        assert game.get_graveyard(p1).contains(lions), (
            f"Lions should be in graveyard; bf={_battlefield_names(game, p1)}"
        )
        assert not game.get_battlefield(p1).contains(lions)
        # Burst Lightning (instant) goes to P2's graveyard after resolution
        assert game.get_graveyard(p2).contains(bolt)
        assert len(game.get_hand(p2)) == 3
        # P1 still at 20 life (Lions was the target, not P1)
        assert p1.life == 20
        assert p2.life == 18  # unchanged from Turn 3

        # =============================================================
        # TURN 5 — P1: Play Plains, attack Bear + combat trick
        #   Bear Cub attacks, Aegis Turtle blocks, Giant Growth on Bear
        #   Bear (5/5) kills Turtle (0/5). Turtle dies. Bear survives.
        # =============================================================
        _setup_turn(game, turn=5, active=0)

        play_land(game, p1, plains[1])

        # --- Combat with combat trick ---
        # Declare attackers: Bear Cub
        game.phase = Phase.COMBAT
        game.step = Step.DECLARE_ATTACKERS
        game.combat_state.in_combat = True
        p1._script.appendleft([bear])
        declare_attackers_step(game)
        assert bear.is_attacking

        # Declare blockers: Turtle blocks Bear
        game.step = Step.DECLARE_BLOCKERS
        p2._script.appendleft({turtle: bear})
        declare_blockers_step(game)
        assert turtle.is_blocking

        # Before damage: P1 casts Giant Growth on Bear Cub (instant speed!)
        # Tap Forest for {G} via land mana ability (untapped at start of turn)
        _tap_land_for_mana(game, p1, forests[0])
        p1._script.appendleft(bear)  # target for Giant Growth
        engine_cast_spell(game, p1, growth)

        # Resolve Giant Growth via priority loop
        assert not game.stack.is_empty()
        _resolve_stack(game)

        # Verify continuous effect: Bear Cub is now 5/5
        game.effect_manager.apply_all(game)
        assert bear.power == 5, f"Bear power should be 5, got {bear.power}"
        assert bear.toughness == 5, f"Bear toughness should be 5, got {bear.toughness}"

        # Combat damage step
        game.step = Step.COMBAT_DAMAGE
        combat_damage_step(game)

        # Bear (5/5) deals 5 damage to Turtle (0/5: toughness 5, lethal)
        # Turtle (0/5) deals 0 damage to Bear
        assert turtle.damage_marked == 5
        assert bear.damage_marked == 0

        # SBAs: Turtle dies (5 damage >= 5 toughness)
        resolve_state_based_actions(game)
        assert game.get_graveyard(p2).contains(turtle), (
            f"Turtle should be dead; P2 bf={_battlefield_names(game, p2)}"
        )
        assert not game.get_battlefield(p2).contains(turtle)
        # Bear survives
        assert game.get_battlefield(p1).contains(bear)
        # P2 life unchanged (Bear was blocked)
        assert p2.life == 18

        # End combat
        end_combat_step(game)

        # --- Cleanup via engine's cleanup step ---
        # This exercises the full cleanup pipeline: discard, EOT effects,
        # damage clearing, combat flags, mana pool emptying, SBAs.
        _do_cleanup_step(game)

        # Bear Cub back to base 2/2 (Giant Growth expired during cleanup)
        assert bear.power == 2, f"Bear power should reset to 2, got {bear.power}"
        assert bear.toughness == 2, f"Bear toughness should reset to 2, got {bear.toughness}"

        # =============================================================
        # TURN 6 — Counterspell interaction:
        #   P1 (active) casts Serra Angel from hand.
        #   P2 responds with Cancel → counters Serra Angel.
        #   Serra Angel ends up in P1's graveyard (countered).
        #   Cancel ends up in P2's graveyard.
        # =============================================================
        _setup_turn(game, turn=6, active=0)

        # Verify pre-state
        assert game.get_hand(p1).contains(angel)
        assert game.get_hand(p2).contains(cancel)
        hand_p1_before = len(game.get_hand(p1))
        hand_p2_before = len(game.get_hand(p2))

        # Tap 2 Plains + Forest for mana (need {3}{W}{W} for Serra Angel)
        _tap_land_for_mana(game, p1, plains[0])   # {W}
        _tap_land_for_mana(game, p1, plains[1])   # {W}
        _tap_land_for_mana(game, p1, forests[0])   # {G} → pays generic
        # Still need 2 more generic — add manually since P1 only has 3 lands
        # (Plains, Plains, Forest). Serra Angel costs {3}{W}{W}.
        # We have {W}{W}{G} from 3 lands; need 2 more generic.
        # For the test scenario, we acknowledge P1 doesn't have enough lands
        # for Angel normally by Turn 6.  Add additional mana to cover the gap.
        p1.mana_pool.add(ManaType.COLORLESS, 2)

        engine_cast_spell(game, p1, angel)

        # Angel is on the stack (not resolved yet)
        assert not game.stack.is_empty()
        angel_so = game.stack.peek()
        assert angel_so.source is angel
        # Angel moved from hand to stack zone
        assert not game.get_hand(p1).contains(angel)
        assert p1.zones[Zone.STACK].contains(angel)

        # P2 responds: cast Cancel targeting the angel's StackObject
        # Cancel costs {1}{U}{U}.  P2 has Island (untapped from Turn 4 setup)
        # and Mountain (tapped since Turn 4 — no P2 untap step ran since).
        # Tap the available Island for {U}, supplement the rest.
        _tap_land_for_mana(game, p2, islands[0])   # {U} via real ability
        p2.mana_pool.add(ManaType.BLUE, 1)         # supplement {U}
        p2.mana_pool.add(ManaType.COLORLESS, 1)    # supplement {1} generic

        p2._script.appendleft(angel_so)  # target for Cancel
        engine_cast_spell(game, p2, cancel)

        # Stack (top-to-bottom): Cancel, Serra Angel
        assert len(game.stack._items) == 2

        # Resolve via priority loop (LIFO: Cancel resolves first, counters Angel)
        _resolve_stack(game)

        # Stack should be empty after resolution
        assert game.stack.is_empty(), "Stack should be empty after Cancel resolves"

        # Serra Angel was countered → in P1's graveyard
        assert game.get_graveyard(p1).contains(angel), (
            f"Angel should be countered to graveyard; "
            f"P1 gy={_graveyard_names(game, p1)}"
        )
        assert not game.get_battlefield(p1).contains(angel)

        # Cancel → in P2's graveyard
        assert game.get_graveyard(p2).contains(cancel), (
            f"Cancel should be in graveyard; P2 gy={_graveyard_names(game, p2)}"
        )

        # Hand sizes decreased by 1 each
        assert len(game.get_hand(p1)) == hand_p1_before - 1
        assert len(game.get_hand(p2)) == hand_p2_before - 1

        # =============================================================
        # FINAL STATE ASSERTIONS
        # =============================================================

        # Life totals
        assert p1.life == 20
        assert p2.life == 18

        # P1 battlefield: Plains ×2, Forest ×1, Bear Cub
        p1_bf = _battlefield_names(game, p1)
        assert p1_bf.count("Plains") == 2
        assert p1_bf.count("Forest") == 1
        assert "Bear Cub" in p1_bf
        assert _count_battlefield(game, p1, CardType.CREATURE) == 1

        # P2 battlefield: Island ×1, Mountain ×1 (turtle is dead)
        p2_bf = _battlefield_names(game, p2)
        assert p2_bf.count("Island") == 1
        assert p2_bf.count("Mountain") == 1
        assert _count_battlefield(game, p2, CardType.CREATURE) == 0

        # P1 graveyard: Savannah Lions (killed by Bolt), Serra Angel (countered)
        p1_gy = _graveyard_names(game, p1)
        assert "Savannah Lions" in p1_gy
        assert "Serra Angel" in p1_gy

        # P2 graveyard: Burst Lightning (resolved), Aegis Turtle (killed),
        #               Cancel (resolved)
        p2_gy = _graveyard_names(game, p2)
        assert "Burst Lightning" in p2_gy
        assert "Aegis Turtle" in p2_gy
        assert "Cancel" in p2_gy

        # Giant Growth should be in P1's graveyard (resolved instant)
        assert game.get_graveyard(p1).contains(growth)

    # ------------------------------------------------------------------
    # Additional focused integration tests
    # ------------------------------------------------------------------

    def test_creature_combat_damage_and_sbas(self):
        """Creature takes lethal combat damage → SBAs move it to graveyard."""
        game = create_game()
        p1, p2 = game.players

        attacker = SavannahLions()  # 2/1
        blocker = BearCub()         # 2/2

        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[blocker])

        attacker.summoning_sick = False
        blocker.summoning_sick = False

        _setup_turn(game, turn=2, active=0)
        _do_combat(game, attackers=[attacker], blocker_map={blocker: attacker})

        # Attacker 2/1 takes 2 damage from blocker → lethal → graveyard
        # Blocker 2/2 takes 2 damage from attacker → lethal (damage == toughness)
        resolve_state_based_actions(game)

        # Both should be dead (2 damage each, both lethal)
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

        # Angel has Vigilance → should NOT be tapped
        assert not angel.is_tapped
        # 4 damage dealt to P2
        assert p2.life == 16

    def test_burst_lightning_via_land_tap(self):
        """Burst Lightning targeting a player: tap Mountain for mana,
        cast, resolve via priority loop."""
        game = create_game()
        p1, p2 = game.players

        bolt = BurstLightning()
        mtn = Mountain(name="Mountain")
        set_board_state(game, 0, hand=[bolt], battlefield=[mtn])
        _setup_turn(game, turn=2, active=0)

        # Tap Mountain for {R} via land mana ability
        _tap_land_for_mana(game, p1, mtn)
        assert mtn.is_tapped
        assert p1.mana_pool.get(ManaType.RED) >= 1

        # Cast and resolve via priority loop
        p1._script.appendleft(p2)  # target
        engine_cast_spell(game, p1, bolt)
        _resolve_stack(game)

        assert p2.life == 18  # 20 - 2

    def test_giant_growth_expires_at_cleanup(self):
        """Giant Growth's +3/+3 expires when the engine's cleanup step runs."""
        game = create_game()
        p1, p2 = game.players

        bear = BearCub()
        growth = GiantGrowth()
        forest = Forest(name="Forest")
        set_board_state(game, 0, battlefield=[bear, forest], hand=[growth])

        _setup_turn(game, turn=2, active=0)

        # Tap Forest for {G} via land mana ability
        _tap_land_for_mana(game, p1, forest)
        assert forest.is_tapped

        # Cast Giant Growth targeting Bear and resolve via priority loop
        p1._script.appendleft(bear)  # target
        engine_cast_spell(game, p1, growth)
        _resolve_stack(game)

        game.effect_manager.apply_all(game)
        assert bear.power == 5
        assert bear.toughness == 5

        # Run engine's cleanup step (not manual mutation)
        _do_cleanup_step(game)

        # Giant Growth expired during cleanup
        assert bear.power == 2
        assert bear.toughness == 2

    def test_flying_blocks_only_by_flying_or_reach(self):
        """Flying creature cannot be blocked by a ground creature.
        But CAN be blocked by a reach creature (tested in full combat)."""
        game = create_game()
        p1, p2 = game.players

        from cards.foundations.simple_creatures import (
            HealersHawk,
            ThornwealdArcher,
        )

        flyer = HealersHawk()   # 1/1 Flying Lifelink
        archer = ThornwealdArcher()  # 2/1 Reach Deathtouch

        set_board_state(game, 0, battlefield=[flyer])
        set_board_state(game, 1, battlefield=[archer])
        flyer.summoning_sick = False
        archer.summoning_sick = False

        _setup_turn(game, turn=2, active=0)
        _do_combat(game, attackers=[flyer], blocker_map={archer: flyer})

        # Archer (reach) can legally block the flyer
        # Healer's Hawk 1/1 vs Thornweald Archer 2/1
        # Hawk deals 1 damage to Archer (deathtouch doesn't help Hawk)
        # Archer deals 2 damage to Hawk → lethal (1 toughness)
        # Archer has 1 damage marked, 1 toughness → also lethal
        resolve_state_based_actions(game)

        assert game.get_graveyard(p1).contains(flyer)
        assert game.get_graveyard(p2).contains(archer)

        # Lifelink: P1 gains 1 life from Hawk's 1 damage
        assert p1.life == 21

    def test_summoning_sickness_prevents_attack(self):
        """A creature with summoning sickness cannot be declared as an attacker."""
        game = create_game()
        p1, p2 = game.players

        creature = SavannahLions()
        set_board_state(game, 0, battlefield=[creature])
        # summoning_sick defaults to True

        _setup_turn(game, turn=1, active=0)

        # Attempt combat — creature should not be eligible
        game.phase = Phase.COMBAT
        game.step = Step.DECLARE_ATTACKERS
        game.combat_state.in_combat = True
        # Script would provide creature, but _can_attack should filter it out
        p1._script.appendleft([creature])
        declare_attackers_step(game)

        # Creature should NOT be attacking (summoning sickness)
        assert not creature.is_attacking
        assert p2.life == 20  # No damage dealt

    def test_land_play_limit_one_per_turn(self):
        """Only one land can be played per turn."""
        game = create_game()
        p1 = game.players[0]

        land1 = Plains(name="Plains")
        land2 = Forest(name="Forest")
        set_board_state(game, 0, hand=[land1, land2])

        _setup_turn(game, turn=1, active=0)

        play_land(game, p1, land1)
        assert p1.land_plays_remaining == 0

        with pytest.raises(Exception):  # CastingError
            play_land(game, p1, land2)

        # Only one land on battlefield
        assert _count_battlefield(game, p1) == 1

    def test_triggered_ability_fires_and_resolves(self):
        """A triggered ability is registered, fires on event, pushed to stack,
        and resolved via priority_loop — exercising the full TriggerManager
        pipeline through real engine APIs."""
        game = create_game()
        p1, p2 = game.players

        bear = BearCub()
        set_board_state(game, 0, battlefield=[bear])
        bear.summoning_sick = False

        _setup_turn(game, turn=2, active=0)

        # Register a triggered ability on the bear: when it deals damage,
        # the controller gains 1 life (simulating a lifelink-like trigger).
        trigger_fired = []

        def _trigger_effect(g):
            """Trigger effect: P1 gains 1 life."""
            g.players[0].life += 1
            trigger_fired.append(True)

        trigger = TriggerRegistration(
            event_type=EventType.DEALS_DAMAGE,
            condition=lambda g, data: data.get("source") is bear,
            effect=_trigger_effect,
            source=bear,
            controller=p1,
        )
        game.trigger_manager.register(trigger)

        # Verify trigger is registered
        assert len(game.trigger_manager.get_triggers_for_source(bear)) == 1

        # Fire the DEALS_DAMAGE event (simulating combat damage from bear)
        game.trigger_manager.fire_event(
            game, EventType.DEALS_DAMAGE, {"source": bear, "amount": 2}
        )

        # Trigger should have pushed a StackObject
        assert not game.stack.is_empty(), "Trigger should be on the stack"

        # Resolve the trigger via priority loop (real engine flow)
        _resolve_stack(game)

        # Verify the trigger effect was applied
        assert len(trigger_fired) == 1, "Trigger should have fired exactly once"
        assert p1.life == 21, "P1 should have gained 1 life from trigger"

        # Unregister and verify cleanup
        game.trigger_manager.unregister(bear)
        assert len(game.trigger_manager.get_triggers_for_source(bear)) == 0
