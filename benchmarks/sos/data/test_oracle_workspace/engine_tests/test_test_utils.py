"""Meta-tests for test_utils.py — verifies test utility helpers work correctly.

Uses test_utils itself to set up boards and cast spells, verifying
that the convenience wrappers behave as expected.
"""

from __future__ import annotations

import pytest

from engine.card import CardImpl, Creature, Instant
from engine.player import DeterministicPlayer
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, Zone

from test_utils import (
    TestSetupError,
    advance_to_phase,
    cast_spell,
    create_game,
    declare_attackers,
    declare_blockers,
    set_board_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deck(size: int = 20, prefix: str = "Card") -> list[CardImpl]:
    """Create a deck of minimal cards."""
    return [CardImpl(name=f"{prefix}_{i}") for i in range(size)]


def _bear(name: str = "Bear") -> Creature:
    """Create a 2/2 creature."""
    return Creature(
        name=name,
        mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}),
        base_power=2,
        base_toughness=2,
    )


def _instant(name: str = "Zap") -> Instant:
    """Create a minimal instant spell."""
    return Instant(
        name=name,
        mana_cost=ManaCost(pips={ManaType.RED: 1}),
    )


# ===================================================================
# create_game
# ===================================================================


class TestCreateGame:
    """Tests for the create_game convenience wrapper."""

    def test_creates_game_with_empty_decks(self) -> None:
        game = create_game()
        assert len(game.players) == 2

    def test_creates_game_with_decks(self) -> None:
        d1 = _make_deck(20, "P1")
        d2 = _make_deck(20, "P2")
        game = create_game(d1, d2)
        # Each player drew 7, so hand should have 7 and library 13
        p1 = game.players[0]
        assert len(game.get_hand(p1)) == 7
        assert len(game.get_library(p1)) == 13

    def test_player_names(self) -> None:
        game = create_game(player1_name="Alice", player2_name="Bob")
        assert game.players[0].name == "Alice"
        assert game.players[1].name == "Bob"

    def test_life_totals(self) -> None:
        game = create_game()
        assert game.players[0].life == 20
        assert game.players[1].life == 20

    def test_active_player_is_player1(self) -> None:
        game = create_game()
        assert game.active_player_index == 0

    def test_scripts_passed_to_players(self) -> None:
        game = create_game(scripts=(["a", "b"], ["c"]))
        p1 = game.players[0]
        p2 = game.players[1]
        assert isinstance(p1, DeterministicPlayer)
        assert isinstance(p2, DeterministicPlayer)
        assert p1.remaining_choices == 2
        assert p2.remaining_choices == 1


# ===================================================================
# set_board_state
# ===================================================================


class TestSetBoardState:
    """Tests for set_board_state."""

    def test_set_battlefield(self) -> None:
        game = create_game()
        bear = _bear()
        set_board_state(game, 0, battlefield=[bear])
        bf = game.get_battlefield(game.players[0])
        assert bf.contains(bear)
        assert bear.owner is game.players[0]
        assert bear.controller is game.players[0]

    def test_set_hand(self) -> None:
        game = create_game()
        card = CardImpl(name="TestCard")
        set_board_state(game, 0, hand=[card])
        hand = game.get_hand(game.players[0])
        assert hand.contains(card)

    def test_set_graveyard(self) -> None:
        game = create_game()
        card = CardImpl(name="DeadCard")
        set_board_state(game, 1, graveyard=[card])
        gy = game.get_graveyard(game.players[1])
        assert gy.contains(card)

    def test_set_life(self) -> None:
        game = create_game()
        set_board_state(game, 0, life=10)
        assert game.players[0].life == 10

    def test_set_mana(self) -> None:
        game = create_game()
        set_board_state(game, 0, mana={ManaType.RED: 3, ManaType.GREEN: 2})
        pool = game.players[0].mana_pool
        assert pool.get(ManaType.RED) == 3
        assert pool.get(ManaType.GREEN) == 2

    def test_replaces_zone_contents(self) -> None:
        game = create_game()
        card1 = CardImpl(name="OldCard")
        card2 = CardImpl(name="NewCard")
        set_board_state(game, 0, hand=[card1])
        set_board_state(game, 0, hand=[card2])
        hand = game.get_hand(game.players[0])
        assert not hand.contains(card1)
        assert hand.contains(card2)

    def test_invalid_player_index_raises(self) -> None:
        game = create_game()
        with pytest.raises(TestSetupError, match="Invalid player_index"):
            set_board_state(game, 5)

    def test_leaves_unspecified_zones_unchanged(self) -> None:
        d1 = _make_deck(20)
        game = create_game(d1, _make_deck(20))
        original_hand_size = len(game.get_hand(game.players[0]))

        # Only set battlefield — hand should be unchanged
        bear = _bear()
        set_board_state(game, 0, battlefield=[bear])
        assert len(game.get_hand(game.players[0])) == original_hand_size

    def test_set_multiple_zones_at_once(self) -> None:
        game = create_game()
        bear = _bear("BattleBear")
        card = CardImpl(name="HandCard")
        dead = CardImpl(name="DeadCard")

        set_board_state(
            game,
            0,
            battlefield=[bear],
            hand=[card],
            graveyard=[dead],
            life=15,
            mana={ManaType.WHITE: 5},
        )

        p = game.players[0]
        assert game.get_battlefield(p).contains(bear)
        assert game.get_hand(p).contains(card)
        assert game.get_graveyard(p).contains(dead)
        assert p.life == 15
        assert p.mana_pool.get(ManaType.WHITE) == 5


# ===================================================================
# cast_spell
# ===================================================================


class TestCastSpell:
    """Tests for cast_spell."""

    def test_cast_instant_from_hand(self) -> None:
        game = create_game()
        zap = _instant("Zap")
        set_board_state(game, 0, hand=[zap], mana={ManaType.RED: 1})
        cast_spell(game, 0, "Zap")
        # After casting and resolving, the instant should be in graveyard
        gy = game.get_graveyard(game.players[0])
        assert gy.contains(zap)
        hand = game.get_hand(game.players[0])
        assert not hand.contains(zap)

    def test_cast_creature_from_hand(self) -> None:
        game = create_game()
        bear = _bear("Bear")
        set_board_state(
            game, 0,
            hand=[bear],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        cast_spell(game, 0, "Bear")
        bf = game.get_battlefield(game.players[0])
        assert bf.contains(bear)

    def test_card_not_in_hand_raises(self) -> None:
        game = create_game()
        with pytest.raises(TestSetupError, match="not found in player"):
            cast_spell(game, 0, "NonExistentCard")

    def test_invalid_player_raises(self) -> None:
        game = create_game()
        with pytest.raises(TestSetupError, match="Invalid player_index"):
            cast_spell(game, 5, "Card")

    def test_insufficient_mana_raises(self) -> None:
        game = create_game()
        bear = _bear("Bear")
        set_board_state(game, 0, hand=[bear])
        # No mana — should fail
        with pytest.raises(TestSetupError, match="Failed to cast"):
            cast_spell(game, 0, "Bear")


# ===================================================================
# advance_to_phase
# ===================================================================


class TestAdvanceToPhase:
    """Tests for advance_to_phase."""

    def test_advance_to_precombat_main(self) -> None:
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.phase == Phase.PRECOMBAT_MAIN
        assert game.step is None

    def test_advance_to_combat_declare_attackers(self) -> None:
        game = create_game()
        advance_to_phase(game, Phase.COMBAT, Step.DECLARE_ATTACKERS)
        assert game.phase == Phase.COMBAT
        assert game.step == Step.DECLARE_ATTACKERS

    def test_advance_to_postcombat_main(self) -> None:
        game = create_game()
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        assert game.phase == Phase.POSTCOMBAT_MAIN

    def test_already_at_target_is_noop(self) -> None:
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        turn_before = game.turn_number
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        # Should not have advanced past target
        assert game.phase == Phase.PRECOMBAT_MAIN
        assert game.turn_number == turn_before

    def test_invalid_phase_step_raises(self) -> None:
        game = create_game()
        with pytest.raises(TestSetupError, match="Invalid phase/step"):
            advance_to_phase(game, Phase.PRECOMBAT_MAIN, Step.UNTAP)

    def test_advance_to_ending(self) -> None:
        game = create_game()
        advance_to_phase(game, Phase.ENDING, Step.END)
        assert game.phase == Phase.ENDING
        assert game.step == Step.END

    def test_advance_cannot_cross_turn_boundary(self) -> None:
        """Post-Phase-18 semantics: advance_to_phase fast-forwards within the
        current turn only — crossing a turn boundary raises (multi-player
        turn control is deferred per AUDITED-TEST-API.md)."""
        game = create_game()
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        with pytest.raises(TestSetupError, match="turn boundary"):
            advance_to_phase(game, Phase.BEGINNING, Step.UNTAP)


# ===================================================================
# declare_attackers
# ===================================================================


class TestDeclareAttackers:
    """Tests for declare_attackers."""

    def test_declare_single_attacker(self) -> None:
        game = create_game()
        bear = _bear("AttackBear")
        bear.summoning_sick = False
        set_board_state(game, 0, battlefield=[bear])
        game.active_player_index = 0
        declare_attackers(game, ["AttackBear"])
        assert bear.is_attacking is True
        assert bear.is_tapped is True

    def test_declare_multiple_attackers(self) -> None:
        game = create_game()
        bear1 = _bear("Bear1")
        bear1.summoning_sick = False
        bear2 = _bear("Bear2")
        bear2.summoning_sick = False
        set_board_state(game, 0, battlefield=[bear1, bear2])
        game.active_player_index = 0
        declare_attackers(game, ["Bear1", "Bear2"])
        assert bear1.is_attacking is True
        assert bear2.is_attacking is True

    def test_attacker_not_found_raises(self) -> None:
        game = create_game()
        with pytest.raises(TestSetupError, match="not found on active player"):
            declare_attackers(game, ["Phantom"])

    def test_advances_to_combat(self) -> None:
        game = create_game()
        bear = _bear("CombatBear")
        bear.summoning_sick = False
        set_board_state(game, 0, battlefield=[bear])
        game.active_player_index = 0
        # Start from beginning phase
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP
        declare_attackers(game, ["CombatBear"])
        assert game.phase == Phase.COMBAT
        assert game.step == Step.DECLARE_ATTACKERS


# ===================================================================
# declare_blockers
# ===================================================================


class TestDeclareBlockers:
    """Tests for declare_blockers."""

    def test_declare_blocker(self) -> None:
        game = create_game()
        attacker = _bear("Attacker")
        attacker.summoning_sick = False
        blocker = _bear("Blocker")
        blocker.summoning_sick = False

        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[blocker])
        game.active_player_index = 0

        # Declare attackers first
        declare_attackers(game, ["Attacker"])

        # Now declare blockers (the legacy helper advances the step itself)
        declare_blockers(game, {"Attacker": ["Blocker"]})
        assert blocker.is_blocking is True

    def test_attacker_not_found_raises(self) -> None:
        game = create_game()
        attacker = _bear("Attacker")
        attacker.summoning_sick = False
        blocker = _bear("Blocker")
        blocker.summoning_sick = False

        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[blocker])
        game.active_player_index = 0

        declare_attackers(game, ["Attacker"])

        with pytest.raises(TestSetupError, match="Attacker.*not found"):
            declare_blockers(game, {"Phantom": ["Blocker"]})

    def test_blocker_not_found_raises(self) -> None:
        game = create_game()
        attacker = _bear("Attacker")
        attacker.summoning_sick = False
        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[])
        game.active_player_index = 0

        declare_attackers(game, ["Attacker"])

        with pytest.raises(TestSetupError, match="Blocker.*not found"):
            declare_blockers(game, {"Attacker": ["Ghost"]})


# ===================================================================
# Integration — meta-test using test_utils to set up board + cast
# ===================================================================


class TestMetaIntegration:
    """Meta-test: use test_utils to set up a board and cast a spell."""

    def test_setup_board_and_cast_creature(self) -> None:
        """Full integration: create game → set board → cast spell → verify."""
        game = create_game()

        bear = _bear("Grizzly")
        set_board_state(
            game,
            0,
            hand=[bear],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
            life=18,
        )

        # Verify pre-conditions
        assert game.players[0].life == 18
        hand = game.get_hand(game.players[0])
        assert hand.contains(bear)

        # Cast the bear
        cast_spell(game, 0, "Grizzly")

        # Verify it resolved to the battlefield
        bf = game.get_battlefield(game.players[0])
        assert bf.contains(bear)
        assert not hand.contains(bear)

    def test_setup_combat(self) -> None:
        """Integration: set up creatures and run combat."""
        game = create_game()

        attacker = _bear("Attacker")
        attacker.summoning_sick = False
        blocker = _bear("Blocker")
        blocker.summoning_sick = False

        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[blocker])
        game.active_player_index = 0

        declare_attackers(game, ["Attacker"])
        assert attacker.is_attacking

        declare_blockers(game, {"Attacker": ["Blocker"]})
        assert blocker.is_blocking

    def test_set_board_state_and_advance_phase(self) -> None:
        """Integration: set board state and advance to a specific phase.

        Post-Phase-18 advance_to_phase processes combat declarations from the
        choice script, so passing through combat with an eligible attacker
        needs a scripted (empty) attacker list."""
        game = create_game(scripts=([[]], []))
        bear = _bear("TestBear")
        set_board_state(game, 0, battlefield=[bear], life=15)

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        assert game.phase == Phase.POSTCOMBAT_MAIN
        assert game.players[0].life == 15

        bf = game.get_battlefield(game.players[0])
        assert bf.contains(bear)
