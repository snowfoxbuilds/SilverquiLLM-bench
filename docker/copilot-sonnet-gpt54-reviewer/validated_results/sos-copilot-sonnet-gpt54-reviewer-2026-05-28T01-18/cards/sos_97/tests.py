"""Tests for sos_97 — Ral Zarek, Guest Lecturer.

A Legendary Planeswalker with starting loyalty 3.
  +1: Surveil 2 (look at top 2 cards, any to graveyard, rest on top in any order)
  −1: Any number of target players each discard a card
  −2: Return target creature card with mana value 3 or less from your graveyard
      to the battlefield
  −7: Flip five coins. Target opponent skips their next X turns, where X is the
      number of coins that came up heads.
"""

from __future__ import annotations

import random
from typing import Any
from unittest.mock import patch

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Planeswalker
from engine.types import CardType, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simple_creature(name: str, *, owner: Any = None, cmc: int = 2) -> Creature:
    """Return a minimal creature card with the given name and CMC."""
    c = Creature(
        name=name,
        owner=owner,
        controller=owner,
        base_power=cmc,
        base_toughness=cmc,
    )
    # Assign a mana cost so that `mana_cost.cmc` returns the expected value.
    try:
        cost_str = "{" + "1" * cmc + "}" if cmc > 0 else "{0}"
        c.mana_cost = ManaCost.parse(cost_str)
    except Exception:
        # Fallback: leave default mana cost (cmc=0).
        pass
    return c


# ---------------------------------------------------------------------------
# 1. Static card properties
# ---------------------------------------------------------------------------


class TestRalZarekProperties:
    """Static card data must match the sos_97 spec."""

    def test_is_planeswalker_subclass(self) -> None:
        """RalZarekGuestLecturer must be a Planeswalker instance."""
        card = RalZarekGuestLecturer(owner=None)
        assert isinstance(card, Planeswalker)

    def test_name(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3

    def test_initial_loyalty_equals_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.loyalty == 3

    def test_planeswalker_card_type(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert CardType.PLANESWALKER in card.card_types

    def test_legendary_supertype(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_ral_subtype(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert "Ral" in card.subtypes

    def test_has_four_loyalty_abilities(self) -> None:
        """Ral Zarek has exactly four loyalty abilities."""
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert len(abilities) == 4

    def test_loyalty_costs(self) -> None:
        """Loyalty costs must be +1, −1, −2, −7 in declared order."""
        card = RalZarekGuestLecturer(owner=None)
        costs = [ab.loyalty_cost for ab in card.get_loyalty_abilities()]
        assert costs[0] == 1    # +1: Surveil 2
        assert costs[1] == -1   # −1: Discard
        assert costs[2] == -2   # −2: Reanimate creature
        assert costs[3] == -7   # −7: Coin flip turn skip


# ---------------------------------------------------------------------------
# 2. +1 Ability: Surveil 2
# ---------------------------------------------------------------------------


class TestPlusOneAbilitySurveil:
    """The +1 ability performs Surveil 2: look at top 2 cards of the library;
    put any number in the graveyard, the rest on top in any order."""

    def test_surveil_cards_can_be_sent_to_graveyard(self) -> None:
        """When the surveil effect sends both cards to GY, library shrinks by 2
        and graveyard gains 2."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        card_a = _simple_creature("CardA", owner=p1)
        card_b = _simple_creature("CardB", owner=p1)
        set_board_state(game, 0, graveyard=[], hand=[])
        # Place two cards on top of library (bottom of internal list = bottom of library).
        library = p1.zones[Zone.LIBRARY]
        for c in library.get_all():
            library.remove(c)
        library.add(card_a)
        library.add(card_b)  # card_b is on top

        gy_before = len(p1.zones[Zone.GRAVEYARD].get_all())
        lib_before = len(p1.zones[Zone.LIBRARY].get_all())

        # Simulate: controller decides to send both cards to GY.
        # Implementation should call controller.choose() to decide which
        # cards to keep. We set chosen_targets / chosen_to_graveyard directly.
        ral.chosen_surveil_to_graveyard = [card_a, card_b]
        ral._surveil(game, num=2)

        gy_after = len(p1.zones[Zone.GRAVEYARD].get_all())
        lib_after = len(p1.zones[Zone.LIBRARY].get_all())

        assert gy_after - gy_before == 2
        assert lib_before - lib_after == 2

    def test_surveil_cards_can_remain_on_top(self) -> None:
        """When the controller keeps both cards, library size is unchanged."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        card_a = _simple_creature("CardC", owner=p1)
        card_b = _simple_creature("CardD", owner=p1)
        library = p1.zones[Zone.LIBRARY]
        for c in library.get_all():
            library.remove(c)
        library.add(card_a)
        library.add(card_b)

        lib_before = len(p1.zones[Zone.LIBRARY].get_all())

        # Keep both — none go to GY.
        ral.chosen_surveil_to_graveyard = []
        ral._surveil(game, num=2)

        lib_after = len(p1.zones[Zone.LIBRARY].get_all())
        assert lib_after == lib_before

    def test_surveil_with_empty_library_does_not_raise(self) -> None:
        """Surveiling with an empty library must not raise."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        library = p1.zones[Zone.LIBRARY]
        for c in library.get_all():
            library.remove(c)

        ral.chosen_surveil_to_graveyard = []
        ral._surveil(game, num=2)  # No-op; must not crash.

    def test_plus_one_loyalty_ability_increases_loyalty(self) -> None:
        """Activating the +1 ability increases loyalty from 3 to 4."""
        from engine.abilities import LoyaltyAbilityInstance, activate_ability

        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        # Place Ral on the battlefield so timing check passes.
        game.get_battlefield(p1).add(ral)
        # Set sorcery-speed timing
        from engine.types import Phase
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        # Provide an empty surveil choice: keep everything on top.
        ral.chosen_surveil_to_graveyard = []

        ability = ral.get_loyalty_abilities()[0]  # +1 ability
        loyalty_instance = LoyaltyAbilityInstance(
            source=ral,
            controller=p1,
            loyalty_cost=ability.loyalty_cost,
            effect=ability.effect,
        )

        from engine.abilities import clear_loyalty_tracking
        clear_loyalty_tracking()

        activate_ability(game, p1, loyalty_instance)
        # Resolve the stack object.
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert ral.loyalty == 4


# ---------------------------------------------------------------------------
# 3. −1 Ability: Target players each discard a card
# ---------------------------------------------------------------------------


class TestMinusOneAbilityDiscard:
    """The −1 ability: Any number of target players each discard a card."""

    def test_single_target_player_discards_a_card(self) -> None:
        """If one player is targeted, that player discards one card."""
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        discard_target = _simple_creature("HandCard", owner=p2)
        set_board_state(game, 1, hand=[discard_target])

        hand_before = len(p2.zones[Zone.HAND].get_all())
        gy_before = len(p2.zones[Zone.GRAVEYARD].get_all())

        ral.chosen_targets = [p2]
        ral._minus_one_discard(game)

        hand_after = len(p2.zones[Zone.HAND].get_all())
        gy_after = len(p2.zones[Zone.GRAVEYARD].get_all())

        assert hand_before - hand_after == 1
        assert gy_after - gy_before == 1

    def test_zero_targets_discards_nothing(self) -> None:
        """If no targets are chosen, no player discards."""
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        card_in_hand = _simple_creature("Keeper", owner=p2)
        set_board_state(game, 1, hand=[card_in_hand])

        hand_before = len(p2.zones[Zone.HAND].get_all())

        ral.chosen_targets = []
        ral._minus_one_discard(game)

        assert len(p2.zones[Zone.HAND].get_all()) == hand_before

    def test_both_players_as_targets_both_discard(self) -> None:
        """If both players are targeted, both discard one card each."""
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        p1_card = _simple_creature("P1Card", owner=p1)
        p2_card = _simple_creature("P2Card", owner=p2)
        set_board_state(game, 0, hand=[p1_card])
        set_board_state(game, 1, hand=[p2_card])

        p1_hand_before = len(p1.zones[Zone.HAND].get_all())
        p2_hand_before = len(p2.zones[Zone.HAND].get_all())

        ral.chosen_targets = [p1, p2]
        ral._minus_one_discard(game)

        assert len(p1.zones[Zone.HAND].get_all()) == p1_hand_before - 1
        assert len(p2.zones[Zone.HAND].get_all()) == p2_hand_before - 1

    def test_discard_with_empty_hand_is_noop(self) -> None:
        """If the targeted player has no cards in hand, nothing happens."""
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        set_board_state(game, 1, hand=[])

        gy_before = len(p2.zones[Zone.GRAVEYARD].get_all())

        ral.chosen_targets = [p2]
        ral._minus_one_discard(game)

        assert len(p2.zones[Zone.GRAVEYARD].get_all()) == gy_before

    def test_minus_one_decreases_loyalty(self) -> None:
        """Activating the −1 ability reduces loyalty by 1 (3 → 2)."""
        from engine.abilities import LoyaltyAbilityInstance, activate_ability, clear_loyalty_tracking

        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(ral)
        from engine.types import Phase
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        # Target p2, who has a card to discard.
        discard_card = _simple_creature("Victim", owner=p2)
        set_board_state(game, 1, hand=[discard_card])
        ral.chosen_targets = [p2]

        ability = ral.get_loyalty_abilities()[1]  # −1 ability
        loyalty_instance = LoyaltyAbilityInstance(
            source=ral,
            controller=p1,
            loyalty_cost=ability.loyalty_cost,
            effect=ability.effect,
        )

        clear_loyalty_tracking()
        activate_ability(game, p1, loyalty_instance)
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert ral.loyalty == 2


# ---------------------------------------------------------------------------
# 4. −2 Ability: Reanimate creature with MV ≤ 3
# ---------------------------------------------------------------------------


class TestMinusTwoAbilityReanimate:
    """The −2 ability: Return target creature card with mana value ≤ 3 from
    your graveyard to the battlefield."""

    def test_creature_mv3_returns_to_battlefield(self) -> None:
        """A creature with MV exactly 3 is returned from GY to battlefield."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        creature = Creature(
            name="MV3Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        creature.mana_cost = ManaCost.parse("{1}{B}{B}")  # CMC = 3

        set_board_state(game, 0, graveyard=[creature])

        bf_before = len(game.get_battlefield(p1).get_all())
        gy_before = len(p1.zones[Zone.GRAVEYARD].get_all())

        ral.chosen_targets = [creature]
        ral._minus_two_reanimate(game)

        bf_after = len(game.get_battlefield(p1).get_all())
        gy_after = len(p1.zones[Zone.GRAVEYARD].get_all())

        assert bf_after - bf_before == 1
        assert gy_before - gy_after == 1
        assert game.get_battlefield(p1).contains(creature)

    def test_creature_mv1_returns_to_battlefield(self) -> None:
        """A creature with MV 1 (≤ 3) is returned from GY to battlefield."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        creature = Creature(
            name="OneDrop",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        creature.mana_cost = ManaCost.parse("{B}")  # CMC = 1

        set_board_state(game, 0, graveyard=[creature])
        ral.chosen_targets = [creature]
        ral._minus_two_reanimate(game)

        assert game.get_battlefield(p1).contains(creature)

    def test_no_target_is_noop(self) -> None:
        """If no target is set, the ability is a no-op."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        bf_before = len(game.get_battlefield(p1).get_all())
        ral.chosen_targets = []
        ral._minus_two_reanimate(game)

        assert len(game.get_battlefield(p1).get_all()) == bf_before

    def test_creature_mv_greater_than_3_is_not_valid_target(self) -> None:
        """A creature with MV > 3 should not be a valid target for the −2
        ability.  The get_targets helper (or any similar filtering) must
        exclude it."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        big_creature = Creature(
            name="BigBeast",
            owner=p1,
            controller=p1,
            base_power=5,
            base_toughness=5,
        )
        big_creature.mana_cost = ManaCost.parse("{4}{B}")  # CMC = 5
        set_board_state(game, 0, graveyard=[big_creature])

        # The _minus_two_reanimate method should do nothing if target has MV > 3.
        bf_before = len(game.get_battlefield(p1).get_all())
        ral.chosen_targets = [big_creature]
        ral._minus_two_reanimate(game)

        # Big creature should NOT end up on the battlefield.
        assert not game.get_battlefield(p1).contains(big_creature)
        assert len(game.get_battlefield(p1).get_all()) == bf_before

    def test_non_creature_card_in_graveyard_is_not_reanimated(self) -> None:
        """Non-creature cards in the graveyard are not valid targets."""
        from engine.card import Instant

        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        instant_card = Instant(
            name="LowCMCInstant",
            owner=p1,
            controller=p1,
        )
        instant_card.mana_cost = ManaCost.parse("{B}")  # CMC = 1
        set_board_state(game, 0, graveyard=[instant_card])

        bf_before = len(game.get_battlefield(p1).get_all())
        ral.chosen_targets = [instant_card]
        ral._minus_two_reanimate(game)

        assert not game.get_battlefield(p1).contains(instant_card)
        assert len(game.get_battlefield(p1).get_all()) == bf_before


# ---------------------------------------------------------------------------
# 5. −7 Ability: Coin flips and turn skipping
# ---------------------------------------------------------------------------


class TestMinusSevenAbilityCoinFlip:
    """The −7 ability: Flip 5 coins. Target opponent skips their next X turns
    where X = number of heads."""

    def test_all_heads_skips_five_turns(self) -> None:
        """With all 5 coins heads, the target opponent skips 5 turns."""
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        ral.chosen_targets = [p2]

        # Mock random to always return 0 (heads) for coin flips.
        with patch("random.random", return_value=0.0):
            ral._minus_seven_coin_flip(game)

        # Verify the target has 5 turns to skip recorded.
        skips = getattr(p2, "turns_to_skip", 0)
        assert skips == 5

    def test_all_tails_skips_zero_turns(self) -> None:
        """With 0 coins heads, the target opponent skips 0 turns (no effect)."""
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        ral.chosen_targets = [p2]

        # Mock random to always return 1 (tails).
        with patch("random.random", return_value=1.0):
            ral._minus_seven_coin_flip(game)

        skips = getattr(p2, "turns_to_skip", 0)
        assert skips == 0

    def test_three_heads_skips_three_turns(self) -> None:
        """With 3 heads out of 5 coins, the opponent skips 3 turns."""
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        ral.chosen_targets = [p2]

        # Return 3 heads then 2 tails.
        side_effects = [0.0, 0.0, 0.0, 1.0, 1.0]
        with patch("random.random", side_effect=side_effects):
            ral._minus_seven_coin_flip(game)

        skips = getattr(p2, "turns_to_skip", 0)
        assert skips == 3

    def test_exactly_five_coins_are_flipped(self) -> None:
        """Exactly 5 coin flips are performed."""
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        ral.chosen_targets = [p2]

        flip_count = 0

        def count_flip():
            nonlocal flip_count
            flip_count += 1
            return 0.0  # heads

        with patch("random.random", side_effect=count_flip):
            ral._minus_seven_coin_flip(game)

        assert flip_count == 5

    def test_no_target_does_not_crash(self) -> None:
        """If no target is selected, the ability must not raise."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        ral.chosen_targets = []
        with patch("random.random", return_value=0.0):
            ral._minus_seven_coin_flip(game)  # Should be a no-op or safe noop.


# ---------------------------------------------------------------------------
# 6. Integration: on_resolve dispatches to the correct loyalty ability
# ---------------------------------------------------------------------------


class TestOnResolveDispatch:
    """on_resolve should look at chosen_loyalty_ability and call the matching
    internal method."""

    def test_on_resolve_surveil_via_loyalty_ability_index_0(self) -> None:
        """When the +1 ability resolves, the library/GY change matches surveil."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        card_a = _simple_creature("X1", owner=p1)
        card_b = _simple_creature("X2", owner=p1)
        library = p1.zones[Zone.LIBRARY]
        for c in library.get_all():
            library.remove(c)
        library.add(card_a)
        library.add(card_b)

        gy_before = len(p1.zones[Zone.GRAVEYARD].get_all())

        # Trigger ability effect directly (as engine would after pop from stack).
        abilities = ral.get_loyalty_abilities()
        ral.chosen_surveil_to_graveyard = [card_a, card_b]
        abilities[0].effect(game)

        gy_after = len(p1.zones[Zone.GRAVEYARD].get_all())
        assert gy_after - gy_before == 2

    def test_on_resolve_discard_via_loyalty_ability_index_1(self) -> None:
        """When the −1 ability resolves, the target player loses a hand card."""
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        victim_card = _simple_creature("Victim2", owner=p2)
        set_board_state(game, 1, hand=[victim_card])
        hand_before = len(p2.zones[Zone.HAND].get_all())

        ral.chosen_targets = [p2]
        abilities = ral.get_loyalty_abilities()
        abilities[1].effect(game)

        assert len(p2.zones[Zone.HAND].get_all()) == hand_before - 1

    def test_on_resolve_reanimate_via_loyalty_ability_index_2(self) -> None:
        """When the −2 ability resolves, a MV≤3 creature enters the battlefield."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        creature = Creature(name="Revived", owner=p1, controller=p1, base_power=2, base_toughness=2)
        creature.mana_cost = ManaCost.parse("{G}{G}")  # CMC = 2
        set_board_state(game, 0, graveyard=[creature])

        bf_before = len(game.get_battlefield(p1).get_all())

        ral.chosen_targets = [creature]
        abilities = ral.get_loyalty_abilities()
        abilities[2].effect(game)

        assert len(game.get_battlefield(p1).get_all()) - bf_before == 1
        assert game.get_battlefield(p1).contains(creature)

    def test_on_resolve_coin_flip_via_loyalty_ability_index_3(self) -> None:
        """When the −7 ability resolves, turns_to_skip is updated on the target."""
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        ral.chosen_targets = [p2]
        abilities = ral.get_loyalty_abilities()

        with patch("random.random", return_value=0.0):  # all heads
            abilities[3].effect(game)

        assert getattr(p2, "turns_to_skip", 0) == 5
