"""Tests for the cleanup step (rule 514) and what it leaves for the next turn.

Each test plays into the cleanup step and judges it by what follows:
- the active player discards to maximum hand size (7); no one else does;
- "until end of turn" effects end, and other effects stay;
- damage marked on creatures is removed, so it no longer counts next turn;
- creatures stop attacking and blocking, and deathtouch damage is forgotten;
- mana left in a pool is gone.

Positions no card can reach through play — a permanent toughness reduction
that kills once an end-of-turn boost ends, a trigger during cleanup, damage
marked on a noncreature permanent — are still set up directly; see the tests
that call ``_do_cleanup_step``.
"""

from __future__ import annotations

from cards.fdn.fdn_10.card_impl import DivineResilience
from cards.fdn.fdn_60.card_impl import GutlessPlunderer
from cards.fdn.fdn_71.card_impl import Stab
from cards.fdn.fdn_72.card_impl import TinybonesBaubleBurglar, TinybonesBaubleBurglarAbility1
from cards.fdn.fdn_116.card_impl import AnthemOfChampions
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_150.card_impl import AegisTurtle
from cards.fdn.fdn_155.card_impl import FleetingDistraction
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_223.card_impl import GiantGrowth
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.fdn_280.card_impl import Forest
from cards.fdn.spg_74.card_impl import Condemn
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, player
from test_utils import DeterministicPlayer

from engine.card import CardImpl, Creature
from engine.game_state import GameState
from engine.turn import MAX_HAND_SIZE
from silverquillm.table import Table, cleanup_trigger, life, moves, off_stack, taps

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _discard_game(hand_size: int, *, other_hand: int = 0):
    """Player 0's end step, with ``hand_size`` cards in player 0's hand and
    ``other_hand`` in player 1's."""
    hand = [card(Plains) for _ in range(hand_size)]
    other = [card(Plains) for _ in range(other_hand)]
    game = create_game(Side(hand=hand), Side(hand=other), start=(Step.END, 0))
    return game, hand, other


def _end_turn(t: Table, discards=()) -> None:
    """Both players pass player 0's end step on an empty stack; in cleanup
    player 0 discards ``discards``, and player 1's upkeep follows."""
    t.pass_(0, choices=list(discards))
    t.pass_(
        1,
        then=[moves(c, Zone.GRAVEYARD) for c in discards],
        note=f"player 0 discards {len(discards)} in cleanup" if discards else "nobody discards in cleanup",
    )


def _cast(t: Table, seat: int, land, spell, *targets) -> None:
    """``seat`` taps ``land`` and casts ``spell`` at ``targets``."""
    t.act(seat, land, then=[taps(land)])
    t.act(seat, spell, choices=list(targets), then=[moves(spell, Zone.STACK)])


def _attack_unblocked(t: Table, attackers, damage_to: int, life_after: int) -> None:
    """Player 0, at its declaration of attackers, attacks with ``attackers``,
    nothing blocks, and player ``damage_to``'s life becomes ``life_after``."""
    t.act(0, *attackers, then=[taps(a) for a in attackers])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)  # declares no blockers
    t.pass_(0)
    t.pass_(1, then=[life(damage_to, life_after)])


def _make_card(name: str = "TestCard") -> CardImpl:
    """Create a minimal card for testing."""
    return CardImpl(name=name)


def _make_creature(name: str = "Bear", base_power: int = 2, base_toughness: int = 2) -> Creature:
    """Create a creature for testing."""
    return Creature(name=name, base_power=base_power, base_toughness=base_toughness)


def _make_game() -> tuple[GameState, DeterministicPlayer, DeterministicPlayer]:
    """Create a bare game state for the cleanup tests no play can reach."""
    p1 = DeterministicPlayer("Alice", life=20)
    p2 = DeterministicPlayer("Bob", life=20)
    game = GameState([p1, p2])
    return game, p1, p2


def _place_on_battlefield(game: GameState, player: DeterministicPlayer, obj) -> None:
    """Place an object on a player's battlefield, setting ownership."""
    obj.owner = player
    obj.controller = player
    player.zones[Zone.BATTLEFIELD].add(obj)


# ===========================================================================
# Discard to hand size
# ===========================================================================


class TestDiscardToHandSize:
    """Tests for cleanup step 1: discard down to max hand size."""

    def test_discard_from_8_to_7(self) -> None:
        """Player with 8 cards in hand discards 1 to reach 7."""
        game, hand, _ = _discard_game(8)
        t = Table(game)
        _end_turn(t, discards=hand[:1])
        final = t.run()
        assert len(final.players[0].hand) == 7

    def test_discard_from_10_to_7(self) -> None:
        """Player with 10 cards in hand discards 3 to reach 7."""
        game, hand, _ = _discard_game(10)
        t = Table(game)
        _end_turn(t, discards=hand[:3])
        final = t.run()
        assert len(final.players[0].hand) == 7

    def test_discarded_cards_go_to_graveyard(self) -> None:
        """Discarded cards during cleanup go to the player's graveyard."""
        game, hand, _ = _discard_game(8)
        t = Table(game)
        _end_turn(t, discards=hand[:1])
        final = t.run()
        assert final.where(hand[0]) is Zone.GRAVEYARD

    def test_exactly_7_cards_no_discard(self) -> None:
        """Player with exactly 7 cards does NOT discard: no discard question
        comes, which the pass's empty choices could not answer."""
        game, _, _ = _discard_game(7)
        t = Table(game)
        _end_turn(t)
        final = t.run()
        assert len(final.players[0].hand) == 7

    def test_fewer_than_7_cards_no_discard(self) -> None:
        """Player with fewer than 7 cards does NOT discard."""
        game, _, _ = _discard_game(3)
        t = Table(game)
        _end_turn(t)
        final = t.run()
        assert len(final.players[0].hand) == 3

    def test_only_active_player_discards(self) -> None:
        """Only the active player discards during cleanup, not the non-active
        player holding 9 cards."""
        game, _, _ = _discard_game(0, other_hand=9)
        t = Table(game)
        _end_turn(t)
        final = t.run()
        assert len(final.players[1].hand) == 9

    def test_chosen_card_is_the_one_discarded(self) -> None:
        """The card the player chooses is the one discarded."""
        game, hand, _ = _discard_game(8)
        t = Table(game)
        _end_turn(t, discards=hand[7:])
        final = t.run()
        assert final.where(hand[7]) is Zone.GRAVEYARD
        assert all(final.where(c) is Zone.HAND for c in hand[:7])


# ===========================================================================
# EOT effect removal
# ===========================================================================


class TestEOTEffectRemoval:
    """Tests for cleanup step 2: remove 'until end of turn' effects."""

    def test_eot_effect_removed(self) -> None:
        """Giant Growth's +3/+3 ends in cleanup: next turn 2 damage kills the
        2/1 it pumped."""
        lions, forest, growth = card(SavannahLions), card(Forest), card(GiantGrowth)
        mountain, bolt = card(Mountain), card(BurstLightning)
        game = create_game(
            Side(battlefield=[lions, forest], hand=[growth]),
            Side(battlefield=[mountain], hand=[bolt]),
            start=(Step.END, 0),
        )
        t = Table(game)
        _cast(t, 0, forest, growth, lions)
        t.pass_(0)
        t.pass_(1, then=[moves(growth, Zone.GRAVEYARD)], note="the Lions is 5/4 until end of turn")
        t.pass_to(Step.UPKEEP, 1)
        _cast(t, 1, mountain, bolt, lions)
        t.pass_(1)
        t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)], note="2 damage kills a 2/1")
        t.run()

    def test_permanent_effect_not_removed(self) -> None:
        """Anthem of Champions' +1/+1 survives cleanup: the 2/1 attacks for 3
        next turn."""
        lions = card(SavannahLions)
        game = create_game(
            Side(battlefield=[lions, AnthemOfChampions], library=[Plains]),
            Side(),
            start=(Step.END, 1),
        )
        t = Table(game)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        _attack_unblocked(t, [lions], damage_to=1, life_after=17)
        t.run()

    def test_multiple_eot_effects_all_removed(self) -> None:
        """Two Giant Growths both end in one cleanup: next turn their 2/1 and
        1/1 attack for 3, not 9."""
        lions, elves = card(SavannahLions), card(LlanowarElves)
        forest_a, forest_b = card(Forest), card(Forest)
        growth_a, growth_b = card(GiantGrowth), card(GiantGrowth)
        game = create_game(
            Side(battlefield=[lions, elves, forest_a, forest_b], hand=[growth_a, growth_b], library=[Plains]),
            Side(),
            start=(Step.END, 1),
        )
        t = Table(game)
        t.pass_(1)
        _cast(t, 0, forest_a, growth_a, lions)
        _cast(t, 0, forest_b, growth_b, elves)
        t.pass_(0)
        t.pass_(1, then=[moves(growth_b, Zone.GRAVEYARD)])
        t.pass_(1)
        t.pass_(0, then=[moves(growth_a, Zone.GRAVEYARD)], note="both are pumped until end of turn")
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        _attack_unblocked(t, [lions, elves], damage_to=1, life_after=17)
        t.run()

    def test_effects_reapplied_after_removal(self) -> None:
        """With Anthem of Champions (+1/+1) and Giant Growth (+3/+3 until end
        of turn) on a 2/1, only the anthem remains next turn: it attacks for 3."""
        lions, forest, growth = card(SavannahLions), card(Forest), card(GiantGrowth)
        game = create_game(
            Side(battlefield=[lions, forest, AnthemOfChampions], hand=[growth], library=[Plains]),
            Side(),
            start=(Step.END, 1),
        )
        t = Table(game)
        t.pass_(1)
        _cast(t, 0, forest, growth, lions)
        t.pass_(0)
        t.pass_(1, then=[moves(growth, Zone.GRAVEYARD)], note="the Lions is 6/5 until end of turn")
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        _attack_unblocked(t, [lions], damage_to=1, life_after=17)
        t.run()


# ===========================================================================
# Damage clearing
# ===========================================================================


class TestDamageClearing:
    """Tests for cleanup step 3: clear damage marked on creatures."""

    def test_damage_cleared_to_zero(self) -> None:
        """A 3/3 dealt 2 damage survives 2 more next turn: cleanup removed all
        of it."""
        scourge, mountain = card(BrazenScourge), card(Mountain)
        bolt_a, bolt_b = card(BurstLightning), card(BurstLightning)
        game = create_game(
            Side(battlefield=[scourge]),
            Side(battlefield=[mountain], hand=[bolt_a, bolt_b]),
            start=(Step.END, 0),
        )
        t = Table(game)
        t.pass_(0)
        _cast(t, 1, mountain, bolt_a, scourge)
        t.pass_(1)
        t.pass_(0, then=[moves(bolt_a, Zone.GRAVEYARD)], note="the Scourge has 2 damage")
        t.pass_to(Step.UPKEEP, 1)
        _cast(t, 1, mountain, bolt_b, scourge)
        t.pass_(1)
        t.pass_(0, then=[moves(bolt_b, Zone.GRAVEYARD)], note="the Scourge survives 2 more")
        t.run()

    def test_damage_cleared_on_all_players_creatures(self) -> None:
        """Damage is removed from every player's creatures, not just the
        active player's: both 3/3s survive a second 2 damage next turn."""
        mine, theirs = card(BrazenScourge), card(BrazenScourge)
        my_mountain_a, my_mountain_b, their_mountain = card(Mountain), card(Mountain), card(Mountain)
        my_bolt_a, my_bolt_b = card(BurstLightning), card(BurstLightning)
        their_bolt_a, their_bolt_b = card(BurstLightning), card(BurstLightning)
        game = create_game(
            Side(battlefield=[mine, my_mountain_a, my_mountain_b], hand=[my_bolt_a, my_bolt_b]),
            Side(battlefield=[theirs, their_mountain], hand=[their_bolt_a, their_bolt_b]),
            start=(Step.END, 0),
        )
        t = Table(game)
        _cast(t, 0, my_mountain_a, my_bolt_a, theirs)
        t.pass_(0)
        t.pass_(1, then=[moves(my_bolt_a, Zone.GRAVEYARD)])
        t.pass_(0)
        _cast(t, 1, their_mountain, their_bolt_a, mine)
        t.pass_(1)
        t.pass_(0, then=[moves(their_bolt_a, Zone.GRAVEYARD)], note="each Scourge has 2 damage")
        t.pass_to(Step.UPKEEP, 1)
        _cast(t, 1, their_mountain, their_bolt_b, mine)
        t.pass_(1)
        _cast(t, 0, my_mountain_b, my_bolt_b, theirs)
        t.pass_(0)
        t.pass_(1, then=[moves(my_bolt_b, Zone.GRAVEYARD)])
        t.pass_(1)
        t.pass_(0, then=[moves(their_bolt_b, Zone.GRAVEYARD)], note="both Scourges survive 2 more")
        t.run()

    def test_damage_cleared_creature_survives(self) -> None:
        """A creature with non-lethal damage is still on the battlefield after
        cleanup."""
        scourge, mountain, bolt = card(BrazenScourge), card(Mountain), card(BurstLightning)
        game = create_game(
            Side(battlefield=[scourge]),
            Side(battlefield=[mountain], hand=[bolt]),
            start=(Step.END, 0),
        )
        t = Table(game)
        t.pass_(0)
        _cast(t, 1, mountain, bolt, scourge)
        t.pass_(1)
        t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD)], note="the Scourge has 2 damage")
        t.pass_to(Step.UPKEEP, 1)
        final = t.run()
        assert final.where(scourge) is Zone.BATTLEFIELD


# ===========================================================================
# Combat flag clearing
# ===========================================================================


class TestCombatFlagClearing:
    """Tests for cleanup step 4: clear combat-related flags."""

    def test_dealt_deathtouch_damage_cleared(self) -> None:
        """A creature that survived deathtouch damage by being indestructible
        until end of turn has it forgotten: next turn, 2 damage from a source
        without deathtouch does not destroy the 0/5."""
        plunderer, mountain, bolt = card(GutlessPlunderer), card(Mountain), card(BurstLightning)
        turtle, plains, resilience = card(AegisTurtle), card(Plains), card(DivineResilience)
        game = create_game(
            Side(battlefield=[plunderer, mountain], hand=[bolt]),
            Side(battlefield=[turtle, plains], hand=[resilience]),
            start=(Step.BEGIN_COMBAT, 0),
        )
        t = Table(game)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, plunderer, then=[taps(plunderer)])
        t.pass_(0)
        t.pass_(1)
        t.act(1, turtle, scoped={turtle: plunderer})
        t.pass_(0)
        _cast(t, 1, plains, resilience, turtle)
        t.pass_(1)
        t.pass_(0, then=[moves(resilience, Zone.GRAVEYARD)])
        t.pass_(0)
        t.pass_(1, note="the Turtle is dealt deathtouch damage and survives, indestructible")
        t.pass_to(Step.UPKEEP, 1)
        t.pass_(1)
        _cast(t, 0, mountain, bolt, turtle)
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD)], note="the 0/5 survives 2 damage")
        final = t.run()
        assert final.where(turtle) is Zone.BATTLEFIELD

    def test_is_attacking_cleared(self) -> None:
        """A creature that attacked last turn is no longer attacking: Condemn
        ("target attacking creature") cannot target it."""
        lions, plains, condemn = card(SavannahLions), card(Plains), card(Condemn)
        game = create_game(
            Side(battlefield=[lions]),
            Side(battlefield=[plains], hand=[condemn]),
            start=(Step.BEGIN_COMBAT, 0),
        )
        t = Table(game)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        _attack_unblocked(t, [lions], damage_to=1, life_after=18)
        t.pass_to(Step.UPKEEP, 1)
        t.act(1, plains, then=[taps(plains)])
        t.act_illegal(1, condemn, choices=[lions], note="the Lions attacked last turn, not this one")
        t.run()

    def test_is_blocking_cleared(self) -> None:
        """A creature that blocked last turn is no longer blocking: on its
        controller's turn it attacks like any other creature."""
        turtle, lions = card(AegisTurtle), card(SavannahLions)
        game = create_game(
            Side(battlefield=[turtle]),
            Side(battlefield=[lions], library=[Plains]),
            start=(Step.BEGIN_COMBAT, 0),
        )
        t = Table(game)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, turtle, then=[taps(turtle)])
        t.pass_(0)
        t.pass_(1)
        t.act(1, lions, scoped={lions: turtle})
        t.pass_(0)
        t.pass_(1, note="the Turtle and the Lions deal each other combat damage; both survive")
        t.pass_to(Step.DECLARE_ATTACKERS, 1)
        t.act(1, lions, then=[taps(lions)], note="the Lions blocked last turn, not this one")
        t.pass_(1)
        t.pass_(0)
        t.pass_(0)  # declares no blockers
        t.pass_(1)
        t.pass_(0, then=[life(0, 18)])
        t.run()

    def test_combat_state_cleared(self) -> None:
        """Last turn's combat is over: the next turn's combat, with no
        attackers, deals no damage again."""
        lions = card(SavannahLions)
        game = create_game(
            Side(battlefield=[lions]),
            Side(library=[Plains]),
            start=(Step.BEGIN_COMBAT, 0),
        )
        t = Table(game)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        _attack_unblocked(t, [lions], damage_to=1, life_after=18)
        t.pass_to(Step.END, 1)
        final = t.run()
        assert final.players[1].life == 18


# ===========================================================================
# Mana pool emptying
# ===========================================================================


class TestManaPoolEmptying:
    """Tests for cleanup step 5: empty all players' mana pools."""

    def test_active_player_mana_emptied(self) -> None:
        """Mana left in the active player's pool at end of turn cannot pay
        for a spell next turn."""
        lions, growth = card(SavannahLions), card(GiantGrowth)
        game = create_game(
            Side(battlefield=[lions], hand=[growth], mana={ManaType.GREEN: 3, ManaType.RED: 2}),
            Side(),
            start=(Step.END, 0),
        )
        t = Table(game)
        t.pass_to(Step.UPKEEP, 1)
        t.pass_(1)
        t.act_illegal(0, growth, choices=[lions], note="player 0's pool is empty")
        t.run()

    def test_non_active_player_mana_emptied(self) -> None:
        """The non-active player's pool is emptied too."""
        lions, growth = card(SavannahLions), card(GiantGrowth)
        game = create_game(
            Side(),
            Side(battlefield=[lions], hand=[growth], mana={ManaType.GREEN: 5}),
            start=(Step.END, 0),
        )
        t = Table(game)
        t.pass_to(Step.UPKEEP, 1)
        t.act_illegal(1, growth, choices=[lions], note="player 1's pool is empty")
        t.run()

    def test_all_mana_types_emptied(self) -> None:
        """Every mana type leaves the pool: no one-mana spell of any color can
        be cast from it next turn."""
        lions = card(SavannahLions)
        spells = [card(GiantGrowth), card(BurstLightning), card(DivineResilience), card(Stab), card(FleetingDistraction)]
        pool = {mana: 1 for mana in (ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN, ManaType.COLORLESS)}
        game = create_game(
            Side(battlefield=[lions], hand=spells, mana=pool),
            Side(),
            start=(Step.END, 0),
        )
        t = Table(game)
        t.pass_to(Step.UPKEEP, 1)
        t.pass_(1)
        t.act_illegal(0, branches=[[spell] for spell in spells], choices=[lions], note="player 0's pool is empty")
        t.run()


# ===========================================================================
# SBA check during cleanup
# ===========================================================================


class TestSBACheckDuringCleanup:
    """Tests for cleanup step 6: state-based actions are checked."""

    def test_creature_dies_after_eot_buff_expires(self) -> None:
        """A 1/1 pumped by Giant Growth and dealt 2 damage survives cleanup:
        its damage is removed as the +3/+3 ends (rule 514.2). As a 1/1 again,
        2 damage next turn kills it."""
        elves, forest, growth = card(LlanowarElves), card(Forest), card(GiantGrowth)
        mountain, bolt_a, bolt_b = card(Mountain), card(BurstLightning), card(BurstLightning)
        game = create_game(
            Side(battlefield=[elves, forest], hand=[growth]),
            Side(battlefield=[mountain], hand=[bolt_a, bolt_b]),
            start=(Step.END, 0),
        )
        t = Table(game)
        _cast(t, 0, forest, growth, elves)
        t.pass_(0)
        t.pass_(1, then=[moves(growth, Zone.GRAVEYARD)])
        t.pass_(0)
        _cast(t, 1, mountain, bolt_a, elves)
        t.pass_(1)
        t.pass_(0, then=[moves(bolt_a, Zone.GRAVEYARD)], note="the Elves is a 4/4 with 2 damage")
        t.pass_to(Step.UPKEEP, 1)
        _cast(t, 1, mountain, bolt_b, elves)
        t.pass_(1)
        t.pass_(0, then=[moves(bolt_b, Zone.GRAVEYARD), moves(elves, Zone.GRAVEYARD)], note="2 damage kills a 1/1")
        t.run()



# ===========================================================================
# Integration tests
# ===========================================================================


class TestCleanupIntegration:
    """Integration tests verifying full cleanup behavior with realistic scenarios."""

    def test_giant_growth_reverts_after_cleanup(self) -> None:
        """Giant Growth (+3/+3 until end of turn) on a 2/1: next turn it
        attacks for 2."""
        lions, forest, growth = card(SavannahLions), card(Forest), card(GiantGrowth)
        game = create_game(
            Side(battlefield=[lions, forest], hand=[growth], library=[Plains]),
            Side(),
            start=(Step.END, 1),
        )
        t = Table(game)
        t.pass_(1)
        _cast(t, 0, forest, growth, lions)
        t.pass_(0)
        t.pass_(1, then=[moves(growth, Zone.GRAVEYARD)], note="the Lions is 5/4 until end of turn")
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        _attack_unblocked(t, [lions], damage_to=1, life_after=18)
        t.run()

    def test_damage_on_3_3_cleared_creature_alive(self) -> None:
        """A 3/3 dealt 2 combat damage survives 2 more next turn."""
        scourge, lions = card(BrazenScourge), card(SavannahLions)
        mountain, bolt = card(Mountain), card(BurstLightning)
        game = create_game(
            Side(battlefield=[scourge]),
            Side(battlefield=[lions, mountain], hand=[bolt]),
            start=(Step.BEGIN_COMBAT, 0),
        )
        t = Table(game)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, scourge, then=[taps(scourge)])
        t.pass_(0)
        t.pass_(1)
        t.act(1, lions, scoped={lions: scourge})
        t.pass_(0)
        t.pass_(1, then=[moves(lions, Zone.GRAVEYARD)], note="the Scourge is dealt 2 damage")
        t.pass_to(Step.UPKEEP, 1)
        _cast(t, 1, mountain, bolt, scourge)
        t.pass_(1)
        t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD)], note="the Scourge survives 2 more")
        t.run()

    def test_full_cleanup_all_steps_execute(self) -> None:
        """One cleanup does everything: player 0 discards to seven, Giant
        Growth ends, the attacker stops attacking and its damage is removed.

        Player 0's 3/3 attacks and is dealt 2 by a blocker, is pumped to 6/6
        and dealt 2 more. Next turn Condemn cannot target it, and 2 damage
        does not kill it.
        """
        scourge, forest, growth = card(BrazenScourge), card(Forest), card(GiantGrowth)
        hand = [card(Plains) for _ in range(8)]
        lions, mountain, plains = card(SavannahLions), card(Mountain), card(Plains)
        bolt_a, bolt_b, condemn = card(BurstLightning), card(BurstLightning), card(Condemn)
        game = create_game(
            Side(battlefield=[scourge, forest], hand=[growth, *hand]),
            Side(battlefield=[lions, mountain, plains], hand=[bolt_a, bolt_b, condemn]),
            start=(Step.BEGIN_COMBAT, 0),
        )
        t = Table(game)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, scourge, then=[taps(scourge)])
        t.pass_(0)
        t.pass_(1)
        t.act(1, lions, scoped={lions: scourge})
        t.pass_(0)
        t.pass_(1, then=[moves(lions, Zone.GRAVEYARD)], note="the Scourge is dealt 2 damage")
        t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
        _cast(t, 0, forest, growth, scourge)
        t.pass_(0)
        t.pass_(1, then=[moves(growth, Zone.GRAVEYARD)])
        t.pass_to(Step.END, 0)
        t.pass_(0)
        _cast(t, 1, mountain, bolt_a, scourge)
        t.pass_(1)
        t.pass_(0, then=[moves(bolt_a, Zone.GRAVEYARD)], note="the Scourge is a 6/6 with 4 damage")
        _end_turn(t, discards=hand[:1])
        t.act(1, plains, then=[taps(plains)])
        t.act_illegal(1, condemn, choices=[scourge], note="the Scourge no longer attacks")
        _cast(t, 1, mountain, bolt_b, scourge)
        t.pass_(1)
        t.pass_(0, then=[moves(bolt_b, Zone.GRAVEYARD)], note="the 3/3 survives 2 damage")
        final = t.run()
        assert len(final.players[0].hand) == 7

    def test_max_hand_size_constant_is_7(self) -> None:
        """MAX_HAND_SIZE is defined as 7."""
        assert MAX_HAND_SIZE == 7


# ===========================================================================
# Rule 514.3a — Re-cleanup loop
# ===========================================================================


class TestReCleanupLoop:
    """Tests for rule 514.3a: if SBAs are performed or triggered abilities
    fire during cleanup, another cleanup step occurs after resolving."""


    def test_stack_trigger_during_cleanup_causes_recleanup(self) -> None:
        """Player 0 discards to hand size in cleanup and Tinybones triggers:
        players get priority in that cleanup step, player 1's Burst Lightning
        marks 2 damage on the Scourge, and another cleanup step removes it —
        a second Burst Lightning on player 1's turn does not kill it."""
        hand = [card(Plains) for _ in range(8)]
        scourge, mountain = card(BrazenScourge), card(Mountain)
        first, second = card(BurstLightning), card(BurstLightning)
        game = create_game(
            Side(hand=hand, battlefield=[scourge]),
            Side(hand=[first, second], battlefield=[card(TinybonesBaubleBurglar), mountain], library=[card(Plains)]),
            start=(Step.END, 0),
        )
        t = Table(game)
        t.pass_(0, choices=[hand[0]])
        t.pass_(1, then=[moves(hand[0], Zone.GRAVEYARD), cleanup_trigger(TinybonesBaubleBurglarAbility1, 1)])
        t.pass_(0)
        _cast(t, 1, mountain, first, scourge)
        t.pass_(1)
        t.pass_(0, then=[moves(first, Zone.GRAVEYARD)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(TinybonesBaubleBurglarAbility1), moves(hand[0], Zone.EXILE)])
        t.pass_(0)
        t.pass_(1, note="the stack is empty: another cleanup step, then player 1's turn")
        _cast(t, 1, mountain, second, scourge)
        t.pass_(1)
        t.pass_(0, then=[moves(second, Zone.GRAVEYARD)], note="the Scourge survives: its damage was removed")
        t.run()

    def test_no_recleanup_when_no_sba_and_empty_stack(self) -> None:
        """When cleanup performs no state-based action and nothing triggers,
        the game goes on to the next turn (no loop)."""
        scourge, mountain, bolt = card(BrazenScourge), card(Mountain), card(BurstLightning)
        game = create_game(
            Side(battlefield=[scourge]),
            Side(battlefield=[mountain], hand=[bolt]),
            start=(Step.END, 0),
        )
        t = Table(game)
        t.pass_(0)
        _cast(t, 1, mountain, bolt, scourge)
        t.pass_(1)
        t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD)])
        t.pass_to(Step.UPKEEP, 1)
        final = t.run()
        assert final.step is Step.UPKEEP and final.active == 1


# ===========================================================================
# Discard down to hand size
# ===========================================================================


class TestDiscardLargeHands:
    """Discard always reaches max hand size."""

    def test_discard_9_to_7_with_baseline(self) -> None:
        """Player with 9 cards discards 2 to reach 7."""
        game, hand, _ = _discard_game(9)
        t = Table(game)
        _end_turn(t, discards=hand[:2])
        final = t.run()
        assert len(final.players[0].hand) == 7
        assert len(final.players[0].graveyard) == 2

    def test_discard_large_hand_with_baseline(self) -> None:
        """Player with 15 cards discards 8 cards to reach 7."""
        game, hand, _ = _discard_game(15)
        t = Table(game)
        _end_turn(t, discards=hand[:8])
        final = t.run()
        assert len(final.players[0].hand) == 7
        assert len(final.players[0].graveyard) == 8


# ===========================================================================
# Edge cases
# ===========================================================================


class TestCleanupEdgeCases:
    """Edge case tests for cleanup step."""

    def test_no_creatures_on_battlefield(self) -> None:
        """Cleanup with no creatures still empties the pool: the red mana left
        cannot pay for Burst Lightning next turn."""
        bolt = card(BurstLightning)
        game = create_game(
            Side(hand=[bolt], mana={ManaType.RED: 2}),
            Side(),
            start=(Step.END, 0),
        )
        t = Table(game)
        t.pass_to(Step.UPKEEP, 1)
        t.pass_(1)
        t.act_illegal(0, bolt, choices=[player(1)], note="player 0's pool is empty")
        final = t.run()
        assert final.players[0].battlefield == ()

    def test_mana_pool_already_empty(self) -> None:
        """Cleanup with nothing to do and empty pools leads into the next turn."""
        game = create_game(Side(), Side(), start=(Step.END, 0))
        t = Table(game)
        t.pass_to(Step.UPKEEP, 1)
        final = t.run()
        assert final.step is Step.UPKEEP and final.active == 1

    def test_empty_battlefield_and_empty_hand(self) -> None:
        """Cleanup works with a completely empty board: no creatures, no cards
        in hand, no mana, nothing to discard."""
        game = create_game(Side(), Side(), start=(Step.END, 0))
        t = Table(game)
        _end_turn(t)
        final = t.run()
        assert final.players[0].hand == () and final.players[0].battlefield == ()

    def test_zero_cards_in_hand_no_discard(self) -> None:
        """Player with 0 cards in hand: nothing is discarded."""
        game, _, _ = _discard_game(0)
        t = Table(game)
        _end_turn(t)
        final = t.run()
        assert final.players[0].hand == () and final.players[0].graveyard == ()

