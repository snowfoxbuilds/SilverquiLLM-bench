"""Tests for Together as One (SOS #4)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


def _vanilla(name: str, p: int = 2, t: int = 2) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{1}{G}"),
        base_power=p,
        base_toughness=t,
    )


def test_is_a_sorcery():
    card = TogetherAsOne()
    assert CardType.SORCERY in card.card_types
    assert card.mana_cost.generic == 6


def test_resolve_with_three_colors():
    game = create_game()
    p1, p2 = game.players
    # Fill p1's library so draws succeed.
    for i in range(5):
        c = _vanilla(f"Lib{i}")
        c.owner = p1
        p1.zones[Zone.LIBRARY].add(c)
    victim = _vanilla("Victim", t=5)
    set_board_state(game, 1, battlefield=[victim])

    card = TogetherAsOne()
    card.controller = p1
    card.colors_spent = ["W", "U", "B"]  # X = 3
    card.chosen_targets = [p1, victim]

    start_hand = len(p1.zones[Zone.HAND].get_all())
    start_life = p1.life
    card.on_resolve(game)

    assert len(p1.zones[Zone.HAND].get_all()) == start_hand + 3
    assert victim.damage_marked == 3
    assert p1.life == start_life + 3


def test_resolve_with_zero_colors_is_noop():
    game = create_game()
    p1, p2 = game.players
    victim = _vanilla("Victim", t=5)
    set_board_state(game, 1, battlefield=[victim])

    card = TogetherAsOne()
    card.controller = p1
    card.colors_spent = []  # X = 0
    card.chosen_targets = [p1, victim]

    start_life = p1.life
    card.on_resolve(game)

    assert victim.damage_marked == 0
    assert p1.life == start_life


def test_colors_spent_as_int_supported():
    card = TogetherAsOne()
    card.colors_spent = 2
    assert card._converge_x() == 2
    card.colors_spent = ["R", "G"]
    assert card._converge_x() == 2


def test_full_cast_counts_distinct_colors():
    game = create_game()
    p1, p2 = game.players
    for i in range(5):
        c = _vanilla(f"Lib{i}")
        c.owner = p1
        p1.zones[Zone.LIBRARY].add(c)
    victim = _vanilla("Victim", t=9)
    set_board_state(game, 1, battlefield=[victim])

    card = TogetherAsOne()
    set_board_state(game, 0, hand=[card])
    # Pay {6} entirely with colored mana of three colors → X = 3.
    p1.mana_pool.add(ManaType.WHITE, 2)
    p1.mana_pool.add(ManaType.BLUE, 2)
    p1.mana_pool.add(ManaType.BLACK, 2)

    from test_utils import cast_spell as cast

    start_life = p1.life
    cast(game, 0, "Together as One", targets=[p1, victim])

    assert victim.damage_marked == 3
    assert p1.life == start_life + 3
