"""Edge-case and supplementary tests for simple_spells_batch2.

These tests complement the main test_simple_spells_batch2.py by covering
edge cases and boundary conditions not tested there:
- Drawing from an empty library
- Surveil with fewer than 2 cards in library
- Opponent discard when opponent hand is empty
- Sacrifice when no creatures on battlefield
- PoxPlague with odd life total (rounding down)
- PoxPlague with 1 permanent (floor division → sac 0)
- WisdomOfAges with no instants/sorceries in graveyard
- SnarlSong fractal token +1/+1 counters
- RapturousMoment discard when hand has fewer than 2 cards after draw
- Mana cost verification for all 15 spells
- get_targets() returns [] for all spells
"""

from __future__ import annotations

import pytest

from cards.foundations.simple_spells_batch2 import (
    AntiquitiesOnTheLoose,
    EmbraceTheParadox,
    FractalAnomaly,
    GroupProject,
    MusesEncouragement,
    PoxPlague,
    PursueThePast,
    RapturousMoment,
    SeizeTheSpoils,
    SendInThePest,
    SnarlSong,
    SocialSnub,
    VisionarysDance,
    WisdomOfAges,
    WitheringCurse,
)
from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, Keyword, ManaCost, Phase, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_game(
    *,
    phase: Phase = Phase.PRECOMBAT_MAIN,
) -> GameState:
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = phase
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    return game


def _add_cards_to_library(player: DeterministicPlayer, n: int) -> list:
    cards = []
    for i in range(n):
        c = CardImpl(name=f"LibCard{i}")
        c.owner = player
        player.zones[Zone.LIBRARY].add(c)
        cards.append(c)
    return cards


def _add_cards_to_hand(player: DeterministicPlayer, n: int) -> list:
    cards = []
    for i in range(n):
        c = CardImpl(name=f"HandCard{i}")
        c.owner = player
        player.zones[Zone.HAND].add(c)
        cards.append(c)
    return cards


def _make_creature(
    name: str = "Test Creature",
    power: int = 2,
    toughness: int = 3,
    owner=None,
    controller=None,
) -> Creature:
    return Creature(
        name=name,
        base_power=power,
        base_toughness=toughness,
        owner=owner,
        controller=controller,
    )


# ---------------------------------------------------------------------------
# Draw from empty library edge cases
# ---------------------------------------------------------------------------


class TestEmbraceTheParadoxEdges:
    """Edge cases for Embrace the Paradox draw spell."""

    def test_draw_from_empty_library(self) -> None:
        """Drawing from an empty library should not crash; draws what's available."""
        game = _make_game()
        p1 = game.players[0]
        # Only 1 card in library, spell tries to draw 3
        _add_cards_to_library(p1, 1)
        spell = EmbraceTheParadox(owner=p1, controller=p1)

        spell.on_resolve(game)
        # Should have drawn the 1 available card
        assert len(game.get_hand(p1)) == 1

    def test_draw_from_completely_empty_library(self) -> None:
        """Drawing from a completely empty library should not crash."""
        game = _make_game()
        p1 = game.players[0]
        spell = EmbraceTheParadox(owner=p1, controller=p1)

        # Should not raise
        spell.on_resolve(game)
        assert len(game.get_hand(p1)) == 0


class TestRapturousMomentEdges:
    """Edge cases for Rapturous Moment draw/discard spell."""

    def test_discard_fewer_than_two_when_hand_small(self) -> None:
        """If after drawing 3, hand has only 1 card, discard what's available."""
        game = _make_game()
        p1 = game.players[0]
        # Library has only 1 card
        _add_cards_to_library(p1, 1)
        spell = RapturousMoment(owner=p1, controller=p1)

        spell.on_resolve(game)
        # Drew 1, try to discard 2 but only have 1 → discard 1
        hand = game.get_hand(p1)
        assert len(hand) == 0

    def test_draw_from_empty_library(self) -> None:
        """Drawing from empty library should not crash."""
        game = _make_game()
        p1 = game.players[0]
        spell = RapturousMoment(owner=p1, controller=p1)

        # Should not raise
        spell.on_resolve(game)
        assert len(game.get_hand(p1)) == 0


# ---------------------------------------------------------------------------
# Surveil edge cases
# ---------------------------------------------------------------------------


class TestMusesEncouragementEdges:
    """Edge cases for Muse's Encouragement surveil."""

    def test_surveil_with_one_card_in_library(self) -> None:
        """Surveil 2 with only 1 card should put 1 in graveyard."""
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 1)
        spell = MusesEncouragement(owner=p1, controller=p1)

        spell.on_resolve(game)
        # Token should still be created
        bf = game.get_battlefield(p1)
        tokens = [o for o in bf.get_all() if getattr(o, "name", "") == "Elemental"]
        assert len(tokens) == 1
        # Only 1 card surveiled since library had only 1
        gy = game.get_graveyard(p1)
        assert len(gy) == 1

    def test_surveil_with_empty_library(self) -> None:
        """Surveil 2 with empty library should still create token."""
        game = _make_game()
        p1 = game.players[0]
        spell = MusesEncouragement(owner=p1, controller=p1)

        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [o for o in bf.get_all() if getattr(o, "name", "") == "Elemental"]
        assert len(tokens) == 1
        assert len(game.get_graveyard(p1)) == 0


# ---------------------------------------------------------------------------
# WisdomOfAges edge cases
# ---------------------------------------------------------------------------


class TestWisdomOfAgesEdges:
    """Edge cases for Wisdom of Ages graveyard recursion."""

    def test_no_instants_or_sorceries_in_graveyard(self) -> None:
        """When graveyard has no instants/sorceries, hand stays empty."""
        game = _make_game()
        p1 = game.players[0]

        # Only a creature in graveyard
        creature = Creature(name="Dud", base_power=1, base_toughness=1)
        creature.owner = p1
        p1.zones[Zone.GRAVEYARD].add(creature)

        spell = WisdomOfAges(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert len(game.get_hand(p1)) == 0
        # Creature stays in graveyard
        assert game.get_graveyard(p1).contains(creature)

    def test_empty_graveyard(self) -> None:
        """Resolving with empty graveyard should not crash."""
        game = _make_game()
        p1 = game.players[0]
        spell = WisdomOfAges(owner=p1, controller=p1)

        spell.on_resolve(game)
        assert len(game.get_hand(p1)) == 0


# ---------------------------------------------------------------------------
# SendInThePest edge cases
# ---------------------------------------------------------------------------


class TestSendInThePestEdges:
    """Edge cases for Send in the Pest."""

    def test_opponent_empty_hand_still_creates_token(self) -> None:
        """If opponent has no cards, spell still creates pest token."""
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Opponent hand is already empty
        spell = SendInThePest(owner=p1, controller=p1)

        spell.on_resolve(game)
        # Token still created
        bf = game.get_battlefield(p1)
        tokens = [o for o in bf.get_all() if getattr(o, "name", "") == "Pest"]
        assert len(tokens) == 1
        # Opponent hand unchanged
        assert len(game.get_hand(p2)) == 0


# ---------------------------------------------------------------------------
# SocialSnub edge cases
# ---------------------------------------------------------------------------


class TestSocialSnubEdges:
    """Edge cases for Social Snub."""

    def test_no_creatures_to_sacrifice(self) -> None:
        """If no creatures on battlefield, life drain still happens."""
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p1.life = 20
        p2.life = 20
        # No creatures on either side
        spell = SocialSnub(owner=p1, controller=p1)

        spell.on_resolve(game)
        # Life drain still applies
        assert p2.life == 19
        assert p1.life == 21

    def test_only_controller_has_creature(self) -> None:
        """If only controller has a creature, only their creature is sacrificed."""
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p1.life = 20
        p2.life = 20

        c1 = _make_creature(name="C1", owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)

        spell = SocialSnub(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert not game.get_battlefield(p1).contains(c1)
        assert p2.life == 19
        assert p1.life == 21


# ---------------------------------------------------------------------------
# PoxPlague edge cases
# ---------------------------------------------------------------------------


class TestPoxPlagueEdges:
    """Edge cases for Pox Plague rounding behavior."""

    def test_odd_life_rounds_down(self) -> None:
        """Losing half of 15 = 7 (floor), leaving 8."""
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p1.life = 15
        p2.life = 7

        spell = PoxPlague(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert p1.life == 8  # 15 - 7
        assert p2.life == 4  # 7 - 3

    def test_one_permanent_rounds_down_to_zero_sacrificed(self) -> None:
        """With 1 permanent, half rounded down = 0, so no sacrifice."""
        game = _make_game()
        p1 = game.players[0]
        p1.life = 2
        game.players[1].life = 2

        c1 = _make_creature(name="Lone", owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)

        spell = PoxPlague(owner=p1, controller=p1)
        spell.on_resolve(game)

        # 1 // 2 = 0, creature survives
        assert game.get_battlefield(p1).contains(c1)

    def test_one_card_in_hand_rounds_down_to_zero_discarded(self) -> None:
        """With 1 card in hand, half rounded down = 0."""
        game = _make_game()
        p1 = game.players[0]
        p1.life = 4
        game.players[1].life = 4
        hand_cards = _add_cards_to_hand(p1, 1)

        spell = PoxPlague(owner=p1, controller=p1)
        spell.on_resolve(game)

        # 1 // 2 = 0, card stays
        assert len(game.get_hand(p1)) == 1

    def test_life_at_one(self) -> None:
        """Half of 1 rounded down is 0, so life stays at 1."""
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p1.life = 1
        p2.life = 1

        spell = PoxPlague(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert p1.life == 1  # 1 - 0
        assert p2.life == 1


# ---------------------------------------------------------------------------
# SnarlSong edge cases
# ---------------------------------------------------------------------------


class TestSnarlSongEdges:
    """Edge cases for Snarl Song token counters."""

    def test_fractal_tokens_have_counters(self) -> None:
        """Default colors_spent=1, each Fractal should have 1 +1/+1 counter."""
        game = _make_game()
        p1 = game.players[0]
        p1.life = 20
        spell = SnarlSong(owner=p1, controller=p1)

        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [o for o in bf.get_all() if getattr(o, "name", "") == "Fractal"]
        assert len(tokens) == 2
        for t in tokens:
            assert getattr(t, "plus_one_counters", 0) == 1

    def test_custom_colors_spent(self) -> None:
        """Setting colors_spent changes counter count and life gain."""
        game = _make_game()
        p1 = game.players[0]
        p1.life = 20
        spell = SnarlSong(owner=p1, controller=p1)
        spell.colors_spent = 3

        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [o for o in bf.get_all() if getattr(o, "name", "") == "Fractal"]
        for t in tokens:
            assert getattr(t, "plus_one_counters", 0) == 3
        assert p1.life == 23  # 20 + 3


# ---------------------------------------------------------------------------
# FractalAnomaly edge cases
# ---------------------------------------------------------------------------


class TestFractalAnomalyEdges:
    """Edge cases for Fractal Anomaly counter tracking."""

    def test_zero_draws_means_zero_counters(self) -> None:
        """If cards_drawn_this_turn is not set, token gets 0 counters."""
        game = _make_game()
        p1 = game.players[0]
        spell = FractalAnomaly(owner=p1, controller=p1)

        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [o for o in bf.get_all() if getattr(o, "name", "") == "Fractal"]
        assert tokens[0].plus_one_counters == 0


# ---------------------------------------------------------------------------
# Mana cost completeness
# ---------------------------------------------------------------------------


_ALL_SPELLS_MANA = [
    (EmbraceTheParadox, "{3}{G}{U}"),
    (RapturousMoment, "{4}{U}{R}"),
    (WisdomOfAges, "{4}{U}{U}{U}"),
    (PursueThePast, "{R}{W}"),
    (SeizeTheSpoils, "{2}{R}"),
    (GroupProject, "{1}{W}"),
    (MusesEncouragement, "{4}{U}"),
    (VisionarysDance, "{5}{U}{R}"),
    (AntiquitiesOnTheLoose, "{1}{W}{W}"),
    (FractalAnomaly, "{U}"),
    (SnarlSong, "{5}{G}"),
    (SendInThePest, "{1}{B}"),
    (WitheringCurse, "{1}{B}{B}"),
    (SocialSnub, "{1}{W}{B}"),
    (PoxPlague, "{B}{B}{B}{B}{B}"),
]


class TestManaCostCompleteness:
    """Verify mana cost is correct for every spell."""

    @pytest.mark.parametrize(
        "spell_cls,expected_cost",
        _ALL_SPELLS_MANA,
        ids=[s[0].__name__ for s in _ALL_SPELLS_MANA],
    )
    def test_mana_cost(self, spell_cls, expected_cost) -> None:
        spell = spell_cls()
        assert spell.mana_cost == ManaCost.parse(expected_cost)


# ---------------------------------------------------------------------------
# get_targets returns [] for all spells
# ---------------------------------------------------------------------------


_ALL_SPELL_CLASSES = [
    EmbraceTheParadox, RapturousMoment, WisdomOfAges, PursueThePast,
    SeizeTheSpoils, GroupProject, MusesEncouragement, VisionarysDance,
    AntiquitiesOnTheLoose, FractalAnomaly, SnarlSong, SendInThePest,
    WitheringCurse, SocialSnub, PoxPlague,
]


class TestAllSpellsNonTargeted:
    """Every batch 2 spell is non-targeted."""

    @pytest.mark.parametrize(
        "spell_cls",
        _ALL_SPELL_CLASSES,
        ids=[c.__name__ for c in _ALL_SPELL_CLASSES],
    )
    def test_get_targets_returns_empty(self, spell_cls) -> None:
        game = _make_game()
        spell = spell_cls()
        assert spell.get_targets(game) == []


# ---------------------------------------------------------------------------
# Controller is None safety
# ---------------------------------------------------------------------------


class TestControllerNoneSafety:
    """Spells should not crash if controller is None."""

    @pytest.mark.parametrize(
        "spell_cls",
        _ALL_SPELL_CLASSES,
        ids=[c.__name__ for c in _ALL_SPELL_CLASSES],
    )
    def test_resolve_with_no_controller(self, spell_cls) -> None:
        game = _make_game()
        spell = spell_cls()
        spell.controller = None
        # Should not raise
        spell.on_resolve(game)
