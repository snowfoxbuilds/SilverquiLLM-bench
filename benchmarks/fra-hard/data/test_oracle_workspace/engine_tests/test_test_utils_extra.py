"""Additional tests for test_utils.py — covers edge cases and gaps
not addressed by the implementer's 37 meta-tests.

Focus areas:
- Descriptive error messages (content of TestSetupError messages)
- Boundary/edge cases for each function
- Phase coverage for advance_to_phase (beginning steps, all combat steps)
- Empty-list and degenerate inputs
- Mana replacement semantics in set_board_state
- cast_spell with sorcery card type
- Non-empty stack error for cast_spell
- Integration: sequential spell casting
"""

from __future__ import annotations

import pytest

from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.decisions import GameRef
from engine.intent_player import DeterministicPlayer, Intent
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


def _bear(name: str = "Bear") -> Creature:
    """Create a 2/2 creature with {1}{G} mana cost."""
    return Creature(
        name=name,
        mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}),
        base_power=2,
        base_toughness=2,
    )


def _instant(name: str = "Zap") -> Instant:
    """Create a minimal instant spell with {R} mana cost."""
    return Instant(
        name=name,
        mana_cost=ManaCost(pips={ManaType.RED: 1}),
    )


def _sorcery(name: str = "Blaze") -> Sorcery:
    """Create a minimal sorcery spell with {R} mana cost."""
    return Sorcery(
        name=name,
        mana_cost=ManaCost(pips={ManaType.RED: 1}),
    )


# ===================================================================
# create_game — additional coverage
# ===================================================================


class TestCreateGameExtra:
    """Additional tests for create_game."""

    def test_custom_life_totals(self) -> None:
        """Verify non-default starting life totals are honoured."""
        game = create_game(player1_life=40, player2_life=10)
        assert game.players[0].life == 40
        assert game.players[1].life == 10

    def test_default_player_names(self) -> None:
        """Default names should be Player1/Player2."""
        game = create_game()
        assert game.players[0].name == "Player1"
        assert game.players[1].name == "Player2"

    def test_game_starts_at_beginning_phase(self) -> None:
        """Newly created game should start at BEGINNING / UNTAP."""
        game = create_game()
        assert game.phase == Phase.BEGINNING
        assert game.step == Step.UNTAP

    def test_players_are_deterministic(self) -> None:
        """Both players should be DeterministicPlayer instances."""
        game = create_game()
        for p in game.players:
            assert isinstance(p, DeterministicPlayer)


# ===================================================================
# set_board_state — additional coverage
# ===================================================================


class TestSetBoardStateExtra:
    """Additional edge-case tests for set_board_state."""

    def test_negative_player_index_raises(self) -> None:
        """Negative index should raise TestSetupError, not silently wrap."""
        game = create_game()
        with pytest.raises(TestSetupError, match="Invalid player_index -1"):
            set_board_state(game, -1, life=10)

    def test_player_index_1_is_valid(self) -> None:
        """Player index 1 should be valid for a 2-player game."""
        game = create_game()
        set_board_state(game, 1, life=5)
        assert game.players[1].life == 5

    def test_set_empty_hand(self) -> None:
        """Setting hand to empty list should clear the hand zone."""
        game = create_game()
        card = CardImpl(name="Temp")
        set_board_state(game, 0, hand=[card])
        assert len(game.get_hand(game.players[0])) == 1
        # Now clear it
        set_board_state(game, 0, hand=[])
        assert len(game.get_hand(game.players[0])) == 0

    def test_set_empty_battlefield(self) -> None:
        """Setting battlefield to empty list should clear it."""
        game = create_game()
        bear = _bear()
        set_board_state(game, 0, battlefield=[bear])
        assert len(game.get_battlefield(game.players[0])) == 1
        set_board_state(game, 0, battlefield=[])
        assert len(game.get_battlefield(game.players[0])) == 0

    def test_set_empty_graveyard(self) -> None:
        """Setting graveyard to empty list should clear it."""
        game = create_game()
        card = CardImpl(name="Dead")
        set_board_state(game, 0, graveyard=[card])
        assert len(game.get_graveyard(game.players[0])) == 1
        set_board_state(game, 0, graveyard=[])
        assert len(game.get_graveyard(game.players[0])) == 0

    def test_mana_replaces_existing_pool(self) -> None:
        """Setting mana should empty existing pool before adding new mana."""
        game = create_game()
        set_board_state(game, 0, mana={ManaType.RED: 5})
        assert game.players[0].mana_pool.get(ManaType.RED) == 5

        # Now set different mana — RED should be gone
        set_board_state(game, 0, mana={ManaType.BLUE: 3})
        assert game.players[0].mana_pool.get(ManaType.BLUE) == 3
        assert game.players[0].mana_pool.get(ManaType.RED) == 0

    def test_life_none_leaves_unchanged(self) -> None:
        """Passing life=None (default) should not change life."""
        game = create_game()
        original_life = game.players[0].life
        set_board_state(game, 0, hand=[])  # only change hand
        assert game.players[0].life == original_life

    def test_mana_none_leaves_pool_unchanged(self) -> None:
        """Passing mana=None (default) should not clear the mana pool."""
        game = create_game()
        set_board_state(game, 0, mana={ManaType.GREEN: 4})
        # Now call set_board_state without mana — pool should stay
        set_board_state(game, 0, life=15)
        assert game.players[0].mana_pool.get(ManaType.GREEN) == 4

    def test_card_controller_set_on_battlefield(self) -> None:
        """Cards placed on battlefield should have controller set to the player."""
        game = create_game()
        bear = _bear("OwnedBear")
        set_board_state(game, 1, battlefield=[bear])
        assert bear.controller is game.players[1]

    def test_card_owner_set_in_graveyard(self) -> None:
        """Cards placed in graveyard should have owner set to the player."""
        game = create_game()
        card = CardImpl(name="Buried")
        set_board_state(game, 0, graveyard=[card])
        assert card.owner is game.players[0]

    def test_card_owner_set_in_hand(self) -> None:
        """Cards placed in hand should have owner set to the player."""
        game = create_game()
        card = CardImpl(name="Held")
        set_board_state(game, 1, hand=[card])
        assert card.owner is game.players[1]

    def test_multiple_cards_in_zone(self) -> None:
        """Multiple cards should all be placed and retrievable."""
        game = create_game()
        cards = [CardImpl(name=f"Card{i}") for i in range(5)]
        set_board_state(game, 0, hand=cards)
        hand = game.get_hand(game.players[0])
        for c in cards:
            assert hand.contains(c)
        assert len(hand) == 5


# ===================================================================
# cast_spell — additional coverage
# ===================================================================


class TestCastSpellExtra:
    """Additional edge-case tests for cast_spell."""

    def test_error_message_includes_hand_contents(self) -> None:
        """Error for missing card should list hand contents."""
        game = create_game()
        card = CardImpl(name="SomeCard")
        set_board_state(game, 0, hand=[card])
        with pytest.raises(TestSetupError, match="SomeCard") as exc_info:
            cast_spell(game, 0, "MissingCard")
        # The error should mention what the hand contains
        assert "Hand contains:" in str(exc_info.value)
        assert "SomeCard" in str(exc_info.value)

    def test_cast_sorcery_from_hand(self) -> None:
        """Sorcery should resolve to graveyard."""
        game = create_game()
        blaze = _sorcery("Blaze")
        set_board_state(game, 0, hand=[blaze], mana={ManaType.RED: 1})
        cast_spell(game, 0, "Blaze")
        gy = game.get_graveyard(game.players[0])
        assert gy.contains(blaze)
        hand = game.get_hand(game.players[0])
        assert not hand.contains(blaze)

    def test_cast_spell_adjusts_phase_for_sorcery(self) -> None:
        """Sorcery-speed spells should auto-adjust to main phase."""
        game = create_game()
        blaze = _sorcery("Blaze")
        set_board_state(game, 0, hand=[blaze], mana={ManaType.RED: 1})
        # Start at beginning phase
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP
        cast_spell(game, 0, "Blaze")
        # After cast_spell, phase should have been adjusted
        gy = game.get_graveyard(game.players[0])
        assert gy.contains(blaze)

    def test_cast_with_first_matching_card(self) -> None:
        """When multiple cards share a name, cast_spell should use the first match."""
        game = create_game()
        bear1 = _bear("Bear")
        bear2 = _bear("Bear")
        set_board_state(
            game, 0,
            hand=[bear1, bear2],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        cast_spell(game, 0, "Bear")
        bf = game.get_battlefield(game.players[0])
        # The first bear should be on the battlefield
        assert bf.contains(bear1)
        # The second bear should still be in hand
        hand = game.get_hand(game.players[0])
        assert hand.contains(bear2)

    def test_cast_by_player_1(self) -> None:
        """Player 1 (index 1) should be able to cast spells."""
        game = create_game()
        zap = _instant("Zap")
        set_board_state(game, 1, hand=[zap], mana={ManaType.RED: 1})
        cast_spell(game, 1, "Zap")
        gy = game.get_graveyard(game.players[1])
        assert gy.contains(zap)


# ===================================================================
# advance_to_phase — additional coverage
# ===================================================================


class TestAdvanceToPhaseExtra:
    """Additional tests for advance_to_phase covering all major phases."""

    def test_advance_to_beginning_upkeep(self) -> None:
        """Should be able to advance to BEGINNING / UPKEEP."""
        game = create_game()
        advance_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
        assert game.phase == Phase.BEGINNING
        assert game.step == Step.UPKEEP

    def test_advance_to_beginning_draw(self) -> None:
        """Should be able to advance to BEGINNING / DRAW."""
        game = create_game()
        advance_to_phase(game, Phase.BEGINNING, Step.DRAW)
        assert game.phase == Phase.BEGINNING
        assert game.step == Step.DRAW

    def test_advance_to_combat_begin_combat(self) -> None:
        """Should be able to advance to COMBAT / BEGIN_COMBAT."""
        game = create_game()
        advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
        assert game.phase == Phase.COMBAT
        assert game.step == Step.BEGIN_COMBAT

    def test_advance_to_combat_damage(self) -> None:
        """Should be able to advance to COMBAT / COMBAT_DAMAGE."""
        game = create_game()
        advance_to_phase(game, Phase.COMBAT, Step.COMBAT_DAMAGE)
        assert game.phase == Phase.COMBAT
        assert game.step == Step.COMBAT_DAMAGE

    def test_advance_to_combat_end_combat(self) -> None:
        """Should be able to advance to COMBAT / END_COMBAT."""
        game = create_game()
        advance_to_phase(game, Phase.COMBAT, Step.END_COMBAT)
        assert game.phase == Phase.COMBAT
        assert game.step == Step.END_COMBAT

    def test_advance_to_cleanup(self) -> None:
        """Should be able to advance to ENDING / CLEANUP."""
        game = create_game()
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        assert game.phase == Phase.ENDING
        assert game.step == Step.CLEANUP

    def test_invalid_combat_none_step_raises(self) -> None:
        """COMBAT with step=None is invalid in the turn sequence."""
        game = create_game()
        with pytest.raises(TestSetupError, match="Invalid phase/step"):
            advance_to_phase(game, Phase.COMBAT, None)

    def test_invalid_ending_none_step_raises(self) -> None:
        """ENDING with step=None is invalid in the turn sequence."""
        game = create_game()
        with pytest.raises(TestSetupError, match="Invalid phase/step"):
            advance_to_phase(game, Phase.ENDING, None)

    def test_error_message_mentions_valid_combinations(self) -> None:
        """Invalid phase/step error should list valid combinations."""
        game = create_game()
        with pytest.raises(TestSetupError, match="Valid combinations") as exc_info:
            advance_to_phase(game, Phase.PRECOMBAT_MAIN, Step.UNTAP)
        assert "Valid combinations" in str(exc_info.value)


# ===================================================================
# declare_attackers — additional coverage
# ===================================================================


class TestDeclareAttackersExtra:
    """Additional edge-case tests for declare_attackers."""

    def test_error_message_lists_battlefield_contents(self) -> None:
        """Attacker-not-found error should list what IS on the battlefield."""
        game = create_game()
        bear = _bear("ActualBear")
        bear.summoning_sick = False
        set_board_state(game, 0, battlefield=[bear])
        game.active_player_index = 0
        with pytest.raises(TestSetupError, match="Battlefield contains:") as exc_info:
            declare_attackers(game, ["Phantom"])
        assert "ActualBear" in str(exc_info.value)

    def test_declare_attackers_requires_deterministic_player(self) -> None:
        """If active player is not a DeterministicPlayer, should error."""
        # This is implicitly tested via the implementation check, but
        # create_game always creates DeterministicPlayer, so this
        # verifies the happy path doesn't error on that check.
        game = create_game()
        bear = _bear("TestBear")
        bear.summoning_sick = False
        set_board_state(game, 0, battlefield=[bear])
        game.active_player_index = 0
        # Should not raise - active player IS a DeterministicPlayer
        declare_attackers(game, ["TestBear"])
        assert bear.is_attacking


# ===================================================================
# declare_blockers — additional coverage
# ===================================================================


class TestDeclareBlockersExtra:
    """Additional edge-case tests for declare_blockers."""

    def test_blocker_error_message_lists_defending_battlefield(self) -> None:
        """Blocker-not-found error should list what IS on defending battlefield."""
        game = create_game()
        attacker = _bear("Attacker")
        attacker.summoning_sick = False
        defender = _bear("RealDefender")
        defender.summoning_sick = False

        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[defender])
        game.active_player_index = 0

        declare_attackers(game, ["Attacker"])
        advance_to_phase(game, Phase.COMBAT, Step.DECLARE_BLOCKERS)

        with pytest.raises(TestSetupError, match="not found on defending") as exc_info:
            declare_blockers(game, {"Attacker": ["NonExistent"]})
        assert "RealDefender" in str(exc_info.value)

    def test_attacker_error_message_lists_active_battlefield(self) -> None:
        """Attacker-not-found in blockers should list active player's battlefield."""
        game = create_game()
        attacker = _bear("RealAttacker")
        attacker.summoning_sick = False
        blocker = _bear("Blocker")
        blocker.summoning_sick = False

        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[blocker])
        game.active_player_index = 0

        declare_attackers(game, ["RealAttacker"])
        advance_to_phase(game, Phase.COMBAT, Step.DECLARE_BLOCKERS)

        with pytest.raises(TestSetupError, match="not found on active") as exc_info:
            declare_blockers(game, {"WrongAttacker": ["Blocker"]})
        assert "RealAttacker" in str(exc_info.value)

    def test_multiple_blockers_on_one_attacker(self) -> None:
        """Multiple creatures should be able to block a single attacker."""
        game = create_game()
        attacker = _bear("Attacker")
        attacker.summoning_sick = False
        blocker1 = _bear("Blocker1")
        blocker1.summoning_sick = False
        blocker2 = _bear("Blocker2")
        blocker2.summoning_sick = False

        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[blocker1, blocker2])
        game.active_player_index = 0

        # When an attacker is multi-blocked the engine raises a damage-order
        # Player Query to the attacker's controller (p0). A Baseline Intent
        # with no preferences answers it by taking the offered blockers in
        # implementation order.
        p0 = game.players[0]
        assert isinstance(p0, DeterministicPlayer)
        p0.set_baseline(Intent(pattern=GameRef()))

        declare_attackers(game, ["Attacker"])
        advance_to_phase(game, Phase.COMBAT, Step.DECLARE_BLOCKERS)
        declare_blockers(game, {"Attacker": ["Blocker1", "Blocker2"]})
        assert blocker1.is_blocking
        assert blocker2.is_blocking


# ===================================================================
# Integration — additional scenarios
# ===================================================================


class TestMetaIntegrationExtra:
    """Additional integration tests combining multiple test_utils functions."""

    def test_cast_instant_then_creature(self) -> None:
        """Integration: cast an instant then a creature sequentially."""
        game = create_game()
        zap = _instant("Zap")
        bear = _bear("Bear")
        set_board_state(
            game, 0,
            hand=[zap, bear],
            mana={ManaType.RED: 2, ManaType.GREEN: 1},
        )

        # Cast the instant first
        cast_spell(game, 0, "Zap")
        gy = game.get_graveyard(game.players[0])
        assert gy.contains(zap)

        # Now cast the creature (need to re-add mana since it may have been used)
        set_board_state(game, 0, mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Bear")
        bf = game.get_battlefield(game.players[0])
        assert bf.contains(bear)

    def test_set_board_state_advance_and_verify(self) -> None:
        """Integration: set state, advance phases, verify state persists."""
        game = create_game()
        bear = _bear("PersistBear")
        set_board_state(game, 0, battlefield=[bear], life=10)

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.players[0].life == 10
        bf = game.get_battlefield(game.players[0])
        assert bf.contains(bear)

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        assert game.players[0].life == 10
        assert bf.contains(bear)

    def test_set_board_for_both_players(self) -> None:
        """Integration: set different board states for both players."""
        game = create_game()
        bear1 = _bear("P1Bear")
        bear2 = _bear("P2Bear")

        set_board_state(game, 0, battlefield=[bear1], life=15)
        set_board_state(game, 1, battlefield=[bear2], life=12)

        assert game.players[0].life == 15
        assert game.players[1].life == 12
        assert game.get_battlefield(game.players[0]).contains(bear1)
        assert game.get_battlefield(game.players[1]).contains(bear2)
        # Each bear should NOT be on the other's battlefield
        assert not game.get_battlefield(game.players[0]).contains(bear2)
        assert not game.get_battlefield(game.players[1]).contains(bear1)

    def test_full_workflow_set_cast_advance(self) -> None:
        """Integration: set board → cast creature → advance to ending → verify."""
        game = create_game()
        bear = _bear("WorkflowBear")
        set_board_state(
            game, 0,
            hand=[bear],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
            life=18,
        )

        cast_spell(game, 0, "WorkflowBear")
        bf = game.get_battlefield(game.players[0])
        assert bf.contains(bear)

        advance_to_phase(game, Phase.ENDING, Step.END)
        assert game.phase == Phase.ENDING
        assert game.step == Step.END
        # Bear should still be on battlefield
        assert bf.contains(bear)
        assert game.players[0].life == 18

    def test_cast_creature_then_enter_combat(self) -> None:
        """Integration: cast creature, advance to combat, declare as attacker."""
        game = create_game()
        bear = _bear("CombatBear")
        set_board_state(
            game, 0,
            hand=[bear],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )

        cast_spell(game, 0, "CombatBear")
        bf = game.get_battlefield(game.players[0])
        assert bf.contains(bear)

        # Remove summoning sickness for test purposes
        bear.summoning_sick = False
        game.active_player_index = 0

        declare_attackers(game, ["CombatBear"])
        assert bear.is_attacking
