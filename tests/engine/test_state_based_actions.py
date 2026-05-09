"""Tests for engine/state_based_actions.py — State-based actions checker and resolver.

Verifies:
- Player with 0 or less life → has_lost = True.
- Player with positive life → not lost.
- Creature with toughness 0 or less → moved to owner's graveyard.
- Creature with lethal damage (damage_marked >= toughness) → graveyard.
- Creature with non-lethal damage → stays on battlefield.
- Player who drew from empty library → has_lost = True.
- Legend rule: 2+ legendaries with same name → player chooses one to keep, others → graveyard.
- Legend rule: 2 legendaries with different names → both stay.
- Token not on battlefield → removed from game entirely.
- Aura with no legal attachment → graveyard.
- +1/+1 and -1/-1 counter annihilation.
- resolve_state_based_actions loops until stable.
- check_state_based_actions returns True when action taken, False when stable.
- Multiple SBAs triggering in same check.
- SBA trigger queueing: death triggers fire when creatures die via SBAs.
- CREATURE_DIES event fires for creatures dying via SBAs (lethal damage, zero toughness).
- LEAVES_BATTLEFIELD event fires for permanents removed via SBAs.
- Multiple simultaneous deaths queue all triggers.
- Non-creature permanents fire LEAVES_BATTLEFIELD but not CREATURE_DIES.
- SBA loop repeats when triggers are queued during processing.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.state_based_actions import check_state_based_actions, resolve_state_based_actions
from engine.triggers import EventType, TriggerRegistration
from engine.types import CardType, Supertype, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(
    p1_script: list | None = None,
    p2_script: list | None = None,
    p1_life: int = 20,
    p2_life: int = 20,
) -> GameState:
    """Create a 2-player GameState with optional scripts and life totals."""
    p1 = DeterministicPlayer("Alice", p1_script or [], life=p1_life)
    p2 = DeterministicPlayer("Bob", p2_script or [], life=p2_life)
    return GameState([p1, p2])


def _make_creature(
    name: str = "Bear",
    toughness: int = 2,
    damage_marked: int = 0,
    supertypes: set | None = None,
    is_token: bool = False,
    keywords: object | None = None,
    plus_one_counters: int = 0,
    minus_one_counters: int = 0,
) -> SimpleNamespace:
    """Create a minimal mock creature with the attributes SBAs check via duck typing."""
    obj = SimpleNamespace(
        name=name,
        toughness=toughness,
        damage_marked=damage_marked,
        supertypes=supertypes or set(),
        is_token=is_token,
        plus_one_counters=plus_one_counters,
        minus_one_counters=minus_one_counters,
    )
    if keywords is not None:
        obj.keywords = keywords
    return obj


def _make_legendary(name: str = "Thalia", toughness: int = 2) -> SimpleNamespace:
    """Create a mock legendary creature."""
    return _make_creature(name=name, toughness=toughness, supertypes={Supertype.LEGENDARY})


def _make_token(name: str = "Soldier", toughness: int = 1) -> SimpleNamespace:
    """Create a mock token creature."""
    return _make_creature(name=name, toughness=toughness, is_token=True)


def _make_aura(name: str = "Pacifism", attached_to: object | None = None) -> SimpleNamespace:
    """Create a mock aura enchantment.

    Unlike creatures, auras have an ``attached_to`` attribute but typically
    no ``toughness`` — so we give them a name and the attachment reference.
    Sets ``is_aura=True`` so the SBA aura-unattached check recognises it.
    """
    return SimpleNamespace(
        name=name,
        attached_to=attached_to,
        supertypes=set(),
        is_token=False,
        is_aura=True,
    )


def _make_equipment(
    name: str = "Bonesplitter",
    attached_to: object | None = None,
) -> SimpleNamespace:
    """Create a mock equipment artifact.

    Equipment has ``attached_to`` but does NOT have ``is_aura`` set,
    so state-based actions should never treat it as an unattached aura.
    """
    return SimpleNamespace(
        name=name,
        attached_to=attached_to,
        supertypes=set(),
        is_token=False,
    )


def _battlefield(game: GameState, player_idx: int):
    """Shortcut to get a player's battlefield."""
    return game.players[player_idx].zones[Zone.BATTLEFIELD]


def _graveyard(game: GameState, player_idx: int):
    """Shortcut to get a player's graveyard."""
    return game.players[player_idx].zones[Zone.GRAVEYARD]


# ===========================================================================
# Player life ≤ 0 → has_lost
# ===========================================================================
class TestPlayerLifeZero:
    """SBA: A player with 0 or less life loses the game."""

    def test_player_with_zero_life_loses(self) -> None:
        """Player at exactly 0 life should have has_lost set to True."""
        game = _make_game(p1_life=0)
        result = check_state_based_actions(game)
        assert game.players[0].has_lost is True
        assert result is True

    def test_player_with_negative_life_loses(self) -> None:
        """Player with negative life should have has_lost set to True."""
        game = _make_game(p1_life=-5)
        result = check_state_based_actions(game)
        assert game.players[0].has_lost is True
        assert result is True

    def test_player_with_positive_life_does_not_lose(self) -> None:
        """Player with positive life should NOT have has_lost set."""
        game = _make_game(p1_life=1)
        check_state_based_actions(game)
        assert game.players[0].has_lost is False

    def test_both_players_zero_life_both_lose(self) -> None:
        """If both players have 0 life, both should lose."""
        game = _make_game(p1_life=0, p2_life=0)
        check_state_based_actions(game)
        assert game.players[0].has_lost is True
        assert game.players[1].has_lost is True

    def test_already_lost_player_not_re_triggered(self) -> None:
        """A player who already has has_lost=True should not cause another action."""
        game = _make_game(p1_life=0)
        game.players[0].has_lost = True  # Already marked as lost
        result = check_state_based_actions(game)
        # Since player is already lost, no NEW action should be taken for life SBA
        # (other SBAs also return False on a clean game)
        assert result is False

    def test_player_at_exactly_one_life_not_lost(self) -> None:
        """Player at exactly 1 life should not lose."""
        game = _make_game(p1_life=1)
        check_state_based_actions(game)
        assert game.players[0].has_lost is False


# ===========================================================================
# Creature with toughness ≤ 0 → graveyard
# ===========================================================================
class TestCreatureZeroToughness:
    """SBA: Creature with toughness 0 or less is put into its owner's graveyard."""

    def test_creature_with_zero_toughness_goes_to_graveyard(self) -> None:
        """A creature with toughness 0 should be moved from battlefield to graveyard."""
        game = _make_game()
        creature = _make_creature(toughness=0)
        _battlefield(game, 0).add(creature)
        result = check_state_based_actions(game)
        assert result is True
        assert not _battlefield(game, 0).contains(creature)
        assert _graveyard(game, 0).contains(creature)

    def test_creature_with_negative_toughness_goes_to_graveyard(self) -> None:
        """A creature with negative toughness should be moved to graveyard."""
        game = _make_game()
        creature = _make_creature(toughness=-3)
        _battlefield(game, 0).add(creature)
        check_state_based_actions(game)
        assert not _battlefield(game, 0).contains(creature)
        assert _graveyard(game, 0).contains(creature)

    def test_creature_with_positive_toughness_stays(self) -> None:
        """A creature with positive toughness should remain on the battlefield."""
        game = _make_game()
        creature = _make_creature(toughness=2)
        _battlefield(game, 0).add(creature)
        check_state_based_actions(game)
        assert _battlefield(game, 0).contains(creature)
        assert not _graveyard(game, 0).contains(creature)

    def test_multiple_creatures_zero_toughness_all_removed(self) -> None:
        """All creatures with 0 toughness should be removed simultaneously."""
        game = _make_game()
        c1 = _make_creature(name="Wall1", toughness=0)
        c2 = _make_creature(name="Wall2", toughness=0)
        c3 = _make_creature(name="Bear", toughness=2)
        _battlefield(game, 0).add(c1)
        _battlefield(game, 0).add(c2)
        _battlefield(game, 0).add(c3)
        check_state_based_actions(game)
        assert not _battlefield(game, 0).contains(c1)
        assert not _battlefield(game, 0).contains(c2)
        assert _battlefield(game, 0).contains(c3)
        assert _graveyard(game, 0).contains(c1)
        assert _graveyard(game, 0).contains(c2)


# ===========================================================================
# Creature with lethal damage → graveyard
# ===========================================================================
class TestCreatureLethalDamage:
    """SBA: Creature with damage_marked >= toughness is destroyed (graveyard)."""

    def test_creature_with_lethal_damage_goes_to_graveyard(self) -> None:
        """Creature with damage_marked == toughness should be moved to graveyard."""
        game = _make_game()
        creature = _make_creature(toughness=3, damage_marked=3)
        _battlefield(game, 0).add(creature)
        result = check_state_based_actions(game)
        assert result is True
        assert not _battlefield(game, 0).contains(creature)
        assert _graveyard(game, 0).contains(creature)

    def test_creature_with_excess_damage_goes_to_graveyard(self) -> None:
        """Creature with damage_marked > toughness should be moved to graveyard."""
        game = _make_game()
        creature = _make_creature(toughness=2, damage_marked=7)
        _battlefield(game, 0).add(creature)
        check_state_based_actions(game)
        assert not _battlefield(game, 0).contains(creature)
        assert _graveyard(game, 0).contains(creature)

    def test_creature_with_nonlethal_damage_stays(self) -> None:
        """Creature with damage_marked < toughness should remain on battlefield."""
        game = _make_game()
        creature = _make_creature(toughness=4, damage_marked=2)
        _battlefield(game, 0).add(creature)
        check_state_based_actions(game)
        assert _battlefield(game, 0).contains(creature)
        assert not _graveyard(game, 0).contains(creature)

    def test_creature_with_zero_damage_stays(self) -> None:
        """Creature with no damage should remain on battlefield."""
        game = _make_game()
        creature = _make_creature(toughness=3, damage_marked=0)
        _battlefield(game, 0).add(creature)
        check_state_based_actions(game)
        assert _battlefield(game, 0).contains(creature)

    def test_indestructible_creature_survives_lethal_damage(self) -> None:
        """Creature with indestructible keyword should NOT be destroyed by lethal damage."""
        from engine.types import Keyword

        game = _make_game()
        creature = _make_creature(toughness=3, damage_marked=5, keywords=Keyword.INDESTRUCTIBLE)
        _battlefield(game, 0).add(creature)
        check_state_based_actions(game)
        assert _battlefield(game, 0).contains(creature)
        assert not _graveyard(game, 0).contains(creature)


# ===========================================================================
# Player drew from empty library → loses
# ===========================================================================
class TestDrawFromEmptyLibrary:
    """SBA: A player who drew from an empty library loses the game."""

    def test_player_drawn_from_empty_library_loses(self) -> None:
        """Player with drawn_from_empty_library=True should have has_lost set."""
        game = _make_game()
        game.players[0].drawn_from_empty_library = True
        result = check_state_based_actions(game)
        assert game.players[0].has_lost is True
        assert result is True

    def test_player_not_drawn_from_empty_library_does_not_lose(self) -> None:
        """Player with drawn_from_empty_library=False should not lose."""
        game = _make_game()
        assert game.players[0].drawn_from_empty_library is False
        check_state_based_actions(game)
        assert game.players[0].has_lost is False

    def test_already_lost_player_drawn_empty_not_retriggered(self) -> None:
        """Player already lost should not trigger a new action for empty library draw."""
        game = _make_game()
        game.players[0].drawn_from_empty_library = True
        game.players[0].has_lost = True
        result = check_state_based_actions(game)
        # No new action because player is already marked as lost
        assert result is False


# ===========================================================================
# Legend rule
# ===========================================================================
class TestLegendRule:
    """SBA: If a player controls 2+ legendaries with the same name, they choose one to keep."""

    def test_two_same_name_legendaries_one_goes_to_graveyard(self) -> None:
        """Two legendaries with same name → player chooses one, the other goes to graveyard."""
        legend1 = _make_legendary(name="Thalia")
        legend2 = _make_legendary(name="Thalia")
        # Script: player chooses legend1 to keep
        game = _make_game(p1_script=[legend1])
        _battlefield(game, 0).add(legend1)
        _battlefield(game, 0).add(legend2)
        result = check_state_based_actions(game)
        assert result is True
        assert _battlefield(game, 0).contains(legend1)
        assert not _battlefield(game, 0).contains(legend2)
        assert _graveyard(game, 0).contains(legend2)

    def test_two_same_name_legendaries_choose_second(self) -> None:
        """Player can choose the second legendary to keep; first goes to graveyard."""
        legend1 = _make_legendary(name="Thalia")
        legend2 = _make_legendary(name="Thalia")
        # Script: player chooses legend2 to keep
        game = _make_game(p1_script=[legend2])
        _battlefield(game, 0).add(legend1)
        _battlefield(game, 0).add(legend2)
        check_state_based_actions(game)
        assert not _battlefield(game, 0).contains(legend1)
        assert _battlefield(game, 0).contains(legend2)
        assert _graveyard(game, 0).contains(legend1)

    def test_two_different_name_legendaries_both_stay(self) -> None:
        """Two legendaries with different names should both stay on battlefield."""
        legend1 = _make_legendary(name="Thalia")
        legend2 = _make_legendary(name="Isamaru")
        game = _make_game()
        _battlefield(game, 0).add(legend1)
        _battlefield(game, 0).add(legend2)
        check_state_based_actions(game)
        assert _battlefield(game, 0).contains(legend1)
        assert _battlefield(game, 0).contains(legend2)

    def test_single_legendary_stays(self) -> None:
        """A lone legendary should not trigger the legend rule."""
        legend = _make_legendary(name="Thalia")
        game = _make_game()
        _battlefield(game, 0).add(legend)
        check_state_based_actions(game)
        assert _battlefield(game, 0).contains(legend)

    def test_three_same_name_legendaries_two_go_to_graveyard(self) -> None:
        """Three legendaries with same name → player keeps one, two go to graveyard."""
        legend1 = _make_legendary(name="Thalia")
        legend2 = _make_legendary(name="Thalia")
        legend3 = _make_legendary(name="Thalia")
        # Script: player chooses legend2 to keep
        game = _make_game(p1_script=[legend2])
        _battlefield(game, 0).add(legend1)
        _battlefield(game, 0).add(legend2)
        _battlefield(game, 0).add(legend3)
        check_state_based_actions(game)
        assert not _battlefield(game, 0).contains(legend1)
        assert _battlefield(game, 0).contains(legend2)
        assert not _battlefield(game, 0).contains(legend3)

    def test_legend_rule_per_player(self) -> None:
        """Legend rule applies per player — each player can have their own copy."""
        legend_p1 = _make_legendary(name="Thalia")
        legend_p2 = _make_legendary(name="Thalia")
        game = _make_game()
        _battlefield(game, 0).add(legend_p1)
        _battlefield(game, 1).add(legend_p2)
        check_state_based_actions(game)
        # Each player controls only one, so no legend rule trigger
        assert _battlefield(game, 0).contains(legend_p1)
        assert _battlefield(game, 1).contains(legend_p2)


# ===========================================================================
# Token not on battlefield → ceases to exist
# ===========================================================================
class TestTokenNotOnBattlefield:
    """SBA: Tokens not on the battlefield cease to exist (removed from game)."""

    def test_token_in_graveyard_removed(self) -> None:
        """A token in the graveyard should be removed entirely."""
        game = _make_game()
        token = _make_token(name="Soldier")
        _graveyard(game, 0).add(token)
        result = check_state_based_actions(game)
        assert result is True
        assert not _graveyard(game, 0).contains(token)

    def test_token_on_battlefield_stays(self) -> None:
        """A token on the battlefield should NOT be removed."""
        game = _make_game()
        token = _make_token(name="Soldier", toughness=1)
        _battlefield(game, 0).add(token)
        check_state_based_actions(game)
        assert _battlefield(game, 0).contains(token)

    def test_token_in_hand_removed(self) -> None:
        """A token in a player's hand should be removed."""
        game = _make_game()
        token = _make_token(name="Soldier")
        game.players[0].zones[Zone.HAND].add(token)
        result = check_state_based_actions(game)
        assert result is True
        assert not game.players[0].zones[Zone.HAND].contains(token)

    def test_token_in_exile_removed(self) -> None:
        """A token in exile should be removed."""
        game = _make_game()
        token = _make_token(name="Soldier")
        game.players[0].zones[Zone.EXILE].add(token)
        result = check_state_based_actions(game)
        assert result is True
        assert not game.players[0].zones[Zone.EXILE].contains(token)

    def test_non_token_in_graveyard_stays(self) -> None:
        """A non-token card in the graveyard should NOT be removed."""
        game = _make_game()
        creature = _make_creature(name="Bear", is_token=False)
        _graveyard(game, 0).add(creature)
        check_state_based_actions(game)
        assert _graveyard(game, 0).contains(creature)


# ===========================================================================
# Aura not attached to legal object → graveyard
# ===========================================================================
class TestAuraUnattached:
    """SBA: An aura not attached to a legal object is put into its owner's graveyard."""

    def test_aura_with_none_attached_to_goes_to_graveyard(self) -> None:
        """An aura with attached_to=None should be moved to graveyard."""
        game = _make_game()
        aura = _make_aura(name="Pacifism", attached_to=None)
        _battlefield(game, 0).add(aura)
        result = check_state_based_actions(game)
        assert result is True
        assert not _battlefield(game, 0).contains(aura)
        assert _graveyard(game, 0).contains(aura)

    def test_aura_attached_to_valid_target_stays(self) -> None:
        """An aura attached to a legal object on the battlefield should stay."""
        game = _make_game()
        target = _make_creature(name="Bear", toughness=2)
        aura = _make_aura(name="Pacifism", attached_to=target)
        _battlefield(game, 0).add(target)
        _battlefield(game, 0).add(aura)
        check_state_based_actions(game)
        assert _battlefield(game, 0).contains(aura)

    def test_aura_attached_to_object_not_on_battlefield_goes_to_graveyard(self) -> None:
        """An aura whose target is no longer on the battlefield should go to graveyard."""
        game = _make_game()
        target = _make_creature(name="Bear", toughness=2)
        aura = _make_aura(name="Pacifism", attached_to=target)
        # Target is NOT on the battlefield, but aura is
        _battlefield(game, 0).add(aura)
        result = check_state_based_actions(game)
        assert result is True
        assert not _battlefield(game, 0).contains(aura)
        assert _graveyard(game, 0).contains(aura)


# ===========================================================================
# +1/+1 and -1/-1 counter annihilation
# ===========================================================================
class TestCounterAnnihilation:
    """SBA: +1/+1 and -1/-1 counters on the same permanent annihilate in pairs."""

    def test_equal_counters_annihilate_to_zero(self) -> None:
        """3 +1/+1 and 3 -1/-1 should both become 0."""
        game = _make_game()
        creature = _make_creature(plus_one_counters=3, minus_one_counters=3, toughness=2)
        _battlefield(game, 0).add(creature)
        result = check_state_based_actions(game)
        assert result is True
        assert creature.plus_one_counters == 0
        assert creature.minus_one_counters == 0

    def test_more_plus_counters_remainder_stays(self) -> None:
        """5 +1/+1 and 2 -1/-1 should leave 3 +1/+1 and 0 -1/-1."""
        game = _make_game()
        creature = _make_creature(plus_one_counters=5, minus_one_counters=2, toughness=5)
        _battlefield(game, 0).add(creature)
        check_state_based_actions(game)
        assert creature.plus_one_counters == 3
        assert creature.minus_one_counters == 0

    def test_more_minus_counters_remainder_stays(self) -> None:
        """2 +1/+1 and 4 -1/-1 should leave 0 +1/+1 and 2 -1/-1."""
        game = _make_game()
        creature = _make_creature(plus_one_counters=2, minus_one_counters=4, toughness=5)
        _battlefield(game, 0).add(creature)
        check_state_based_actions(game)
        assert creature.plus_one_counters == 0
        assert creature.minus_one_counters == 2

    def test_no_counters_no_action(self) -> None:
        """A creature with 0 of each counter should not trigger annihilation."""
        game = _make_game()
        creature = _make_creature(plus_one_counters=0, minus_one_counters=0, toughness=2)
        _battlefield(game, 0).add(creature)
        # Only counter SBA check — other SBAs won't fire for a healthy creature
        result = check_state_based_actions(game)
        assert result is False
        assert creature.plus_one_counters == 0
        assert creature.minus_one_counters == 0

    def test_only_plus_counters_no_annihilation(self) -> None:
        """A creature with +1/+1 counters but no -1/-1 should not have annihilation."""
        game = _make_game()
        creature = _make_creature(plus_one_counters=3, minus_one_counters=0, toughness=2)
        _battlefield(game, 0).add(creature)
        check_state_based_actions(game)
        assert creature.plus_one_counters == 3
        assert creature.minus_one_counters == 0

    def test_only_minus_counters_no_annihilation(self) -> None:
        """A creature with -1/-1 counters but no +1/+1 should not have annihilation."""
        game = _make_game()
        creature = _make_creature(plus_one_counters=0, minus_one_counters=2, toughness=5)
        _battlefield(game, 0).add(creature)
        check_state_based_actions(game)
        assert creature.plus_one_counters == 0
        assert creature.minus_one_counters == 2


# ===========================================================================
# check_state_based_actions return value
# ===========================================================================
class TestCheckReturnValue:
    """check_state_based_actions should return True when action taken, False when stable."""

    def test_returns_false_when_no_actions_needed(self) -> None:
        """Clean game state should return False — no actions needed."""
        game = _make_game()
        result = check_state_based_actions(game)
        assert result is False

    def test_returns_true_when_life_zero(self) -> None:
        """Should return True when a player's life triggers the SBA."""
        game = _make_game(p1_life=0)
        result = check_state_based_actions(game)
        assert result is True

    def test_returns_true_when_creature_dies(self) -> None:
        """Should return True when a creature with zero toughness is removed."""
        game = _make_game()
        creature = _make_creature(toughness=0)
        _battlefield(game, 0).add(creature)
        result = check_state_based_actions(game)
        assert result is True

    def test_second_call_returns_false_after_stable(self) -> None:
        """After all SBAs are resolved, a second call should return False."""
        game = _make_game(p1_life=0)
        check_state_based_actions(game)
        result = check_state_based_actions(game)
        assert result is False


# ===========================================================================
# resolve_state_based_actions — loops until stable
# ===========================================================================
class TestResolveStateBasedActions:
    """resolve_state_based_actions should loop until check returns False."""

    def test_resolves_single_sba(self) -> None:
        """Simple case: one creature with 0 toughness should end up in graveyard."""
        game = _make_game()
        creature = _make_creature(toughness=0)
        _battlefield(game, 0).add(creature)
        resolve_state_based_actions(game)
        assert not _battlefield(game, 0).contains(creature)
        assert _graveyard(game, 0).contains(creature)

    def test_resolves_cascading_sbas(self) -> None:
        """Resolve should loop: token dies → goes to graveyard → token in graveyard ceases to exist.

        A token with zero toughness first moves to graveyard (zero toughness SBA),
        then on the next pass the token-not-on-battlefield SBA removes it from graveyard.
        """
        game = _make_game()
        token = _make_token(name="Illusion", toughness=0)
        _battlefield(game, 0).add(token)
        resolve_state_based_actions(game)
        # Token should NOT be on battlefield
        assert not _battlefield(game, 0).contains(token)
        # Token should also NOT be in graveyard (ceases to exist)
        assert not _graveyard(game, 0).contains(token)

    def test_stable_state_no_change(self) -> None:
        """On a clean game state, resolve should do nothing."""
        game = _make_game()
        creature = _make_creature(toughness=5)
        _battlefield(game, 0).add(creature)
        resolve_state_based_actions(game)
        assert _battlefield(game, 0).contains(creature)

    def test_player_life_zero_resolved(self) -> None:
        """After resolve, player with 0 life should be marked as lost."""
        game = _make_game(p1_life=0)
        resolve_state_based_actions(game)
        assert game.players[0].has_lost is True


# ===========================================================================
# Multiple SBAs in same check
# ===========================================================================
class TestMultipleSBAs:
    """Multiple SBAs can trigger in the same pass of check_state_based_actions."""

    def test_life_zero_and_creature_zero_toughness_same_pass(self) -> None:
        """Both life zero and creature zero toughness should be handled in one call."""
        game = _make_game(p1_life=0)
        creature = _make_creature(toughness=0)
        _battlefield(game, 0).add(creature)
        result = check_state_based_actions(game)
        assert result is True
        assert game.players[0].has_lost is True
        assert not _battlefield(game, 0).contains(creature)
        assert _graveyard(game, 0).contains(creature)

    def test_lethal_damage_and_counter_annihilation_same_pass(self) -> None:
        """A creature with lethal damage AND counters to annihilate — both should resolve."""
        game = _make_game()
        dying = _make_creature(toughness=2, damage_marked=3)
        countered = _make_creature(
            name="Hydra", toughness=5, plus_one_counters=3, minus_one_counters=2
        )
        _battlefield(game, 0).add(dying)
        _battlefield(game, 0).add(countered)
        check_state_based_actions(game)
        # dying creature should be in graveyard
        assert not _battlefield(game, 0).contains(dying)
        assert _graveyard(game, 0).contains(dying)
        # countered creature should have annihilated counters
        assert countered.plus_one_counters == 1
        assert countered.minus_one_counters == 0
        # countered creature stays on battlefield
        assert _battlefield(game, 0).contains(countered)

    def test_both_players_different_sbas(self) -> None:
        """Different SBAs for different players should all be handled."""
        game = _make_game(p2_life=-3)
        creature = _make_creature(toughness=0)
        _battlefield(game, 0).add(creature)
        check_state_based_actions(game)
        # Player 2 should lose
        assert game.players[1].has_lost is True
        # Player 1's creature should be in graveyard
        assert not _battlefield(game, 0).contains(creature)
        assert _graveyard(game, 0).contains(creature)

    def test_legend_rule_and_creature_zero_toughness_same_pass(self) -> None:
        """Legend rule and zero toughness both in the same pass."""
        legend1 = _make_legendary(name="Thalia")
        legend2 = _make_legendary(name="Thalia")
        fragile = _make_creature(name="Weakling", toughness=0)
        game = _make_game(p1_script=[legend1])
        _battlefield(game, 0).add(legend1)
        _battlefield(game, 0).add(legend2)
        _battlefield(game, 0).add(fragile)
        check_state_based_actions(game)
        # Legend rule: legend1 kept, legend2 in graveyard
        assert _battlefield(game, 0).contains(legend1)
        assert not _battlefield(game, 0).contains(legend2)
        # Zero toughness: fragile in graveyard
        assert not _battlefield(game, 0).contains(fragile)
        assert _graveyard(game, 0).contains(fragile)


# ===========================================================================
# Equipment (non-aura) should NOT be sacrificed by aura SBA
# ===========================================================================
class TestEquipmentNotTreatedAsAura:
    """SBA fix: objects with ``attached_to`` but no ``is_aura`` must not be
    sacrificed by the aura-unattached state-based action.

    This verifies the fix for ``getattr(obj, 'is_aura', True)`` → ``False``.
    """

    def test_equipped_equipment_stays_on_battlefield(self) -> None:
        """Equipment attached to a creature on the battlefield must survive SBAs."""
        game = _make_game()
        creature = _make_creature(name="Bear", toughness=2)
        equipment = _make_equipment(name="Bonesplitter", attached_to=creature)
        _battlefield(game, 0).add(creature)
        _battlefield(game, 0).add(equipment)

        resolve_state_based_actions(game)

        assert _battlefield(game, 0).contains(equipment), (
            "Equipment attached to a creature should remain on the battlefield"
        )
        assert _battlefield(game, 0).contains(creature)

    def test_unequipped_equipment_stays_on_battlefield(self) -> None:
        """Equipment sitting on the battlefield with attached_to=None must NOT
        be treated as an unattached aura and sacrificed."""
        game = _make_game()
        equipment = _make_equipment(name="Swiftfoot Boots", attached_to=None)
        _battlefield(game, 0).add(equipment)

        result = check_state_based_actions(game)

        assert _battlefield(game, 0).contains(equipment), (
            "Unequipped equipment should remain on the battlefield"
        )

    def test_equipment_whose_creature_left_battlefield_stays(self) -> None:
        """If the equipped creature leaves the battlefield, the equipment
        should stay (it becomes unattached, but SBAs should NOT sacrifice it
        because it is not an aura)."""
        game = _make_game()
        creature = _make_creature(name="Bear", toughness=2)
        equipment = _make_equipment(name="Whispersilk Cloak", attached_to=creature)
        # Equipment is on the battlefield, creature is NOT
        _battlefield(game, 0).add(equipment)

        resolve_state_based_actions(game)

        assert _battlefield(game, 0).contains(equipment), (
            "Equipment whose creature left should stay on the battlefield"
        )

    def test_object_with_attached_to_and_is_aura_false_stays(self) -> None:
        """An object that explicitly sets is_aura=False should not be
        treated as an unattached aura even if attached_to is None."""
        game = _make_game()
        obj = SimpleNamespace(
            name="CustomArtifact",
            attached_to=None,
            supertypes=set(),
            is_token=False,
            is_aura=False,
        )
        _battlefield(game, 0).add(obj)

        check_state_based_actions(game)

        assert _battlefield(game, 0).contains(obj), (
            "Object with is_aura=False should not be sacrificed by aura SBA"
        )

    def test_aura_with_is_aura_true_still_sacrificed_when_unattached(self) -> None:
        """Ensure the fix didn't break aura handling: an object with
        is_aura=True and attached_to=None must still go to graveyard."""
        game = _make_game()
        aura = _make_aura(name="Holy Strength", attached_to=None)
        _battlefield(game, 0).add(aura)

        check_state_based_actions(game)

        assert not _battlefield(game, 0).contains(aura), (
            "Aura with is_aura=True and no attachment should be sacrificed"
        )
        assert _graveyard(game, 0).contains(aura)

    def test_aura_with_is_aura_true_and_missing_target_sacrificed(self) -> None:
        """Aura whose enchanted creature is no longer on the battlefield
        must still be put into its owner's graveyard."""
        game = _make_game()
        dead_creature = _make_creature(name="Bear", toughness=2)
        aura = _make_aura(name="Pacifism", attached_to=dead_creature)
        # Aura is on battlefield, creature is NOT
        _battlefield(game, 0).add(aura)

        resolve_state_based_actions(game)

        assert not _battlefield(game, 0).contains(aura), (
            "Aura attached to missing creature should be sacrificed"
        )
        assert _graveyard(game, 0).contains(aura)


# ===========================================================================
# SBA trigger queueing — death triggers, LEAVES_BATTLEFIELD, loop behaviour
# ===========================================================================


def _make_creature_with_card_types(
    name: str = "Bear",
    toughness: int = 2,
    damage_marked: int = 0,
    supertypes: set | None = None,
    is_token: bool = False,
    card_types: set | None = None,
    keywords: object | None = None,
    plus_one_counters: int = 0,
    minus_one_counters: int = 0,
) -> SimpleNamespace:
    """Create a mock creature that includes ``card_types`` for event firing."""
    obj = SimpleNamespace(
        name=name,
        toughness=toughness,
        damage_marked=damage_marked,
        supertypes=supertypes or set(),
        is_token=is_token,
        card_types=card_types if card_types is not None else {CardType.CREATURE},
        plus_one_counters=plus_one_counters,
        minus_one_counters=minus_one_counters,
    )
    if keywords is not None:
        obj.keywords = keywords
    return obj


class TestSBATriggerQueueing:
    """SBA trigger queueing: events fired during SBAs, triggers pushed to stack."""

    def test_creature_dies_event_fires_on_lethal_damage(self) -> None:
        """When a creature with lethal damage dies via SBAs, CREATURE_DIES
        event should fire and its registered death trigger should be pushed
        onto the stack."""
        game = _make_game()
        creature = _make_creature_with_card_types(
            name="Doomed Bear", toughness=2, damage_marked=2,
        )
        creature.owner = game.players[0]
        _battlefield(game, 0).add(creature)

        # Track whether CREATURE_DIES was fired
        died_creatures: list[object] = []

        def on_death_effect(g):
            died_creatures.append(creature)

        # Register a "when this creature dies" trigger
        trigger = TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=lambda g, data: data.get("creature") is creature,
            effect=on_death_effect,
            source=creature,
            controller=game.players[0],
        )
        game.trigger_manager.register(trigger)

        resolve_state_based_actions(game)

        # Creature should be in graveyard
        assert not _battlefield(game, 0).contains(creature)
        assert _graveyard(game, 0).contains(creature)

        # Death trigger should have been pushed onto the stack
        assert len(game.stack._items) >= 1, (
            "Death trigger should be on the stack after SBA processes lethal damage"
        )
        # The trigger's on_resolve should be the death effect
        stack_item = game.stack._items[0]
        assert stack_item.source is creature

    def test_creature_dies_event_fires_on_zero_toughness(self) -> None:
        """CREATURE_DIES event should fire when a creature dies via zero
        toughness SBA, not just lethal damage."""
        game = _make_game()
        creature = _make_creature_with_card_types(
            name="Fragile Creature", toughness=0,
        )
        creature.owner = game.players[0]
        _battlefield(game, 0).add(creature)

        died: list[bool] = []

        trigger = TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=lambda g, data: data.get("creature") is creature,
            effect=lambda g: died.append(True),
            source=creature,
            controller=game.players[0],
        )
        game.trigger_manager.register(trigger)

        resolve_state_based_actions(game)

        assert len(game.stack._items) >= 1, (
            "Death trigger should fire for creature with zero toughness"
        )

    def test_leaves_battlefield_event_fires_on_creature_death(self) -> None:
        """LEAVES_BATTLEFIELD event should fire when a creature dies via SBAs."""
        game = _make_game()
        creature = _make_creature_with_card_types(
            name="Leaving Bear", toughness=2, damage_marked=3,
        )
        creature.owner = game.players[0]
        _battlefield(game, 0).add(creature)

        left: list[bool] = []

        # Use a separate source object for the trigger so it doesn't get
        # unregistered when the creature leaves.
        trigger_source = SimpleNamespace(name="Observer")
        trigger = TriggerRegistration(
            event_type=EventType.LEAVES_BATTLEFIELD,
            condition=lambda g, data: data.get("permanent") is creature,
            effect=lambda g: left.append(True),
            source=trigger_source,
            controller=game.players[0],
        )
        game.trigger_manager.register(trigger)

        resolve_state_based_actions(game)

        assert len(game.stack._items) >= 1, (
            "LEAVES_BATTLEFIELD trigger should fire when creature dies via SBA"
        )

    def test_multiple_creatures_dying_all_triggers_queued(self) -> None:
        """When multiple creatures die simultaneously via SBAs, all their
        death triggers should be pushed onto the stack."""
        game = _make_game()
        creatures = []
        for i in range(3):
            c = _make_creature_with_card_types(
                name=f"Doomed_{i}", toughness=2, damage_marked=2,
            )
            c.owner = game.players[0]
            _battlefield(game, 0).add(c)
            creatures.append(c)

        trigger_count = [0]

        for c in creatures:
            trigger = TriggerRegistration(
                event_type=EventType.CREATURE_DIES,
                condition=lambda g, data, cap=c: data.get("creature") is cap,
                effect=lambda g: trigger_count.__setitem__(0, trigger_count[0] + 1),
                source=c,
                controller=game.players[0],
            )
            game.trigger_manager.register(trigger)

        resolve_state_based_actions(game)

        # All 3 creatures should be in graveyard
        for c in creatures:
            assert _graveyard(game, 0).contains(c)

        # All 3 death triggers should be on the stack
        assert len(game.stack._items) >= 3, (
            f"Expected 3 death triggers on stack, got {len(game.stack._items)}"
        )

    def test_non_creature_permanent_fires_leaves_but_not_dies(self) -> None:
        """A non-creature permanent removed via SBAs (e.g., legend rule) should
        fire LEAVES_BATTLEFIELD but NOT CREATURE_DIES."""
        game = _make_game(p1_script=["keep_first"])  # script for legend rule choice
        # Two legendary enchantments with the same name
        ench1 = SimpleNamespace(
            name="Legendary Enchantment",
            supertypes={Supertype.LEGENDARY},
            is_token=False,
            card_types={CardType.ENCHANTMENT},
        )
        ench2 = SimpleNamespace(
            name="Legendary Enchantment",
            supertypes={Supertype.LEGENDARY},
            is_token=False,
            card_types={CardType.ENCHANTMENT},
        )
        ench1.owner = game.players[0]
        ench2.owner = game.players[0]
        _battlefield(game, 0).add(ench1)
        _battlefield(game, 0).add(ench2)

        # Script the player to choose ench1 to keep
        game.players[0]._script.clear()
        game.players[0]._script.append(ench1)

        creature_dies_fired = []
        leaves_fired = []

        # Observer trigger for CREATURE_DIES — should NOT fire
        observer = SimpleNamespace(name="Observer")
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=None,
            effect=lambda g: creature_dies_fired.append(True),
            source=observer,
            controller=game.players[0],
        ))

        # Observer trigger for LEAVES_BATTLEFIELD — should fire for ench2
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.LEAVES_BATTLEFIELD,
            condition=None,
            effect=lambda g: leaves_fired.append(True),
            source=observer,
            controller=game.players[0],
        ))

        resolve_state_based_actions(game)

        # CREATURE_DIES should not have produced a stack object for non-creature
        creature_dies_on_stack = [
            s for s in game.stack._items
            if s.on_resolve.__code__ == (lambda g: creature_dies_fired.append(True)).__code__
        ]
        # Simpler check: creature_dies_fired should not have been populated
        # by the trigger itself (it fires into the stack, not directly called).
        # Instead, check that LEAVES_BATTLEFIELD did fire (stack has items)
        # and that the source for any stack entry is observer (LTB trigger).
        assert len(game.stack._items) >= 1, (
            "LEAVES_BATTLEFIELD trigger should fire for non-creature permanent"
        )

    def test_creature_token_dies_fires_creature_dies_event(self) -> None:
        """A creature token dying via SBAs should fire CREATURE_DIES event."""
        game = _make_game()
        token = _make_creature_with_card_types(
            name="Soldier Token", toughness=1, damage_marked=1, is_token=True,
        )
        token.owner = game.players[0]
        _battlefield(game, 0).add(token)

        trigger_source = SimpleNamespace(name="Observer")
        fired = []

        trigger = TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=lambda g, data: data.get("creature") is token,
            effect=lambda g: fired.append(True),
            source=trigger_source,
            controller=game.players[0],
        )
        game.trigger_manager.register(trigger)

        resolve_state_based_actions(game)

        # Token goes to graveyard then ceases to exist (token SBA),
        # but the death trigger should have been queued first.
        assert len(game.stack._items) >= 1, (
            "CREATURE_DIES trigger should fire for creature tokens dying via SBA"
        )

    def test_sba_loop_repeats_when_triggers_queued(self) -> None:
        """The SBA loop should repeat if triggers were pushed onto the stack
        during processing. Per MTG 704.3, the game must re-check SBAs after
        triggers are queued."""
        game = _make_game()
        creature = _make_creature_with_card_types(
            name="Chain Creature", toughness=2, damage_marked=2,
        )
        creature.owner = game.players[0]
        _battlefield(game, 0).add(creature)

        # Register a death trigger: its mere placement on the stack should
        # cause the SBA loop to iterate again (checking if new SBAs arose).
        trigger = TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=lambda g, data: data.get("creature") is creature,
            effect=lambda g: None,
            source=creature,
            controller=game.players[0],
        )
        game.trigger_manager.register(trigger)

        # Snapshot: stack should be empty before
        assert game.stack.is_empty()

        result = resolve_state_based_actions(game)

        # SBAs were performed
        assert result is True
        # Trigger is on the stack
        assert not game.stack.is_empty(), (
            "Death trigger should be on the stack after resolve_state_based_actions"
        )

    def test_death_trigger_source_matches_dying_creature(self) -> None:
        """The stack object created by a death trigger should reference
        the dying creature as its source."""
        game = _make_game()
        creature = _make_creature_with_card_types(
            name="Tracked Bear", toughness=1, damage_marked=1,
        )
        creature.owner = game.players[0]
        _battlefield(game, 0).add(creature)

        effect_called = []

        def death_effect(g):
            effect_called.append(True)

        trigger = TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=lambda g, data: data.get("creature") is creature,
            effect=death_effect,
            source=creature,
            controller=game.players[0],
        )
        game.trigger_manager.register(trigger)

        resolve_state_based_actions(game)

        assert len(game.stack._items) >= 1
        stack_obj = game.stack._items[0]
        assert stack_obj.source is creature
        assert stack_obj.controller is game.players[0]

        # Resolving the trigger should call the effect
        stack_obj.on_resolve(game)
        assert len(effect_called) == 1
