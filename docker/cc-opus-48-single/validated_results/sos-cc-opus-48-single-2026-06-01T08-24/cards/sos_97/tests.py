"""Tests for SOS 97 — Ral Zarek, Guest Lecturer.

Ral Zarek, Guest Lecturer is a {1}{B}{B} Legendary Planeswalker — Ral with
starting loyalty 3 and four loyalty abilities:

1. ``+1: Surveil 2.`` — look at the top two cards of your library, then put
   any number of them into your graveyard and the rest back on top in any
   order.
2. ``−1: Any number of target players each discard a card.``
3. ``−2: Return target creature card with mana value 3 or less from your
   graveyard to the battlefield.``
4. ``−7: Flip five coins. Target opponent skips their next X turns, where X is
   the number of coins that came up heads.``

These define the TDD contract; ``card_impl.py`` is a stub, so the behavioural
tests are expected to fail until the card is implemented.

Conventions followed (cf. fdn_134 Ajani planeswalker, fdn_53 surveil):
- Loyalty abilities are exposed via ``get_loyalty_abilities()`` returning
  ``LoyaltyAbility`` dataclasses (``loyalty_cost`` + ``effect(game)``).
- A loyalty ability's target is supplied to the effect via the planeswalker's
  ``chosen_targets`` / ``_resolve_target`` attribute (per Ajani's pattern).
- Surveil: the top of the library is the END of the zone list; the controller
  uses ``choose_yes_no`` to decide whether each examined card goes to the
  graveyard.
"""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Instant, LoyaltyAbility, Planeswalker
from engine.types import (
    CardType,
    ManaCost,
    Phase,
    Step,
    Supertype,
    Zone,
)
from test_utils import advance_to_phase, create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _creature(name: str, cost: str) -> Creature:
    """A vanilla creature card with the given mana cost string."""
    c = Creature(name=name, mana_cost=ManaCost.parse(cost), base_power=2, base_toughness=2)
    return c


def _instant(name: str = "Test Instant") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{1}{U}"))


def _ability_by_cost(card: RalZarekGuestLecturer, cost: int) -> LoyaltyAbility:
    """Return the loyalty ability whose loyalty_cost matches *cost*."""
    for ab in card.get_loyalty_abilities():
        if ab.loyalty_cost == cost:
            return ab
    raise AssertionError(f"No loyalty ability with loyalty_cost {cost}")


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestRalProperties:
    """Static card data should match the SOS 97 spec."""

    def test_is_planeswalker(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert isinstance(card, Planeswalker)
        assert CardType.PLANESWALKER in card.card_types

    def test_name(self) -> None:
        assert RalZarekGuestLecturer(owner=None).name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        assert RalZarekGuestLecturer(owner=None).mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in RalZarekGuestLecturer(owner=None).supertypes

    def test_is_ral_subtype(self) -> None:
        assert "Ral" in RalZarekGuestLecturer(owner=None).subtypes

    def test_starting_loyalty_is_three(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3
        assert card.loyalty == 3


# ---------------------------------------------------------------------------
# Loyalty ability declaration
# ---------------------------------------------------------------------------


class TestRalLoyaltyAbilityDeclaration:
    """get_loyalty_abilities() should expose all four printed abilities."""

    def test_returns_four_abilities(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        assert len(abilities) == 4

    def test_each_is_loyalty_ability(self) -> None:
        for ab in RalZarekGuestLecturer(owner=None).get_loyalty_abilities():
            assert isinstance(ab, LoyaltyAbility)

    def test_loyalty_costs_match_spec(self) -> None:
        costs = sorted(
            ab.loyalty_cost
            for ab in RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        )
        assert costs == [-7, -2, -1, 1]


# ---------------------------------------------------------------------------
# +1: Surveil 2
# ---------------------------------------------------------------------------


class TestRalSurveil:
    """+1: Surveil 2 — examine the top two cards, put any number into the
    graveyard, the rest back on top."""

    def test_surveil_puts_both_chosen_cards_into_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        top1, top2 = _instant("Top1"), _instant("Top2")
        # Library order: deeper cards first, top of library is the LAST element.
        set_board_state(game, 0, battlefield=[card])
        lib = game.get_library(p1)
        for c in [_instant("Deep"), top2, top1]:
            c.owner = p1
            c.controller = p1
            lib.add(c)
        # Script controller to put BOTH examined cards into the graveyard.
        p1._script.extend([True, True])
        _ability_by_cost(card, +1).effect(game)
        gy = game.get_graveyard(p1).get_all()
        assert top1 in gy
        assert top2 in gy

    def test_surveil_keeps_cards_on_top_when_declined(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        top1, top2 = _instant("Top1"), _instant("Top2")
        set_board_state(game, 0, battlefield=[card])
        lib = game.get_library(p1)
        for c in [_instant("Deep"), top2, top1]:
            c.owner = p1
            c.controller = p1
            lib.add(c)
        before = len(lib.get_all())
        # Decline to bin either card.
        p1._script.extend([False, False])
        _ability_by_cost(card, +1).effect(game)
        # No cards left the library; graveyard is unchanged.
        assert len(game.get_library(p1).get_all()) == before
        assert len(game.get_graveyard(p1).get_all()) == 0

    def test_surveil_with_fewer_than_two_cards_does_not_raise(self) -> None:
        """A near-empty library (one card) must not crash Surveil 2."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        lib = game.get_library(p1)
        only = _instant("Only")
        only.owner = p1
        only.controller = p1
        lib.add(only)
        # Provide a generous answer queue; effect should examine only one card.
        p1._script.extend([False, False])
        _ability_by_cost(card, +1).effect(game)
        # Card stays in the library since it was not binned.
        assert game.get_library(p1).contains(only)

    def test_surveil_empty_library_does_not_raise(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        # Empty library — nothing to surveil.
        _ability_by_cost(card, +1).effect(game)
        assert len(game.get_graveyard(p1).get_all()) == 0


# ---------------------------------------------------------------------------
# -1: Any number of target players each discard a card
# ---------------------------------------------------------------------------


class TestRalDiscard:
    """−1: Any number of target players each discard a card."""

    def test_targeted_player_discards_a_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        victim_card = _instant("Doomed")
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[victim_card])
        # Opponent will be made to choose which card to discard.
        p2._script.append(victim_card)
        card.chosen_targets = [p2]
        card._resolve_target = p2
        _ability_by_cost(card, -1).effect(game)
        assert not game.get_hand(p2).contains(victim_card)
        assert game.get_graveyard(p2).contains(victim_card)

    def test_no_targets_is_a_noop(self) -> None:
        """With zero chosen target players, nobody discards and nothing raises."""
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        kept = _instant("Kept")
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[kept])
        card.chosen_targets = []
        _ability_by_cost(card, -1).effect(game)
        assert game.get_hand(p2).contains(kept)

    def test_targeted_player_with_empty_hand_does_not_raise(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[])
        card.chosen_targets = [p2]
        card._resolve_target = p2
        _ability_by_cost(card, -1).effect(game)
        assert len(game.get_hand(p2).get_all()) == 0


# ---------------------------------------------------------------------------
# -2: Reanimate a low-mana-value creature from your graveyard
# ---------------------------------------------------------------------------


class TestRalReanimate:
    """−2: Return target creature card with mana value 3 or less from your
    graveyard to the battlefield."""

    def test_returns_low_mv_creature_to_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = _creature("Goblin", "{1}{R}")  # mana value 2
        set_board_state(game, 0, battlefield=[card], graveyard=[target])
        card.chosen_targets = [target]
        card._resolve_target = target
        _ability_by_cost(card, -2).effect(game)
        assert game.get_battlefield(p1).contains(target)
        assert not game.get_graveyard(p1).contains(target)

    def test_mv_exactly_three_is_legal(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = _creature("Bear Cavalry", "{1}{B}{B}")  # mana value 3
        set_board_state(game, 0, battlefield=[card], graveyard=[target])
        card.chosen_targets = [target]
        card._resolve_target = target
        _ability_by_cost(card, -2).effect(game)
        assert game.get_battlefield(p1).contains(target)

    def test_target_filter_rejects_high_mv_creature(self) -> None:
        """A creature with mana value 4+ is not a legal target for the −2."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        big = _creature("Dragon", "{2}{R}{R}")  # mana value 4
        # Resolve the −2 with the big creature as the (illegal) chosen target.
        set_board_state(game, 0, battlefield=[card], graveyard=[big])
        card.chosen_targets = [big]
        card._resolve_target = big
        _ability_by_cost(card, -2).effect(game)
        # An mv-4 creature must NOT be reanimated.
        assert not game.get_battlefield(p1).contains(big)
        assert game.get_graveyard(p1).contains(big)

    def test_target_filter_rejects_noncreature(self) -> None:
        """A noncreature card (e.g. an instant) is not a legal target."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        spell = _instant("Bolt")  # mana value 2 but not a creature
        set_board_state(game, 0, battlefield=[card], graveyard=[spell])
        card.chosen_targets = [spell]
        card._resolve_target = spell
        _ability_by_cost(card, -2).effect(game)
        assert not game.get_battlefield(p1).contains(spell)
        assert game.get_graveyard(p1).contains(spell)

    def test_only_your_graveyard(self) -> None:
        """A low-mv creature in the OPPONENT's graveyard is not a legal target."""
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        opp_creature = _creature("Their Goblin", "{R}")  # mana value 1
        opp_creature.owner = p2
        opp_creature.controller = p2
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, graveyard=[opp_creature])
        card.chosen_targets = [opp_creature]
        card._resolve_target = opp_creature
        _ability_by_cost(card, -2).effect(game)
        # It must not enter your battlefield.
        assert not game.get_battlefield(p1).contains(opp_creature)

    def test_no_target_chosen_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        creature = _creature("Goblin", "{R}")
        set_board_state(game, 0, battlefield=[card], graveyard=[creature])
        # No chosen target.
        _ability_by_cost(card, -2).effect(game)
        assert game.get_graveyard(p1).contains(creature)
        assert not game.get_battlefield(p1).contains(creature)


# ---------------------------------------------------------------------------
# -7: Ultimate (coin flips + skip turns)
# ---------------------------------------------------------------------------


class TestRalUltimate:
    """−7: Flip five coins. Target opponent skips their next X turns.

    The engine now exposes a deterministic coin-flip primitive
    (``GameState.flip_coin(player)``, scriptable through the controller's
    ``DeterministicPlayer`` yes/no script) and a per-player ``skipped_turns``
    counter consumed by ``advance_phase``. These let us force a known number
    of heads (X) and assert the opponent's queued skip count, as well as that
    the skip is actually consumed by the turn loop."""

    def test_ultimate_loyalty_cost_is_minus_seven(self) -> None:
        ab = _ability_by_cost(RalZarekGuestLecturer(owner=None), -7)
        assert ab.loyalty_cost == -7

    def test_ultimate_resolution_does_not_raise(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.chosen_targets = [p2]
        card._resolve_target = p2
        # Should not raise regardless of how coins land.
        _ability_by_cost(card, -7).effect(game)

    def test_ultimate_forced_head_count_sets_skipped_turns(self) -> None:
        """Scripting three heads (and two tails) makes X==3 and queues exactly
        3 skipped turns on the target opponent."""
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.chosen_targets = [p2]
        card._resolve_target = p2
        # The controller (p1) supplies the five coin-flip results via its
        # DeterministicPlayer yes/no script: three heads, two tails -> X == 3.
        p1._script.extend([True, True, True, False, False])
        assert p2.skipped_turns == 0  # baseline before resolution
        _ability_by_cost(card, -7).effect(game)
        assert p2.skipped_turns == 3

    def test_ultimate_all_tails_skips_no_turns(self) -> None:
        """Five tails -> X == 0 -> opponent's skipped_turns is unchanged."""
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.chosen_targets = [p2]
        card._resolve_target = p2
        p1._script.extend([False, False, False, False, False])
        _ability_by_cost(card, -7).effect(game)
        assert p2.skipped_turns == 0

    def test_ultimate_all_heads_skips_five_turns(self) -> None:
        """Five heads -> X == 5 -> opponent's skipped_turns increases by 5."""
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.chosen_targets = [p2]
        card._resolve_target = p2
        p1._script.extend([True, True, True, True, True])
        _ability_by_cost(card, -7).effect(game)
        assert p2.skipped_turns == 5

    def test_ultimate_adds_to_existing_skipped_turns(self) -> None:
        """The effect adds X to any skips already queued, not overwrites them."""
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.chosen_targets = [p2]
        card._resolve_target = p2
        p2.skipped_turns = 1  # opponent already owed one skip
        p1._script.extend([True, True, False, False, False])  # X == 2
        _ability_by_cost(card, -7).effect(game)
        assert p2.skipped_turns == 3

    def test_skipped_turn_is_consumed_by_turn_rotation(self) -> None:
        """A queued skip is actually consumed when the turn loop rotates to the
        skipped player: the opponent's next turn is handed back to the
        controller and skipped_turns decrements."""
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.chosen_targets = [p2]
        card._resolve_target = p2
        # Force exactly one head -> one skipped turn for p2 (index 1).
        p1._script.extend([True, False, False, False, False])
        _ability_by_cost(card, -7).effect(game)
        assert p2.skipped_turns == 1

        # p1 is the active player on turn 1. Drive to end of turn and wrap:
        # the rotation would make p2 active, but its queued skip is consumed
        # and the turn is handed back to p1.
        assert game.active_player is p1
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()  # wrap to the next turn

        # The skip was consumed: p2 did not get to be the active player.
        assert p2.skipped_turns == 0
        assert game.active_player is p1

    def test_zero_heads_leaves_turn_rotation_unchanged(self) -> None:
        """With X == 0 no skip is queued, so normal rotation hands the next
        turn to the opponent as usual (the skip hook is a no-op)."""
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.chosen_targets = [p2]
        card._resolve_target = p2
        p1._script.extend([False, False, False, False, False])  # X == 0
        _ability_by_cost(card, -7).effect(game)
        assert p2.skipped_turns == 0

        assert game.active_player is p1
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()  # wrap to the next turn

        # No skip queued, so the opponent becomes active normally.
        assert game.active_player is p2
