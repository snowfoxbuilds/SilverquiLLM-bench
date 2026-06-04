"""Tests for Witherbloom, the Balancer (SOS #245)."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.casting import cast_spell, get_cost_reduction
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state


def _vanilla(name: str = "Bear") -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{1}{G}"),
        base_power=2,
        base_toughness=2,
    )


def test_basic_characteristics():
    card = WitherbloomTheBalancer()
    assert card.base_power == 5 and card.base_toughness == 5
    assert Keyword.FLYING in card.keywords
    assert Keyword.DEATHTOUCH in card.keywords
    assert Supertype.LEGENDARY in card.supertypes
    assert {"Elder", "Dragon"} <= card.subtypes


def test_self_affinity_reduces_by_creature_count():
    game = create_game()
    p1 = game.players[0]
    set_board_state(game, 0, battlefield=[_vanilla("A"), _vanilla("B"), _vanilla("C")])
    card = WitherbloomTheBalancer()
    card.controller = p1
    # {6}{B}{G}: 3 creatures → reduce generic 6 by 3.
    assert get_cost_reduction(game, card, p1) == 3


def test_self_affinity_clamped_to_generic():
    game = create_game()
    p1 = game.players[0]
    set_board_state(game, 0, battlefield=[_vanilla(str(i)) for i in range(9)])
    card = WitherbloomTheBalancer()
    card.controller = p1
    # 9 creatures but only 6 generic to reduce.
    assert get_cost_reduction(game, card, p1) == 6


def test_grants_affinity_to_instant():
    game = create_game()
    p1 = game.players[0]
    wither = WitherbloomTheBalancer()
    # Witherbloom + 1 other creature = 2 creatures controlled.
    set_board_state(game, 0, battlefield=[wither, _vanilla("Buddy")])
    bolt = Instant(name="Big Bolt", mana_cost=ManaCost.parse("{4}{R}"))
    bolt.controller = p1
    # Instant gets affinity for creatures: reduce {4} by 2.
    assert get_cost_reduction(game, bolt, p1) == 2


def test_grant_does_not_apply_to_creatures():
    game = create_game()
    p1 = game.players[0]
    wither = WitherbloomTheBalancer()
    set_board_state(game, 0, battlefield=[wither, _vanilla("Buddy")])
    other = Creature(
        name="Hill Giant",
        mana_cost=ManaCost.parse("{3}{R}"),
        base_power=3,
        base_toughness=3,
    )
    other.controller = p1
    # Witherbloom only grants affinity to instants/sorceries, not creatures.
    assert get_cost_reduction(game, other, p1) == 0


def test_instant_cast_pays_reduced_cost():
    game = create_game()
    p1 = game.players[0]
    wither = WitherbloomTheBalancer()
    set_board_state(game, 0, battlefield=[wither, _vanilla("Buddy")])
    bolt = Instant(name="Cheap Bolt", mana_cost=ManaCost.parse("{4}{R}"))
    set_board_state(game, 0, hand=[bolt])
    # Affinity 2 → effective {2}{R} = 3 mana.
    p1.mana_pool.add(ManaType.COLORLESS, 2)
    p1.mana_pool.add(ManaType.RED, 1)
    cast_spell(game, p1, bolt)
    assert not game.stack.is_empty()
