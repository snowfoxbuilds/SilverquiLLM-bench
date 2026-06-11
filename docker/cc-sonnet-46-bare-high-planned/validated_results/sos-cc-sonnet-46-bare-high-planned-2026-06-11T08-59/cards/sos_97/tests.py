"""Tests for Ral Zarek, Guest Lecturer (sos_97)."""

from __future__ import annotations

import random

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


def _setup():
    game = create_game()
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    return game


def _get_ability(ral, index):
    """Return the effect function for a loyalty ability by index."""
    return ral.get_loyalty_abilities()[index].effect


def test_surveil_2_keeps_or_bins():
    """+1 Surveil 2: player looks at top 2 and chooses graveyard or keep."""
    game = _setup()
    p0, p1 = game.players

    ral = RalZarekGuestLecturer()
    ral.owner = p0
    ral.controller = p0
    set_board_state(game, 0, battlefield=[ral])

    card_a = Instant(name="CardA", mana_cost=ManaCost(generic=1))
    card_b = Instant(name="CardB", mana_cost=ManaCost(generic=2))
    lib = game.get_library(p0)
    # Add bottom→top: card_b (bottom), card_a (top)
    lib.add(card_b, position="bottom")
    lib.add(card_a, position="top")

    # Script: keep card_a, discard card_b (say No = graveyard for card_b)
    # Effect processes surveiled in order: first card_a (top), then card_b (next)
    p0._script.appendleft(False)  # consumed second: card_b → graveyard
    p0._script.appendleft(True)   # consumed first: card_a → keep

    effect = _get_ability(ral, 0)
    effect(game)

    assert game.get_library(p0).get_all()[-1] is card_a, "card_a should be back on top"
    assert game.get_graveyard(p0).contains(card_b), "card_b should be in graveyard"


def test_minus1_target_players_discard():
    """-1: Target players each discard a card."""
    game = _setup()
    p0, p1 = game.players

    ral = RalZarekGuestLecturer()
    ral.owner = p0
    ral.controller = p0
    ral.loyalty = 5  # enough for -1

    # Give p1 a card in hand
    hand_card = Creature(name="VictimCard", base_power=1, base_toughness=1)
    hand_card.owner = p1
    hand_card.controller = p1
    p1.zones[Zone.HAND].add(hand_card)

    # Set chosen_targets = [p1]
    ral.chosen_targets = [p1]

    # Script: p1 chooses hand_card to discard
    p1._script.appendleft(hand_card)

    effect = _get_ability(ral, 1)
    effect(game)

    assert game.get_graveyard(p1).contains(hand_card), "p1's card should be discarded"


def test_minus2_reanimates_creature_mv3_or_less():
    """-2: Return creature card with MV ≤ 3 from graveyard to battlefield."""
    game = _setup()
    p0, p1 = game.players

    ral = RalZarekGuestLecturer()
    ral.owner = p0
    ral.controller = p0
    ral.loyalty = 4

    creature = Creature(name="Zombie", base_power=2, base_toughness=2,
                        mana_cost=ManaCost(generic=2))
    creature.owner = p0
    creature.controller = p0
    set_board_state(game, 0, graveyard=[creature])

    ral.chosen_targets = [creature]

    effect = _get_ability(ral, 2)
    effect(game)

    assert game.get_battlefield(p0).contains(creature), "Creature should be on battlefield"
    assert not game.get_graveyard(p0).contains(creature)


def test_minus2_does_not_reanimate_mv4():
    """-2: Does not return creature with MV > 3."""
    game = _setup()
    p0, p1 = game.players

    ral = RalZarekGuestLecturer()
    ral.owner = p0
    ral.controller = p0
    ral.loyalty = 4

    big_creature = Creature(name="BigZombie", base_power=4, base_toughness=4,
                             mana_cost=ManaCost(generic=4))
    big_creature.owner = p0
    big_creature.controller = p0
    set_board_state(game, 0, graveyard=[big_creature])

    ral.chosen_targets = [big_creature]

    effect = _get_ability(ral, 2)
    effect(game)

    assert game.get_graveyard(p0).contains(big_creature), "Big creature should stay in graveyard"


def test_minus7_skips_turns_by_heads():
    """-7: Flip 5 coins; target opponent skips X turns where X = heads."""
    game = _setup()
    p0, p1 = game.players

    ral = RalZarekGuestLecturer()
    ral.owner = p0
    ral.controller = p0
    ral.loyalty = 10  # enough for -7

    # Seed RNG to always get heads (1) for deterministic test: 5 heads
    game.rng = random.Random()
    game.rng.seed(42)  # This seed gives specific results; let's count
    # Actually, seed the RNG to return all-heads by using a fixed sequence
    # We'll use randint mock approach by setting a predictable sequence
    # Easier: just count what seed 42 gives
    temp_rng = random.Random(42)
    expected_heads = sum(temp_rng.randint(0, 1) for _ in range(5))
    game.rng.seed(42)  # reset to same seed

    ral.chosen_targets = [p1]
    if not hasattr(p1, "skip_turns"):
        p1.skip_turns = 0

    effect = _get_ability(ral, 3)
    effect(game)

    assert p1.skip_turns == expected_heads, (
        f"Expected {expected_heads} skipped turns, got {p1.skip_turns}"
    )
