"""Tests for engine/game.py — Game setup, helper actions, and the full game loop.

Verifies:
- create_game: life set to 20, decks placed in libraries, 7 cards drawn each,
  active player set to player1.
- deal_damage: damage to player (life reduced), damage to creature (damage_marked),
  zero/negative amount no-op.
- destroy: permanent moved to owner's graveyard, indestructible prevents destruction,
  replacement effects consulted.
- sacrifice: permanent moved to owner's graveyard.
- exile: object moved to exile zone from various source zones.
- draw_card: top of library moved to hand.
- draw_card on empty library: player.drawn_from_empty_library set to True.
- discard: card from hand to owner's graveyard.
- create_token: token added to battlefield with is_token flag, owner/controller set.
- add_counter / remove_counter: counter manipulation on creatures and generics.
- tap / untap: tapped state changed.
- run_game: basic game runs to completion.
- run_game: player losing at 0 life.
- run_game: max turn limit prevents infinite loop.
- Integration: create game, run one full turn, verify phase progression and card draw.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.card import CardImpl, Creature
from engine.game import (
    MAX_TURNS,
    add_counter,
    create_game,
    create_token,
    deal_damage,
    destroy,
    discard,
    draw_card,
    exile,
    remove_counter,
    run_game,
    sacrifice,
    tap,
    untap,
)
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, Keyword, Phase, Step, Zone


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


def _make_deck(size: int = 20, prefix: str = "Card") -> list[CardImpl]:
    """Create a deck of simple cards."""
    return [_make_card(f"{prefix}_{i}") for i in range(size)]


def _make_game(
    deck_size: int = 20,
    p1_script: list | None = None,
    p2_script: list | None = None,
) -> tuple[GameState, DeterministicPlayer, DeterministicPlayer]:
    """Create a game with two players and simple decks via create_game."""
    p1 = DeterministicPlayer("Alice", p1_script or [])
    p2 = DeterministicPlayer("Bob", p2_script or [])
    deck1 = _make_deck(deck_size, "P1Card")
    deck2 = _make_deck(deck_size, "P2Card")
    game = create_game(p1, p2, deck1, deck2)
    return game, p1, p2


def _make_bare_game(
    p1_script: list | None = None,
    p2_script: list | None = None,
    p1_life: int = 20,
    p2_life: int = 20,
) -> tuple[GameState, DeterministicPlayer, DeterministicPlayer]:
    """Create a bare GameState (no create_game) for unit-testing helpers."""
    p1 = DeterministicPlayer("Alice", p1_script or [], life=p1_life)
    p2 = DeterministicPlayer("Bob", p2_script or [], life=p2_life)
    game = GameState([p1, p2])
    return game, p1, p2


# ===========================================================================
# create_game
# ===========================================================================
class TestCreateGame:
    """Tests for create_game()."""

    def test_life_set_to_20_each(self) -> None:
        """Both players' life totals should be 20 after game creation."""
        game, p1, p2 = _make_game()
        assert p1.life == 20
        assert p2.life == 20

    def test_decks_placed_in_libraries(self) -> None:
        """After creation, libraries should contain the remaining cards (deck_size - 7)."""
        deck_size = 20
        game, p1, p2 = _make_game(deck_size=deck_size)
        assert len(p1.zones[Zone.LIBRARY]) == deck_size - 7
        assert len(p2.zones[Zone.LIBRARY]) == deck_size - 7

    def test_seven_cards_drawn_each(self) -> None:
        """Each player should have 7 cards in hand after game creation."""
        game, p1, p2 = _make_game()
        assert len(p1.zones[Zone.HAND]) == 7
        assert len(p2.zones[Zone.HAND]) == 7

    def test_active_player_is_player1(self) -> None:
        """The active player should be player1 after game creation."""
        game, p1, p2 = _make_game()
        assert game.active_player is p1
        assert game.active_player_index == 0

    def test_card_ownership_set(self) -> None:
        """Cards in player1's hand should have owner = player1."""
        game, p1, p2 = _make_game()
        for card in p1.zones[Zone.HAND].get_all():
            assert card.owner is p1
            assert card.controller is p1
        for card in p2.zones[Zone.HAND].get_all():
            assert card.owner is p2
            assert card.controller is p2

    def test_library_cards_ownership(self) -> None:
        """Cards remaining in libraries should retain correct ownership."""
        game, p1, p2 = _make_game()
        for card in p1.zones[Zone.LIBRARY].get_all():
            assert card.owner is p1
        for card in p2.zones[Zone.LIBRARY].get_all():
            assert card.owner is p2

    def test_initial_phase_is_beginning_untap(self) -> None:
        """Game should start at BEGINNING/UNTAP phase."""
        game, _, _ = _make_game()
        assert game.phase == Phase.BEGINNING
        assert game.step == Step.UNTAP

    def test_initial_turn_number_is_1(self) -> None:
        """Turn number should be 1 at start."""
        game, _, _ = _make_game()
        assert game.turn_number == 1

    def test_small_deck_draw_seven(self) -> None:
        """With deck of exactly 7, library should be empty after creation."""
        game, p1, p2 = _make_game(deck_size=7)
        assert len(p1.zones[Zone.LIBRARY]) == 0
        assert len(p1.zones[Zone.HAND]) == 7
        assert len(p2.zones[Zone.LIBRARY]) == 0
        assert len(p2.zones[Zone.HAND]) == 7


# ===========================================================================
# deal_damage
# ===========================================================================
class TestDealDamage:
    """Tests for deal_damage()."""

    def test_damage_to_player_reduces_life(self) -> None:
        """Dealing damage to a player should reduce their life total."""
        game, p1, p2 = _make_bare_game()
        source = SimpleNamespace(keywords=Keyword(0))
        deal_damage(game, source, p2, 5)
        assert p2.life == 15

    def test_damage_to_creature_marks_damage(self) -> None:
        """Dealing damage to a creature should increase damage_marked."""
        game, p1, p2 = _make_bare_game()
        creature = _make_creature()
        source = SimpleNamespace(keywords=Keyword(0))
        deal_damage(game, source, creature, 3)
        assert creature.damage_marked == 3

    def test_zero_damage_is_noop(self) -> None:
        """Dealing 0 damage should not change life or damage_marked."""
        game, p1, p2 = _make_bare_game()
        source = SimpleNamespace(keywords=Keyword(0))
        deal_damage(game, source, p2, 0)
        assert p2.life == 20

    def test_negative_damage_is_noop(self) -> None:
        """Dealing negative damage should be a no-op."""
        game, p1, p2 = _make_bare_game()
        source = SimpleNamespace(keywords=Keyword(0))
        deal_damage(game, source, p2, -3)
        assert p2.life == 20

    def test_damage_accumulates(self) -> None:
        """Multiple damage events should accumulate on a creature."""
        game, p1, p2 = _make_bare_game()
        creature = _make_creature()
        source = SimpleNamespace(keywords=Keyword(0))
        deal_damage(game, source, creature, 1)
        deal_damage(game, source, creature, 1)
        assert creature.damage_marked == 2

    def test_lifelink_heals_controller(self) -> None:
        """A source with lifelink should heal its controller."""
        game, p1, p2 = _make_bare_game()
        source = SimpleNamespace(keywords=Keyword.LIFELINK, controller=p1)
        deal_damage(game, source, p2, 3)
        assert p1.life == 23
        assert p2.life == 17

    def test_deathtouch_marks_flag(self) -> None:
        """A deathtouch source dealing damage to a creature should set dealt_deathtouch_damage."""
        game, p1, p2 = _make_bare_game()
        creature = _make_creature()
        source = SimpleNamespace(keywords=Keyword.DEATHTOUCH)
        deal_damage(game, source, creature, 1)
        assert creature.dealt_deathtouch_damage is True


# ===========================================================================
# destroy
# ===========================================================================
class TestDestroy:
    """Tests for destroy()."""

    def test_permanent_moved_to_graveyard(self) -> None:
        """Destroying a permanent should move it to owner's graveyard."""
        game, p1, p2 = _make_bare_game()
        creature = _make_creature()
        creature.owner = p1
        creature.controller = p1
        p1.zones[Zone.BATTLEFIELD].add(creature)
        destroy(game, creature)
        assert not p1.zones[Zone.BATTLEFIELD].contains(creature)
        assert p1.zones[Zone.GRAVEYARD].contains(creature)

    def test_indestructible_prevents_destruction(self) -> None:
        """An indestructible permanent should not be destroyed."""
        game, p1, p2 = _make_bare_game()
        creature = _make_creature(keywords=Keyword.INDESTRUCTIBLE)
        creature.owner = p1
        creature.controller = p1
        p1.zones[Zone.BATTLEFIELD].add(creature)
        destroy(game, creature)
        assert p1.zones[Zone.BATTLEFIELD].contains(creature)
        assert not p1.zones[Zone.GRAVEYARD].contains(creature)

    def test_destroy_goes_to_owners_graveyard(self) -> None:
        """Destroying a stolen creature should put it in the owner's graveyard."""
        game, p1, p2 = _make_bare_game()
        creature = _make_creature()
        creature.owner = p1
        creature.controller = p2  # stolen
        p2.zones[Zone.BATTLEFIELD].add(creature)
        destroy(game, creature)
        # Goes to owner's (p1) graveyard, not controller's (p2)
        assert p1.zones[Zone.GRAVEYARD].contains(creature)
        assert not p2.zones[Zone.GRAVEYARD].contains(creature)

    def test_destroy_not_on_battlefield_is_noop(self) -> None:
        """Destroying a permanent not on any battlefield should be a no-op."""
        game, p1, p2 = _make_bare_game()
        creature = _make_creature()
        creature.owner = p1
        creature.controller = p1
        # Not on battlefield; should not raise
        destroy(game, creature)


# ===========================================================================
# sacrifice
# ===========================================================================
class TestSacrifice:
    """Tests for sacrifice()."""

    def test_permanent_moved_to_graveyard(self) -> None:
        """Sacrificing a permanent should move it to owner's graveyard."""
        game, p1, p2 = _make_bare_game()
        creature = _make_creature()
        creature.owner = p1
        creature.controller = p1
        p1.zones[Zone.BATTLEFIELD].add(creature)
        sacrifice(game, p1, creature)
        assert not p1.zones[Zone.BATTLEFIELD].contains(creature)
        assert p1.zones[Zone.GRAVEYARD].contains(creature)

    def test_sacrifice_not_on_battlefield_is_noop(self) -> None:
        """Sacrificing a permanent not on the battlefield should do nothing."""
        game, p1, p2 = _make_bare_game()
        creature = _make_creature()
        sacrifice(game, p1, creature)

    def test_sacrifice_goes_to_owners_graveyard(self) -> None:
        """Sacrificing a stolen creature should put it in the owner's graveyard."""
        game, p1, p2 = _make_bare_game()
        creature = _make_creature()
        creature.owner = p1
        creature.controller = p2
        p2.zones[Zone.BATTLEFIELD].add(creature)
        sacrifice(game, p2, creature)
        assert p1.zones[Zone.GRAVEYARD].contains(creature)
        assert not p2.zones[Zone.GRAVEYARD].contains(creature)


# ===========================================================================
# exile
# ===========================================================================
class TestExile:
    """Tests for exile()."""

    def test_exile_from_battlefield(self) -> None:
        """Exiling from battlefield should move to owner's exile zone."""
        game, p1, p2 = _make_bare_game()
        creature = _make_creature()
        creature.owner = p1
        creature.controller = p1
        p1.zones[Zone.BATTLEFIELD].add(creature)
        exile(game, creature)
        assert not p1.zones[Zone.BATTLEFIELD].contains(creature)
        assert p1.zones[Zone.EXILE].contains(creature)

    def test_exile_from_graveyard(self) -> None:
        """Exiling from graveyard should move to owner's exile zone."""
        game, p1, p2 = _make_bare_game()
        card = _make_card()
        card.owner = p1
        p1.zones[Zone.GRAVEYARD].add(card)
        exile(game, card)
        assert not p1.zones[Zone.GRAVEYARD].contains(card)
        assert p1.zones[Zone.EXILE].contains(card)

    def test_exile_from_hand(self) -> None:
        """Exiling from hand should move to owner's exile zone."""
        game, p1, p2 = _make_bare_game()
        card = _make_card()
        card.owner = p1
        p1.zones[Zone.HAND].add(card)
        exile(game, card)
        assert not p1.zones[Zone.HAND].contains(card)
        assert p1.zones[Zone.EXILE].contains(card)

    def test_exile_object_not_in_any_zone_is_noop(self) -> None:
        """Exiling an object not found in any zone should be a no-op."""
        game, p1, p2 = _make_bare_game()
        card = _make_card()
        exile(game, card)  # Should not raise


# ===========================================================================
# draw_card
# ===========================================================================
class TestDrawCard:
    """Tests for draw_card()."""

    def test_draw_moves_top_of_library_to_hand(self) -> None:
        """Drawing should move the top card of library to hand."""
        game, p1, p2 = _make_bare_game()
        card_a = _make_card("A")
        card_b = _make_card("B")
        p1.zones[Zone.LIBRARY].add(card_a)
        p1.zones[Zone.LIBRARY].add(card_b)
        result = draw_card(game, p1)
        # Top of library is last element (card_b)
        assert result is card_b
        assert p1.zones[Zone.HAND].contains(card_b)
        assert not p1.zones[Zone.LIBRARY].contains(card_b)
        # card_a should still be in library
        assert p1.zones[Zone.LIBRARY].contains(card_a)

    def test_draw_returns_drawn_card(self) -> None:
        """draw_card should return the drawn card."""
        game, p1, _ = _make_bare_game()
        card = _make_card()
        p1.zones[Zone.LIBRARY].add(card)
        result = draw_card(game, p1)
        assert result is card

    def test_draw_from_empty_library_sets_flag(self) -> None:
        """Drawing from an empty library should set drawn_from_empty_library."""
        game, p1, _ = _make_bare_game()
        assert len(p1.zones[Zone.LIBRARY]) == 0
        result = draw_card(game, p1)
        assert result is None
        assert p1.drawn_from_empty_library is True

    def test_draw_from_empty_library_returns_none(self) -> None:
        """Drawing from an empty library should return None."""
        game, p1, _ = _make_bare_game()
        result = draw_card(game, p1)
        assert result is None

    def test_multiple_draws(self) -> None:
        """Drawing multiple times should draw from the top each time."""
        game, p1, _ = _make_bare_game()
        cards = [_make_card(f"C{i}") for i in range(3)]
        for c in cards:
            p1.zones[Zone.LIBRARY].add(c)
        # Library order bottom→top: C0, C1, C2
        r1 = draw_card(game, p1)
        r2 = draw_card(game, p1)
        r3 = draw_card(game, p1)
        assert r1 is cards[2]  # top first
        assert r2 is cards[1]
        assert r3 is cards[0]
        assert len(p1.zones[Zone.HAND]) == 3


# ===========================================================================
# discard
# ===========================================================================
class TestDiscard:
    """Tests for discard()."""

    def test_discard_moves_card_to_graveyard(self) -> None:
        """Discarding should move a card from hand to graveyard."""
        game, p1, _ = _make_bare_game()
        card = _make_card()
        card.owner = p1
        p1.zones[Zone.HAND].add(card)
        discard(game, p1, card)
        assert not p1.zones[Zone.HAND].contains(card)
        assert p1.zones[Zone.GRAVEYARD].contains(card)

    def test_discard_card_not_in_hand_is_noop(self) -> None:
        """Discarding a card not in hand should be a no-op."""
        game, p1, _ = _make_bare_game()
        card = _make_card()
        card.owner = p1
        discard(game, p1, card)  # Should not raise

    def test_discard_goes_to_owners_graveyard(self) -> None:
        """Discarded card should go to its owner's graveyard."""
        game, p1, p2 = _make_bare_game()
        card = _make_card()
        card.owner = p1
        # Card is in p2's hand (e.g., through some effect)
        p2.zones[Zone.HAND].add(card)
        discard(game, p2, card)
        assert p1.zones[Zone.GRAVEYARD].contains(card)


# ===========================================================================
# create_token
# ===========================================================================
class TestCreateToken:
    """Tests for create_token()."""

    def test_token_added_to_battlefield(self) -> None:
        """Creating a token should place it on the battlefield."""
        game, p1, _ = _make_bare_game()
        token = _make_creature("Token")
        create_token(game, p1, token)
        assert p1.zones[Zone.BATTLEFIELD].contains(token)

    def test_token_has_is_token_flag(self) -> None:
        """Created token should have is_token = True."""
        game, p1, _ = _make_bare_game()
        token = _make_creature("Token")
        create_token(game, p1, token)
        assert token.is_token is True

    def test_token_owner_and_controller_set(self) -> None:
        """Token's owner and controller should be set to the creating player."""
        game, p1, _ = _make_bare_game()
        token = _make_creature("Token")
        create_token(game, p1, token)
        assert token.owner is p1
        assert token.controller is p1


# ===========================================================================
# add_counter / remove_counter
# ===========================================================================
class TestCounters:
    """Tests for add_counter() and remove_counter()."""

    def test_add_plus_one_counter(self) -> None:
        """Adding +1/+1 counters should increase plus_one_counters."""
        game, _, _ = _make_bare_game()
        creature = _make_creature()
        add_counter(game, creature, "+1/+1", 2)
        assert creature.plus_one_counters == 2

    def test_add_minus_one_counter(self) -> None:
        """Adding -1/-1 counters should increase minus_one_counters."""
        game, _, _ = _make_bare_game()
        creature = _make_creature()
        add_counter(game, creature, "-1/-1", 1)
        assert creature.minus_one_counters == 1

    def test_add_generic_counter(self) -> None:
        """Adding a generic counter type should use the counters dict."""
        game, _, _ = _make_bare_game()
        obj = SimpleNamespace()
        add_counter(game, obj, "charge", 3)
        assert obj.counters["charge"] == 3

    def test_add_counter_zero_amount_is_noop(self) -> None:
        """Adding 0 counters should not change anything."""
        game, _, _ = _make_bare_game()
        creature = _make_creature()
        add_counter(game, creature, "+1/+1", 0)
        assert creature.plus_one_counters == 0

    def test_remove_plus_one_counter(self) -> None:
        """Removing +1/+1 counters should decrease plus_one_counters."""
        game, _, _ = _make_bare_game()
        creature = _make_creature()
        creature.plus_one_counters = 3
        remove_counter(game, creature, "+1/+1", 2)
        assert creature.plus_one_counters == 1

    def test_remove_counter_does_not_go_below_zero(self) -> None:
        """Removing more counters than present should floor at 0."""
        game, _, _ = _make_bare_game()
        creature = _make_creature()
        creature.plus_one_counters = 1
        remove_counter(game, creature, "+1/+1", 5)
        assert creature.plus_one_counters == 0

    def test_remove_generic_counter(self) -> None:
        """Removing generic counters should work via the counters dict."""
        game, _, _ = _make_bare_game()
        obj = SimpleNamespace(counters={"charge": 5})
        remove_counter(game, obj, "charge", 2)
        assert obj.counters["charge"] == 3

    def test_add_loyalty_counter(self) -> None:
        """Adding loyalty counters should increase loyalty attribute."""
        from engine.card import Planeswalker
        game, _, _ = _make_bare_game()
        pw = Planeswalker(name="TestPW", starting_loyalty=3)
        add_counter(game, pw, "loyalty", 2)
        assert pw.loyalty == 5

    def test_remove_loyalty_counter(self) -> None:
        """Removing loyalty counters should decrease loyalty attribute."""
        from engine.card import Planeswalker
        game, _, _ = _make_bare_game()
        pw = Planeswalker(name="TestPW", starting_loyalty=4)
        remove_counter(game, pw, "loyalty", 2)
        assert pw.loyalty == 2

    def test_add_counter_accumulates(self) -> None:
        """Multiple add_counter calls should accumulate."""
        game, _, _ = _make_bare_game()
        creature = _make_creature()
        add_counter(game, creature, "+1/+1", 1)
        add_counter(game, creature, "+1/+1", 2)
        assert creature.plus_one_counters == 3


# ===========================================================================
# tap / untap
# ===========================================================================
class TestTapUntap:
    """Tests for tap() and untap()."""

    def test_tap_sets_is_tapped_true(self) -> None:
        """Tapping a permanent should set is_tapped = True."""
        game, _, _ = _make_bare_game()
        creature = _make_creature()
        creature.is_tapped = False
        tap(game, creature)
        assert creature.is_tapped is True

    def test_untap_sets_is_tapped_false(self) -> None:
        """Untapping a permanent should set is_tapped = False."""
        game, _, _ = _make_bare_game()
        creature = _make_creature()
        creature.is_tapped = True
        untap(game, creature)
        assert creature.is_tapped is False

    def test_tap_already_tapped_stays_tapped(self) -> None:
        """Tapping an already tapped permanent should keep it tapped."""
        game, _, _ = _make_bare_game()
        creature = _make_creature()
        creature.is_tapped = True
        tap(game, creature)
        assert creature.is_tapped is True

    def test_untap_already_untapped_stays_untapped(self) -> None:
        """Untapping an already untapped permanent should keep it untapped."""
        game, _, _ = _make_bare_game()
        creature = _make_creature()
        creature.is_tapped = False
        untap(game, creature)
        assert creature.is_tapped is False

    def test_tap_object_without_is_tapped_is_noop(self) -> None:
        """Tapping an object without is_tapped should be a no-op."""
        game, _, _ = _make_bare_game()
        obj = SimpleNamespace()
        tap(game, obj)  # Should not raise
        assert not hasattr(obj, "is_tapped")

    def test_untap_object_without_is_tapped_is_noop(self) -> None:
        """Untapping an object without is_tapped should be a no-op."""
        game, _, _ = _make_bare_game()
        obj = SimpleNamespace()
        untap(game, obj)  # Should not raise
        assert not hasattr(obj, "is_tapped")


# ===========================================================================
# run_game — basic scenarios
# ===========================================================================
class TestRunGame:
    """Tests for run_game()."""

    def test_player_losing_at_zero_life(self) -> None:
        """A player at 0 life should lose. run_game returns the other player."""
        game, p1, p2 = _make_bare_game()
        # Manually set player2's life to 0 and mark lost so SBAs detect it
        p2.life = 0
        winner = run_game(game)
        assert winner is p1
        assert game.is_game_over is True
        assert p2.has_lost is True

    def test_max_turn_limit_prevents_infinite_loop(self) -> None:
        """Game should end as draw when MAX_TURNS is exceeded.

        The run_game loop exits when turn_number > MAX_TURNS. When we
        pre-set turn_number past the limit, run_game returns None (draw)
        without entering the loop.
        """
        game, p1, p2 = _make_bare_game()
        # Set turn_number beyond MAX_TURNS so the while-loop condition fails
        game.turn_number = MAX_TURNS + 1
        winner = run_game(game)
        # Winner is None (draw) because the loop never runs
        assert winner is None

    def test_both_players_lose_is_draw(self) -> None:
        """If both players lose, the game is a draw (winner is None)."""
        game, p1, p2 = _make_bare_game()
        p1.life = 0
        p2.life = 0
        winner = run_game(game)
        assert game.is_game_over is True
        assert winner is None

    def test_run_game_with_empty_library_player_loses(self) -> None:
        """A player who tries to draw from empty library should lose."""
        # Create game with exactly 7 cards (library will be empty after draw-7)
        game, p1, p2 = _make_game(deck_size=7)
        # After create_game, both libraries are empty.
        # Per MTG rules, the starting player (p1) skips their first draw step,
        # so p1 survives turn 1. On turn 2, p2 (non-starting) draws from
        # empty library → flag set → SBA → p2 loses.
        assert len(p1.zones[Zone.LIBRARY]) == 0
        assert len(p2.zones[Zone.LIBRARY]) == 0
        winner = run_game(game)
        assert game.is_game_over is True
        # p2 should lose (draws from empty library on their draw step, turn 2)
        assert p2.has_lost is True
        assert winner is p1

    def test_max_turns_constant_is_positive(self) -> None:
        """MAX_TURNS should be a positive integer."""
        assert MAX_TURNS > 0


# ===========================================================================
# Integration: create_game + run one full turn
# ===========================================================================
class TestIntegration:
    """Integration tests combining create_game with turn execution."""

    def test_create_game_and_run_one_turn(self) -> None:
        """Create a game and run one full turn; verify turn advances."""
        from engine.turn import run_turn

        game, p1, p2 = _make_game(deck_size=40)
        assert game.turn_number == 1
        assert game.active_player is p1

        hand_before = len(p1.zones[Zone.HAND])
        lib_before = len(p1.zones[Zone.LIBRARY])

        run_turn(game)

        # Turn number should have advanced
        assert game.turn_number == 2
        # Active player should have swapped
        assert game.active_player is p2
        # Per MTG rules, the starting player skips their first draw step,
        # so hand and library sizes should remain unchanged after turn 1.
        assert len(p1.zones[Zone.HAND]) == hand_before
        assert len(p1.zones[Zone.LIBRARY]) == lib_before

    def test_create_game_and_run_two_turns(self) -> None:
        """Create a game and run two full turns; verify alternating active player."""
        from engine.turn import run_turn

        game, p1, p2 = _make_game(deck_size=40)

        run_turn(game)
        assert game.turn_number == 2
        assert game.active_player is p2

        lib_p2_before = len(p2.zones[Zone.LIBRARY])
        run_turn(game)
        assert game.turn_number == 3
        assert game.active_player is p1
        # Player 2 should have drawn during their turn's draw step
        # (library shrank by 1; hand may stay at max due to cleanup discard)
        assert len(p2.zones[Zone.LIBRARY]) == lib_p2_before - 1

    def test_phase_starts_at_beginning_after_turn(self) -> None:
        """After a full turn, phase should reset to BEGINNING/UNTAP."""
        from engine.turn import run_turn

        game, p1, p2 = _make_game(deck_size=40)
        run_turn(game)
        # After run_turn, the game state should be at the start of the next turn
        assert game.phase == Phase.BEGINNING
        assert game.step == Step.UNTAP

    def test_untap_step_untaps_creatures(self) -> None:
        """Creatures on the active player's battlefield should be untapped during untap step."""
        from engine.turn import run_turn

        # The combat step will ask Alice to choose attackers when she has
        # eligible creatures. Provide [] (no attackers) so the turn completes.
        game, p1, p2 = _make_game(deck_size=40, p1_script=[[]])
        creature = _make_creature("TappedBear")
        creature.owner = p1
        creature.controller = p1
        creature.is_tapped = True
        p1.zones[Zone.BATTLEFIELD].add(creature)

        run_turn(game)  # p1's turn

        # After p1's turn, creature should have been untapped during untap step
        assert creature.is_tapped is False

    def test_full_game_ends_on_library_depletion(self) -> None:
        """A game with small decks should eventually end as library is depleted."""
        # 10 cards each: 7 drawn at start + draw per turn = library depletes quickly
        game, p1, p2 = _make_game(deck_size=10)
        winner = run_game(game)
        assert game.is_game_over is True
        # One of them should have lost (drew from empty library)
        assert p1.has_lost or p2.has_lost
