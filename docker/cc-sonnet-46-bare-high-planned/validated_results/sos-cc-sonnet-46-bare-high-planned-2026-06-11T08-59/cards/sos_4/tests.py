"""Tests for Together as One (sos_4)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Instant
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


def _game_with_library_cards(n=10):
    """Create game with n dummy cards in each library."""
    libs = [[Instant(name=f"Dummy{i}P{p}") for i in range(n)] for p in range(2)]
    game = create_game(deck1=libs[0], deck2=libs[1])
    # Reset draw flags from initial 7-card draw
    for p in game.players:
        p.drawn_from_empty_library = False
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    return game


def test_x_equals_two_colors():
    """With two colors of mana spent, X = 2: draw 2, deal 2, gain 2."""
    game = _game_with_library_cards()
    p0, p1 = game.players

    card = TogetherAsOne()
    card.controller = p0
    card.colors_spent = [ManaType.WHITE, ManaType.BLUE]
    card.chosen_targets = [p1, p1]

    p0.life = 20
    p1.life = 20
    hand_before = len(game.get_hand(p1).get_all())

    card.on_resolve(game)

    assert len(game.get_hand(p1).get_all()) == hand_before + 2
    assert p1.life == 18   # took 2 damage
    assert p0.life == 22   # gained 2 life


def test_x_equals_zero_colorless():
    """With only colorless mana spent, X = 0 (all effects do nothing)."""
    game = _game_with_library_cards()
    p0, p1 = game.players

    card = TogetherAsOne()
    card.controller = p0
    card.colors_spent = []
    card.chosen_targets = [p1, p0]

    p0.life = 20
    p1.life = 20
    hand_before = len(game.get_hand(p1).get_all())

    card.on_resolve(game)

    assert len(game.get_hand(p1).get_all()) == hand_before
    assert p0.life == 20
    assert p1.life == 20


def test_x_equals_five_max():
    """With five colors spent, X = 5: draw 5, deal 5, gain 5."""
    game = _game_with_library_cards(n=20)
    p0, p1 = game.players

    card = TogetherAsOne()
    card.controller = p0
    card.colors_spent = [
        ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN
    ]
    card.chosen_targets = [p1, p1]

    p0.life = 20
    p1.life = 20
    hand_before = len(game.get_hand(p1).get_all())

    card.on_resolve(game)

    assert len(game.get_hand(p1).get_all()) == hand_before + 5
    assert p1.life == 15
    assert p0.life == 25


def test_damage_to_creature():
    """X damage can target a creature."""
    game = _game_with_library_cards()
    p0, p1 = game.players

    creature = Creature(name="Bear", base_power=2, base_toughness=2)
    set_board_state(game, 1, battlefield=[creature])

    card = TogetherAsOne()
    card.controller = p0
    card.colors_spent = [ManaType.RED]  # X = 1
    card.chosen_targets = [p0, creature]

    p0.life = 20
    card.on_resolve(game)

    assert creature.damage_marked == 1
    assert p0.life == 21  # gained 1 life
