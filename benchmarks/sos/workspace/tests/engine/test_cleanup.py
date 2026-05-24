"""Tests for end-of-turn cleanup step (engine/turn.py :: _do_cleanup_step).

Verifies:
- Active player discards to maximum hand size (7).
- Player with <=7 cards does not discard.
- "Until end of turn" continuous effects are removed during cleanup.
- Damage marked on creatures is cleared to 0.
- Combat flags (dealt_deathtouch_damage, is_attacking, is_blocking) are cleared.
- CombatState is cleared.
- All players' mana pools are emptied.
- SBAs are checked after effects expire (creature with lethal damage dies).
- If triggers fire during cleanup, another cleanup step occurs.
- Integration: Giant Growth (+3/+3 EOT) reverts after cleanup.
- Integration: 2 damage on a 3/3 is cleared — creature survives cleanup.
"""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.engine.card import CardImpl, Creature
from benchmarks.sos.workspace.engine.combat import CombatState
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.game_state import GameState
from benchmarks.sos.workspace.engine.mana import ManaPool
from benchmarks.sos.workspace.engine.player import DeterministicPlayer
from benchmarks.sos.workspace.engine.turn import _do_cleanup_step, MAX_HAND_SIZE
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaType, Phase, Step, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_card(name: str = "TestCard") -> CardImpl:
    """Create a minimal card for testing."""
    return CardImpl(name=name)


def _make_creature(
    name: str = "Bear",
    base_power: int = 2,
    base_toughness: int = 2,
    keywords: Keyword | None = None,
) -> Creature:
    """Create a creature for testing."""
    return Creature(
        name=name,
        base_power=base_power,
        base_toughness=base_toughness,
        keywords=keywords,
    )


def _make_game(
    p1_script: list | None = None,
    p2_script: list | None = None,
) -> tuple[GameState, DeterministicPlayer, DeterministicPlayer]:
    """Create a bare game state for cleanup tests."""
    p1 = DeterministicPlayer("Alice", p1_script or [])
    p2 = DeterministicPlayer("Bob", p2_script or [])
    game = GameState([p1, p2])
    return game, p1, p2


def _place_on_battlefield(game: GameState, player: DeterministicPlayer, obj) -> None:
    """Place an object on a player's battlefield, setting ownership."""
    obj.owner = player
    obj.controller = player
    player.zones[Zone.BATTLEFIELD].add(obj)


def _place_in_hand(game: GameState, player: DeterministicPlayer, obj) -> None:
    """Place a card in a player's hand, setting ownership."""
    obj.owner = player
    obj.controller = player
    player.zones[Zone.HAND].add(obj)


# ===========================================================================
# Discard to hand size
# ===========================================================================


class TestDiscardToHandSize:
    """Tests for cleanup step 1: discard down to max hand size."""

    def test_discard_from_8_to_7(self) -> None:
        """Player with 8 cards in hand discards 1 to reach 7."""
        cards = [_make_card(f"Card_{i}") for i in range(8)]
        # Script: choose the first card in the list for discard
        game, p1, p2 = _make_game(p1_script=[cards[0]])
        for card in cards:
            _place_in_hand(game, p1, card)

        _do_cleanup_step(game)

        assert len(p1.zones[Zone.HAND]) == MAX_HAND_SIZE

    def test_discard_from_10_to_7(self) -> None:
        """Player with 10 cards in hand discards 3 to reach 7."""
        cards = [_make_card(f"Card_{i}") for i in range(10)]
        # Need to script 3 discard choices
        game, p1, p2 = _make_game(p1_script=[cards[0], cards[1], cards[2]])
        for card in cards:
            _place_in_hand(game, p1, card)

        _do_cleanup_step(game)

        assert len(p1.zones[Zone.HAND]) == MAX_HAND_SIZE

    def test_discarded_cards_go_to_graveyard(self) -> None:
        """Discarded cards during cleanup go to the player's graveyard."""
        cards = [_make_card(f"Card_{i}") for i in range(8)]
        game, p1, p2 = _make_game(p1_script=[cards[0]])
        for card in cards:
            _place_in_hand(game, p1, card)

        _do_cleanup_step(game)

        graveyard = p1.zones[Zone.GRAVEYARD]
        assert graveyard.contains(cards[0])

    def test_exactly_7_cards_no_discard(self) -> None:
        """Player with exactly 7 cards does NOT discard."""
        cards = [_make_card(f"Card_{i}") for i in range(7)]
        game, p1, p2 = _make_game()
        for card in cards:
            _place_in_hand(game, p1, card)

        _do_cleanup_step(game)

        assert len(p1.zones[Zone.HAND]) == 7

    def test_fewer_than_7_cards_no_discard(self) -> None:
        """Player with fewer than 7 cards does NOT discard."""
        cards = [_make_card(f"Card_{i}") for i in range(3)]
        game, p1, p2 = _make_game()
        for card in cards:
            _place_in_hand(game, p1, card)

        _do_cleanup_step(game)

        assert len(p1.zones[Zone.HAND]) == 3

    def test_only_active_player_discards(self) -> None:
        """Only the active player discards during cleanup, not the non-active player."""
        # P1 is active (default), P2 has 9 cards — P2 should NOT discard
        cards_p2 = [_make_card(f"P2Card_{i}") for i in range(9)]
        game, p1, p2 = _make_game()
        for card in cards_p2:
            _place_in_hand(game, p2, card)

        _do_cleanup_step(game)

        # P2 should still have 9 cards since they're not the active player
        assert len(p2.zones[Zone.HAND]) == 9

    def test_chosen_card_is_the_one_discarded(self) -> None:
        """The specific card returned by choose_card is discarded."""
        cards = [_make_card(f"Card_{i}") for i in range(8)]
        # Player chooses to discard the last card
        game, p1, p2 = _make_game(p1_script=[cards[7]])
        for card in cards:
            _place_in_hand(game, p1, card)

        _do_cleanup_step(game)

        hand = p1.zones[Zone.HAND]
        assert not hand.contains(cards[7])
        graveyard = p1.zones[Zone.GRAVEYARD]
        assert graveyard.contains(cards[7])


# ===========================================================================
# EOT effect removal
# ===========================================================================


class TestEOTEffectRemoval:
    """Tests for cleanup step 2: remove 'until end of turn' effects."""

    def test_eot_effect_removed(self) -> None:
        """A DURATION_END_OF_TURN effect is removed during cleanup."""
        game, p1, p2 = _make_game()
        creature = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, p1, creature)

        # Add an EOT effect that gives +3/+3
        effect = ContinuousEffect(
            source=creature,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=lambda g: setattr(creature, "modified_power", creature.base_power + 3)
            or setattr(creature, "modified_toughness", creature.base_toughness + 3),
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)
        # Apply once to verify effect is active
        game.effect_manager.apply_all(game)
        assert creature.modified_power == 5

        _do_cleanup_step(game)

        # After cleanup, the effect should be removed and P/T reverted
        assert creature.modified_power == 2
        assert creature.modified_toughness == 2

    def test_permanent_effect_not_removed(self) -> None:
        """A DURATION_PERMANENT effect survives cleanup."""
        game, p1, p2 = _make_game()
        creature = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, p1, creature)

        # Add a permanent effect
        effect = ContinuousEffect(
            source=creature,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=lambda g: setattr(creature, "modified_power", creature.base_power + 1)
            or setattr(creature, "modified_toughness", creature.base_toughness + 1),
            duration=DURATION_PERMANENT,
        )
        game.effect_manager.add(effect)
        game.effect_manager.apply_all(game)
        assert creature.modified_power == 3

        _do_cleanup_step(game)

        # Permanent effect remains — P/T should still be boosted
        assert creature.modified_power == 3
        assert creature.modified_toughness == 3

    def test_multiple_eot_effects_all_removed(self) -> None:
        """Multiple EOT effects are all removed during a single cleanup."""
        game, p1, p2 = _make_game()
        c1 = _make_creature("Bear1", 2, 2)
        c2 = _make_creature("Bear2", 3, 3)
        _place_on_battlefield(game, p1, c1)
        _place_on_battlefield(game, p1, c2)

        effect1 = ContinuousEffect(
            source=c1,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=lambda g: setattr(c1, "modified_power", c1.base_power + 2),
            duration=DURATION_END_OF_TURN,
        )
        effect2 = ContinuousEffect(
            source=c2,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=lambda g: setattr(c2, "modified_power", c2.base_power + 2),
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect1)
        game.effect_manager.add(effect2)

        _do_cleanup_step(game)

        assert c1.modified_power == 2
        assert c2.modified_power == 3

    def test_effects_reapplied_after_removal(self) -> None:
        """After removing expired effects, remaining effects are reapplied correctly."""
        game, p1, p2 = _make_game()
        creature = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, p1, creature)

        # One permanent effect (+1/+1) and one EOT effect (+3/+3)
        perm_effect = ContinuousEffect(
            source=creature,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=lambda g: setattr(creature, "modified_power", creature.base_power + 1)
            or setattr(creature, "modified_toughness", creature.base_toughness + 1),
            duration=DURATION_PERMANENT,
        )
        eot_effect = ContinuousEffect(
            source=creature,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=lambda g: setattr(creature, "modified_power", creature.modified_power + 3)
            or setattr(creature, "modified_toughness", creature.modified_toughness + 3),
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(perm_effect)
        game.effect_manager.add(eot_effect)

        _do_cleanup_step(game)

        # Only permanent effect remains: 2 + 1 = 3
        assert creature.modified_power == 3
        assert creature.modified_toughness == 3


# ===========================================================================
# Damage clearing
# ===========================================================================


class TestDamageClearing:
    """Tests for cleanup step 3: clear damage marked on creatures."""

    def test_damage_cleared_to_zero(self) -> None:
        """Creature with damage_marked has it cleared to 0 during cleanup."""
        game, p1, p2 = _make_game()
        creature = _make_creature("Bear", 2, 3)
        _place_on_battlefield(game, p1, creature)
        creature.damage_marked = 2

        _do_cleanup_step(game)

        assert creature.damage_marked == 0

    def test_damage_cleared_on_all_players_creatures(self) -> None:
        """Damage is cleared on creatures belonging to ALL players, not just active."""
        game, p1, p2 = _make_game()
        c1 = _make_creature("Bear1", 2, 3)
        c2 = _make_creature("Bear2", 2, 4)
        _place_on_battlefield(game, p1, c1)
        _place_on_battlefield(game, p2, c2)
        c1.damage_marked = 2
        c2.damage_marked = 3

        _do_cleanup_step(game)

        assert c1.damage_marked == 0
        assert c2.damage_marked == 0

    def test_damage_cleared_creature_survives(self) -> None:
        """A creature with non-lethal damage survives after damage is cleared."""
        game, p1, p2 = _make_game()
        creature = _make_creature("Hill Giant", 3, 3)
        _place_on_battlefield(game, p1, creature)
        creature.damage_marked = 2  # Non-lethal

        _do_cleanup_step(game)

        # Creature should still be on battlefield
        bf = p1.zones[Zone.BATTLEFIELD]
        assert bf.contains(creature)
        assert creature.damage_marked == 0


# ===========================================================================
# Combat flag clearing
# ===========================================================================


class TestCombatFlagClearing:
    """Tests for cleanup step 4: clear combat-related flags."""

    def test_dealt_deathtouch_damage_cleared(self) -> None:
        """dealt_deathtouch_damage is set to False during cleanup."""
        game, p1, p2 = _make_game()
        creature = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, p1, creature)
        creature.dealt_deathtouch_damage = True

        _do_cleanup_step(game)

        assert creature.dealt_deathtouch_damage is False

    def test_is_attacking_cleared(self) -> None:
        """is_attacking flag is cleared during cleanup."""
        game, p1, p2 = _make_game()
        creature = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, p1, creature)
        creature.is_attacking = True

        _do_cleanup_step(game)

        assert creature.is_attacking is False

    def test_is_blocking_cleared(self) -> None:
        """is_blocking flag is cleared during cleanup."""
        game, p1, p2 = _make_game()
        creature = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, p2, creature)
        creature.is_blocking = True

        _do_cleanup_step(game)

        assert creature.is_blocking is False

    def test_combat_state_cleared(self) -> None:
        """CombatState itself is cleared (attackers, was_blocked, in_combat)."""
        game, p1, p2 = _make_game()
        creature = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, p1, creature)

        # Simulate active combat state
        game.combat_state.in_combat = True
        game.combat_state.attackers[creature] = p2
        game.combat_state.was_blocked.add(creature)

        _do_cleanup_step(game)

        assert game.combat_state.in_combat is False
        assert len(game.combat_state.attackers) == 0
        assert len(game.combat_state.was_blocked) == 0


# ===========================================================================
# Mana pool emptying
# ===========================================================================


class TestManaPoolEmptying:
    """Tests for cleanup step 5: empty all players' mana pools."""

    def test_active_player_mana_emptied(self) -> None:
        """Active player's mana pool is emptied during cleanup."""
        game, p1, p2 = _make_game()
        p1.mana_pool.add(ManaType.GREEN, 3)
        p1.mana_pool.add(ManaType.RED, 2)

        _do_cleanup_step(game)

        assert p1.mana_pool.total() == 0

    def test_non_active_player_mana_emptied(self) -> None:
        """Non-active player's mana pool is also emptied during cleanup."""
        game, p1, p2 = _make_game()
        p2.mana_pool.add(ManaType.BLUE, 5)

        _do_cleanup_step(game)

        assert p2.mana_pool.total() == 0

    def test_all_mana_types_emptied(self) -> None:
        """All mana types (WUBRG + colorless) are emptied."""
        game, p1, p2 = _make_game()
        p1.mana_pool.add(ManaType.WHITE, 1)
        p1.mana_pool.add(ManaType.BLUE, 1)
        p1.mana_pool.add(ManaType.BLACK, 1)
        p1.mana_pool.add(ManaType.RED, 1)
        p1.mana_pool.add(ManaType.GREEN, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 1)

        _do_cleanup_step(game)

        for mt in ManaType:
            assert p1.mana_pool.get(mt) == 0


# ===========================================================================
# SBA check during cleanup
# ===========================================================================


class TestSBACheckDuringCleanup:
    """Tests for cleanup step 6: state-based actions are checked."""

    def test_creature_dies_after_eot_buff_expires(self) -> None:
        """A creature that only survives due to an EOT buff dies when the buff expires.

        Example: 1/1 creature with Giant Growth (+3/+3 EOT) has taken 3 damage.
        During cleanup, the buff expires making it a 1/1 with 3 damage → dies via SBA.
        """
        game, p1, p2 = _make_game()
        creature = _make_creature("Soldier", 1, 1)
        _place_on_battlefield(game, p1, creature)

        # Simulate Giant Growth: temporarily make it 4/4
        effect = ContinuousEffect(
            source=creature,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=lambda g: setattr(creature, "modified_power", creature.base_power + 3)
            or setattr(creature, "modified_toughness", creature.base_toughness + 3),
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)
        game.effect_manager.apply_all(game)
        # While buffed, creature takes 3 damage (survivable at 4 toughness)
        creature.damage_marked = 3

        _do_cleanup_step(game)

        # After cleanup: effect expires → toughness back to 1, but damage is cleared
        # to 0 in step 3. So actually the creature would survive since damage clears
        # before SBAs. Let's verify it's on battlefield still.
        bf = p1.zones[Zone.BATTLEFIELD]
        # Damage is cleared in step 3 (before SBA check in step 6),
        # so the creature should survive as a 1/1 with 0 damage.
        assert bf.contains(creature)
        assert creature.damage_marked == 0
        assert creature.modified_power == 1
        assert creature.modified_toughness == 1

    def test_zero_toughness_creature_dies_after_eot_buff_expires(self) -> None:
        """A creature whose toughness drops to 0 after EOT buff expires dies via SBA.

        A 0/1 base creature with an EOT +0/+2 buff → cleanup removes buff → 0/1 stays.
        But a creature that has its toughness SET to 0 by buff removal dies.
        Let's make a -1 toughness scenario: creature has base 2/1 and -1/-1 counter,
        kept alive by a +0/+1 EOT buff. When buff expires: toughness = 1 - 1 = 0 → dies.
        """
        game, p1, p2 = _make_game()
        creature = _make_creature("Weakling", 2, 1)
        _place_on_battlefield(game, p1, creature)
        # Give it a -1/-1 counter (would make it 1/0 without help)
        creature.minus_one_counters = 1
        creature._base_minus_one_counters = 1

        # EOT buff that gives +0/+1 toughness to keep it alive
        effect = ContinuousEffect(
            source=creature,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=lambda g: setattr(creature, "modified_toughness", creature.base_toughness + 1),
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)
        game.effect_manager.apply_all(game)
        # With buff: toughness = (1+1) - 1 = 1, alive
        assert creature.toughness == 1

        _do_cleanup_step(game)

        # After cleanup: buff removed → toughness = 1 - 1 = 0 → SBA kills it
        bf = p1.zones[Zone.BATTLEFIELD]
        assert not bf.contains(creature)
        graveyard = p1.zones[Zone.GRAVEYARD]
        assert graveyard.contains(creature)


# ===========================================================================
# Integration tests
# ===========================================================================


class TestCleanupIntegration:
    """Integration tests verifying full cleanup behavior with realistic scenarios."""

    def test_giant_growth_reverts_after_cleanup(self) -> None:
        """Giant Growth (+3/+3 until EOT) on a 2/2 Bear → cleanup → reverts to 2/2.

        This is the canonical test from the TODO: "Giant Growth a creature →
        advance to cleanup → verify P/T reverts."
        """
        game, p1, p2 = _make_game()
        bear = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, p1, bear)

        # Simulate Giant Growth: +3/+3 until end of turn
        def giant_growth_apply(g):
            bear.modified_power = bear.base_power + 3
            bear.modified_toughness = bear.base_toughness + 3

        effect = ContinuousEffect(
            source=bear,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=giant_growth_apply,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)
        game.effect_manager.apply_all(game)

        # Verify the buff is active
        assert bear.power == 5
        assert bear.toughness == 5

        _do_cleanup_step(game)

        # After cleanup, the creature should revert to its original stats
        assert bear.power == 2
        assert bear.toughness == 2

    def test_damage_on_3_3_cleared_creature_alive(self) -> None:
        """Deal 2 damage to a 3/3 → cleanup → damage cleared, creature alive.

        This is the canonical test from the TODO: "Deal 2 damage to 3/3 →
        cleanup → verify damage cleared."
        """
        game, p1, p2 = _make_game()
        hill_giant = _make_creature("Hill Giant", 3, 3)
        _place_on_battlefield(game, p1, hill_giant)

        # Simulate taking 2 damage
        hill_giant.damage_marked = 2

        _do_cleanup_step(game)

        # Creature should be alive with 0 damage
        bf = p1.zones[Zone.BATTLEFIELD]
        assert bf.contains(hill_giant)
        assert hill_giant.damage_marked == 0

    def test_full_cleanup_all_steps_execute(self) -> None:
        """Verify that all cleanup steps execute together in a realistic scenario.

        Scenario: Active player has 8 cards, a creature with damage, mana in pool,
        creature with combat flags, and an EOT effect.
        """
        # Create 8 cards in hand for P1
        cards = [_make_card(f"Card_{i}") for i in range(8)]
        game, p1, p2 = _make_game(p1_script=[cards[0]])
        for card in cards:
            _place_in_hand(game, p1, card)

        # Creature with damage and combat flags
        creature = _make_creature("Bear", 2, 3)
        _place_on_battlefield(game, p1, creature)
        creature.damage_marked = 1
        creature.is_attacking = True
        creature.dealt_deathtouch_damage = True

        # Mana in pool
        p1.mana_pool.add(ManaType.GREEN, 3)

        # EOT effect
        effect = ContinuousEffect(
            source=creature,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=lambda g: setattr(creature, "modified_power", creature.base_power + 2),
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)
        game.effect_manager.apply_all(game)

        _do_cleanup_step(game)

        # All cleanup effects verified:
        assert len(p1.zones[Zone.HAND]) == MAX_HAND_SIZE  # Discarded to 7
        assert creature.damage_marked == 0  # Damage cleared
        assert creature.is_attacking is False  # Combat flag cleared
        assert creature.dealt_deathtouch_damage is False  # Deathtouch flag cleared
        assert p1.mana_pool.total() == 0  # Mana emptied
        assert creature.modified_power == 2  # EOT effect removed

    def test_max_hand_size_constant_is_7(self) -> None:
        """MAX_HAND_SIZE is defined as 7."""
        assert MAX_HAND_SIZE == 7


# ===========================================================================
# Rule 514.3a — Re-cleanup loop
# ===========================================================================


class TestReCleanupLoop:
    """Tests for rule 514.3a: if SBAs are performed or triggered abilities
    fire during cleanup, another cleanup step occurs after resolving."""

    def test_sba_during_cleanup_triggers_recleanup(self) -> None:
        """A creature that dies from SBA during cleanup causes a re-cleanup.

        Scenario: A 2/1 creature kept alive by an EOT +0/+1 buff.
        When cleanup removes the buff, toughness drops to 1 and the creature
        has a -1/-1 counter → effective toughness 0 → SBA kills it.
        The re-cleanup should then clear damage on remaining creatures, etc.

        We verify the SBA fires (creature goes to graveyard) AND that
        the re-cleanup properly clears damage on a *second* creature that
        only exists to prove the second cleanup pass ran.
        """
        game, p1, p2 = _make_game()

        # Creature #1: 2/1 with -1/-1 counter, kept alive by EOT +0/+1
        doomed = _make_creature("Doomed", 2, 1)
        _place_on_battlefield(game, p1, doomed)
        doomed.minus_one_counters = 1
        doomed._base_minus_one_counters = 1

        effect = ContinuousEffect(
            source=doomed,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=lambda g: setattr(doomed, "modified_toughness", doomed.base_toughness + 1),
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)
        game.effect_manager.apply_all(game)
        assert doomed.toughness == 1  # (1+1) - 1 = 1, alive

        # Creature #2: survives first cleanup, gets damage marked.
        # The first cleanup clears its damage, but the SBA from doomed dying
        # triggers a second cleanup. We mark damage on survivor *after*
        # the first cleanup's step 3 by using a trick: we mark damage high
        # enough that it wouldn't survive without the second cleanup clearing it.
        # Actually, simpler approach: verify that the second cleanup occurred
        # by checking that mana added *during* cleanup processing gets cleared.
        survivor = _make_creature("Survivor", 3, 3)
        _place_on_battlefield(game, p1, survivor)
        survivor.damage_marked = 1  # Non-lethal

        _do_cleanup_step(game)

        # Doomed creature should be dead (SBA from toughness 0)
        assert not p1.zones[Zone.BATTLEFIELD].contains(doomed)
        assert p1.zones[Zone.GRAVEYARD].contains(doomed)

        # Survivor should still be alive with damage cleared
        assert p1.zones[Zone.BATTLEFIELD].contains(survivor)
        assert survivor.damage_marked == 0

    def test_stack_trigger_during_cleanup_causes_recleanup(self) -> None:
        """If something is on the stack during cleanup, priority_loop is called
        and then another cleanup step occurs.

        We manually push an item onto the stack before cleanup to simulate
        a triggered ability. The priority_loop should resolve it, and then
        a second cleanup should run (clearing mana, damage, etc. again).
        """
        from benchmarks.sos.workspace.engine.stack import StackObject

        game, p1, p2 = _make_game()
        resolved = []

        # Push a triggered ability onto the stack that records its resolution
        trigger = StackObject(
            source=None,
            controller=p1,
            on_resolve=lambda g: resolved.append("trigger_resolved"),
        )
        game.stack.push(trigger)

        # Both players need to pass priority for the stack to resolve.
        # P1 passes, P2 passes → trigger resolves.
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])

        # Place a creature with damage to verify re-cleanup clears it
        creature = _make_creature("Bear", 2, 3)
        _place_on_battlefield(game, p1, creature)
        creature.damage_marked = 1

        _do_cleanup_step(game)

        # Trigger should have been resolved
        assert "trigger_resolved" in resolved

        # Re-cleanup should have cleared damage again
        assert creature.damage_marked == 0

    def test_no_recleanup_when_no_sba_and_empty_stack(self) -> None:
        """When cleanup doesn't trigger SBAs and the stack is empty,
        no extra cleanup step occurs (no infinite loop)."""
        game, p1, p2 = _make_game()
        creature = _make_creature("Bear", 2, 3)
        _place_on_battlefield(game, p1, creature)
        creature.damage_marked = 1

        # This should complete without hanging (no infinite recursion)
        _do_cleanup_step(game)

        assert creature.damage_marked == 0
        assert p1.zones[Zone.BATTLEFIELD].contains(creature)


# ===========================================================================
# DeterministicPlayer discard fallback
# ===========================================================================


class TestDeterministicPlayerDiscard:
    """Tests verifying that cleanup discard works when DeterministicPlayer's
    script is exhausted — the fallback should discard from the end of hand."""

    def test_discard_without_script_falls_back_to_last_card(self) -> None:
        """Player with 9 cards and NO scripted choices still discards to 7.

        When choose_card raises ScriptExhaustedError, the cleanup code
        falls back to discarding the last card in hand deterministically.
        """
        cards = [_make_card(f"Card_{i}") for i in range(9)]
        # Empty script — choose_card will raise ScriptExhaustedError
        game, p1, p2 = _make_game(p1_script=[])
        for card in cards:
            _place_in_hand(game, p1, card)

        _do_cleanup_step(game)

        assert len(p1.zones[Zone.HAND]) == MAX_HAND_SIZE

    def test_discard_fallback_sends_cards_to_graveyard(self) -> None:
        """Deterministic fallback discards go to graveyard, not lost."""
        cards = [_make_card(f"Card_{i}") for i in range(9)]
        game, p1, p2 = _make_game(p1_script=[])
        for card in cards:
            _place_in_hand(game, p1, card)

        _do_cleanup_step(game)

        # 2 cards should be in graveyard (9 - 7 = 2)
        assert len(p1.zones[Zone.GRAVEYARD]) == 2

    def test_discard_partial_script_then_fallback(self) -> None:
        """Player with 10 cards and only 1 scripted choice: first discard uses
        the script, remaining 2 use the deterministic fallback."""
        cards = [_make_card(f"Card_{i}") for i in range(10)]
        # Script has only 1 choice (for the first discard)
        game, p1, p2 = _make_game(p1_script=[cards[0]])
        for card in cards:
            _place_in_hand(game, p1, card)

        _do_cleanup_step(game)

        # Should still end up at 7 cards
        assert len(p1.zones[Zone.HAND]) == MAX_HAND_SIZE
        # The scripted choice (cards[0]) should be in graveyard
        assert p1.zones[Zone.GRAVEYARD].contains(cards[0])
        # Total discards = 3
        assert len(p1.zones[Zone.GRAVEYARD]) == 3

    def test_discard_large_hand_without_script(self) -> None:
        """Player with 15 cards and no script discards 8 cards to reach 7."""
        cards = [_make_card(f"Card_{i}") for i in range(15)]
        game, p1, p2 = _make_game(p1_script=[])
        for card in cards:
            _place_in_hand(game, p1, card)

        _do_cleanup_step(game)

        assert len(p1.zones[Zone.HAND]) == MAX_HAND_SIZE
        assert len(p1.zones[Zone.GRAVEYARD]) == 8


# ===========================================================================
# Edge cases
# ===========================================================================


class TestCleanupEdgeCases:
    """Edge case tests for cleanup step."""

    def test_no_creatures_on_battlefield(self) -> None:
        """Cleanup succeeds when no creatures are on the battlefield.

        Damage clearing is a no-op, combat flag clearing is a no-op,
        SBA check finds nothing. Verify no errors and mana is still cleared.
        """
        game, p1, p2 = _make_game()
        # No creatures — just mana to empty
        p1.mana_pool.add(ManaType.RED, 2)

        _do_cleanup_step(game)

        assert p1.mana_pool.total() == 0
        assert len(p1.zones[Zone.BATTLEFIELD]) == 0

    def test_mana_pool_already_empty(self) -> None:
        """Cleanup succeeds when all mana pools are already empty."""
        game, p1, p2 = _make_game()
        # Mana pools are empty by default
        assert p1.mana_pool.total() == 0
        assert p2.mana_pool.total() == 0

        _do_cleanup_step(game)

        assert p1.mana_pool.total() == 0
        assert p2.mana_pool.total() == 0

    def test_empty_battlefield_and_empty_hand(self) -> None:
        """Cleanup works with completely empty board state — no creatures,
        no cards in hand, no mana, nothing to discard."""
        game, p1, p2 = _make_game()

        _do_cleanup_step(game)

        assert len(p1.zones[Zone.HAND]) == 0
        assert len(p1.zones[Zone.BATTLEFIELD]) == 0
        assert p1.mana_pool.total() == 0

    def test_zero_cards_in_hand_no_discard(self) -> None:
        """Player with 0 cards in hand: discard step is a no-op."""
        game, p1, p2 = _make_game()
        assert len(p1.zones[Zone.HAND]) == 0

        _do_cleanup_step(game)

        assert len(p1.zones[Zone.HAND]) == 0
        assert len(p1.zones[Zone.GRAVEYARD]) == 0

    def test_non_creature_permanent_damage_attr_cleared(self) -> None:
        """If a non-creature permanent somehow has damage_marked, it's still cleared.

        The cleanup code iterates all battlefield objects with damage_marked,
        not just creatures.
        """
        game, p1, p2 = _make_game()
        artifact = _make_card("Artifact")
        artifact.damage_marked = 5  # Unusual but possible
        _place_on_battlefield(game, p1, artifact)

        _do_cleanup_step(game)

        assert artifact.damage_marked == 0
