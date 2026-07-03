"""Tests for Witherbloom, the Balancer (sos_245)."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state
from engine.casting import get_cost_reduction


def _game_with_witherbloom(n_creatures=0):
    """Set up game with Witherbloom on p0's battlefield and n_creatures extra creatures."""
    wb = WitherbloomTheBalancer()
    creatures = [Creature(name=f"Creature{i}", base_power=1, base_toughness=1)
                 for i in range(n_creatures)]
    game = create_game()
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    p0 = game.players[0]
    # Put Witherbloom and extra creatures on battlefield
    battlefield = [wb] + creatures
    set_board_state(game, 0, battlefield=battlefield)
    return game, wb, creatures


def test_flying_deathtouch():
    """Witherbloom has Flying and Deathtouch."""
    wb = WitherbloomTheBalancer()
    assert Keyword.FLYING in wb.keywords
    assert Keyword.DEATHTOUCH in wb.keywords


def test_self_affinity_no_creatures():
    """With only Witherbloom on battlefield, affinity = 1 (Witherbloom itself)."""
    game, wb, _ = _game_with_witherbloom(n_creatures=0)
    p0 = game.players[0]
    wb.controller = p0
    # Witherbloom is a creature, so it counts itself
    assert wb.cost_reduction(game) == 1


def test_self_affinity_three_creatures():
    """With 3 extra creatures, affinity reduces cost by 4 (3 + Witherbloom itself)."""
    game, wb, creatures = _game_with_witherbloom(n_creatures=3)
    p0 = game.players[0]
    wb.controller = p0
    assert wb.cost_reduction(game) == 4


def test_grant_affinity_to_instant_via_e3():
    """E3: Instant spells cast by Witherbloom's controller get affinity for creatures."""
    game, wb, creatures = _game_with_witherbloom(n_creatures=2)
    p0 = game.players[0]
    wb.controller = p0

    # An instant with generic=5
    spell = Instant(name="Big Instant", mana_cost=ManaCost(generic=5))
    spell.controller = p0

    # E3 in get_cost_reduction should pick up wb.spell_cost_reduction
    # Total creatures: wb + 2 extras = 3
    reduction = get_cost_reduction(game, spell, p0)
    assert reduction == 3


def test_grant_affinity_only_to_own_spells():
    """Witherbloom only reduces cost of spells cast by its controller, not opponents."""
    game, wb, creatures = _game_with_witherbloom(n_creatures=2)
    p0 = game.players[0]
    p1 = game.players[1]
    wb.controller = p0

    # Opponent casts instant
    spell = Instant(name="Opponent Instant", mana_cost=ManaCost(generic=5))
    spell.controller = p1

    # No reduction from Witherbloom for opponent's spell
    reduction = get_cost_reduction(game, spell, p1)
    assert reduction == 0


def test_grant_affinity_clamps_at_zero():
    """Cost reduction clamps at the generic portion (never goes negative)."""
    game, wb, _ = _game_with_witherbloom(n_creatures=0)
    p0 = game.players[0]
    wb.controller = p0

    # Spell with only 1 generic (Witherbloom alone counts 1)
    spell = Instant(name="Cheap Instant", mana_cost=ManaCost(generic=1))
    spell.controller = p0

    reduction = get_cost_reduction(game, spell, p0)
    assert reduction == 1  # clamped to generic=1
