"""Tests for Witherbloom, the Balancer (SOS #245)."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_creature(name: str = "Creature") -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{1}{G}"),
        base_power=2,
        base_toughness=2,
    )


def _make_instant(generic: int = 3) -> Instant:
    return Instant(
        name="Test Instant",
        mana_cost=ManaCost(generic=generic),
    )


def _make_sorcery(generic: int = 4) -> Sorcery:
    return Sorcery(
        name="Test Sorcery",
        mana_cost=ManaCost(generic=generic),
    )


# ---------------------------------------------------------------------------
# 1. Card identity
# ---------------------------------------------------------------------------

class TestCardIdentity:
    def test_name(self):
        card = WitherbloomTheBalancer()
        assert card.name == "Witherbloom, the Balancer"

    def test_mana_cost(self):
        card = WitherbloomTheBalancer()
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_power_toughness(self):
        card = WitherbloomTheBalancer()
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_creature_type(self):
        card = WitherbloomTheBalancer()
        assert CardType.CREATURE in card.card_types

    def test_legendary_supertype(self):
        card = WitherbloomTheBalancer()
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self):
        card = WitherbloomTheBalancer()
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_flying_keyword(self):
        card = WitherbloomTheBalancer()
        assert Keyword.FLYING in card.keywords

    def test_deathtouch_keyword(self):
        card = WitherbloomTheBalancer()
        assert Keyword.DEATHTOUCH in card.keywords


# ---------------------------------------------------------------------------
# 2. Self affinity for creatures — cost_reduction()
# ---------------------------------------------------------------------------

class TestSelfAffinity:
    def test_no_creatures_no_reduction(self):
        game = create_game()
        wb = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[])
        wb.controller = game.players[0]
        assert wb.cost_reduction(game) == 0

    def test_one_creature_reduces_by_one(self):
        game = create_game()
        wb = WitherbloomTheBalancer()
        c1 = _make_creature("Bear")
        set_board_state(game, 0, battlefield=[c1])
        wb.controller = game.players[0]
        assert wb.cost_reduction(game) == 1

    def test_three_creatures_reduces_by_three(self):
        game = create_game()
        wb = WitherbloomTheBalancer()
        creatures = [_make_creature(f"Creature{i}") for i in range(3)]
        set_board_state(game, 0, battlefield=creatures)
        wb.controller = game.players[0]
        assert wb.cost_reduction(game) == 3

    def test_no_controller_returns_zero(self):
        game = create_game()
        wb = WitherbloomTheBalancer()
        c1 = _make_creature()
        set_board_state(game, 0, battlefield=[c1])
        wb.controller = None
        assert wb.cost_reduction(game) == 0

    def test_reduction_capped_at_generic(self):
        """Reduction can't exceed the generic portion (6 for Witherbloom)."""
        game = create_game()
        wb = WitherbloomTheBalancer()
        # 10 creatures, but generic is only 6
        creatures = [_make_creature(f"C{i}") for i in range(10)]
        set_board_state(game, 0, battlefield=creatures)
        wb.controller = game.players[0]
        # get_cost_reduction clamps to generic
        reduction = get_cost_reduction(game, wb, game.players[0])
        assert reduction == 6  # capped at generic=6

    def test_opponent_creatures_dont_reduce(self):
        """Only controller's creatures provide reduction."""
        game = create_game()
        wb = WitherbloomTheBalancer()
        # Put creatures on opponent's battlefield, none on controller's
        opp_creatures = [_make_creature(f"OppC{i}") for i in range(4)]
        set_board_state(game, 0, battlefield=[])
        set_board_state(game, 1, battlefield=opp_creatures)
        wb.controller = game.players[0]
        assert wb.cost_reduction(game) == 0


# ---------------------------------------------------------------------------
# 3. Affinity granted to instants/sorceries via global_cost_reduction_for
# ---------------------------------------------------------------------------

class TestGrantedAffinity:
    def test_instant_gets_reduced_with_witherbloom_on_battlefield(self):
        game = create_game()
        c1 = _make_creature("Elf")
        c2 = _make_creature("Goblin")
        wb = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[c1, c2, wb])
        player = game.players[0]

        instant = _make_instant(generic=3)
        instant.controller = player

        reduction = get_cost_reduction(game, instant, player)
        # 3 creatures (c1, c2, wb) on battlefield → reduction = 3
        assert reduction == 3

    def test_sorcery_gets_reduced_with_witherbloom_on_battlefield(self):
        game = create_game()
        c1 = _make_creature("Elf")
        wb = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[c1, wb])
        player = game.players[0]

        sorcery = _make_sorcery(generic=4)
        sorcery.controller = player

        reduction = get_cost_reduction(game, sorcery, player)
        # 2 creatures (c1, wb) → reduction = 2
        assert reduction == 2

    def test_granted_reduction_capped_at_generic(self):
        """Granted reduction can't reduce generic below 0."""
        game = create_game()
        creatures = [_make_creature(f"C{i}") for i in range(5)]
        wb = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=creatures + [wb])
        player = game.players[0]

        # Instant with only 2 generic mana
        instant = _make_instant(generic=2)
        instant.controller = player

        reduction = get_cost_reduction(game, instant, player)
        # 6 creatures total, but generic is 2 → capped at 2
        assert reduction == 2

    def test_no_effect_on_creature_spells(self):
        """Witherbloom does NOT grant affinity to creature spells."""
        game = create_game()
        c1 = _make_creature("Bear")
        wb = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[c1, wb])
        player = game.players[0]

        creature_spell = _make_creature("New Bear")
        creature_spell.controller = player

        reduction = get_cost_reduction(game, creature_spell, player)
        # creature_spell has its own cost_reduction (0 by default)
        # and Witherbloom only grants to instants/sorceries
        assert reduction == 0

    def test_no_effect_on_opponent_instants(self):
        """Witherbloom only reduces costs for its controller, not opponents."""
        game = create_game()
        c1 = _make_creature("Bear")
        wb = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[c1, wb])  # wb controlled by p0
        player1 = game.players[1]

        instant = _make_instant(generic=3)
        instant.controller = player1

        reduction = get_cost_reduction(game, instant, player1)
        # Witherbloom is controlled by player0, not player1
        assert reduction == 0

    def test_no_effect_when_witherbloom_not_on_battlefield(self):
        """Without Witherbloom on battlefield, instants get no bonus reduction."""
        game = create_game()
        c1 = _make_creature("Bear")
        c2 = _make_creature("Wolf")
        # No Witherbloom on battlefield
        set_board_state(game, 0, battlefield=[c1, c2])
        player = game.players[0]

        instant = _make_instant(generic=3)
        instant.controller = player

        reduction = get_cost_reduction(game, instant, player)
        # instant.cost_reduction() returns 0, no Witherbloom on battlefield
        assert reduction == 0

    def test_witherbloom_counts_itself_for_granted_affinity(self):
        """Witherbloom itself is a creature and counts toward the reduction."""
        game = create_game()
        wb = WitherbloomTheBalancer()
        # Only Witherbloom on battlefield (no other creatures)
        set_board_state(game, 0, battlefield=[wb])
        player = game.players[0]

        instant = _make_instant(generic=3)
        instant.controller = player

        reduction = get_cost_reduction(game, instant, player)
        assert reduction == 1

    def test_full_cast_instant_with_reduction(self):
        """Integration test: cast an instant with reduced cost due to Witherbloom."""
        game = create_game()
        wb = WitherbloomTheBalancer()
        c1 = _make_creature("Bear")

        instant = _make_instant(generic=3)

        # Set up: witherbloom + 1 creature on battlefield; instant in hand
        set_board_state(
            game, 0,
            battlefield=[wb, c1],
            hand=[instant],
            mana={ManaType.COLORLESS: 1},  # 3 - 2 (wb + c1) = 1 needed
        )

        player = game.players[0]
        game.active_player_index = 0
        game.priority_player_index = 0

        from engine.casting import cast_spell as engine_cast
        # Should succeed with only 1 generic (reduced from 3 by 2 creatures)
        engine_cast(game, player, instant)
        # Spell on stack — no mana error means reduction worked
        assert not game.stack.is_empty()
