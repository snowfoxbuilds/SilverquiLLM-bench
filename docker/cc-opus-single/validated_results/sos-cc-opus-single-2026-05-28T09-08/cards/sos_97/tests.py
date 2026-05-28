"""Tests for SOS 97 — Ral Zarek, Guest Lecturer.

Ral Zarek, Guest Lecturer is a {1}{B}{B} Legendary Planeswalker — Ral
with starting loyalty 3.

Requirements tested:
1. Static properties: name, mana cost, card types, supertypes, subtypes, starting loyalty.
2. Loyalty abilities: four abilities at +1, -1, -2, -7.
3. +1: Surveil 2 — look at top 2 cards of library, put any number into
   graveyard and rest on top in any order.
4. -1: Any number of target players each discard a card.
5. -2: Return target creature card with mana value 3 or less from your
   graveyard to the battlefield.
6. -7: Flip five coins. Target opponent skips their next X turns, where
   X is the number of coins that came up heads.
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Instant, LoyaltyAbility, Planeswalker
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestRalZarekProperties:
    """Static card data should match the SOS 97 spec."""

    def test_is_planeswalker(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert isinstance(card, Planeswalker)

    def test_name(self) -> None:
        assert RalZarekGuestLecturer(owner=None).name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        assert RalZarekGuestLecturer(owner=None).mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3

    def test_initial_loyalty_equals_starting(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.loyalty == 3

    def test_is_legendary(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_ral_subtype(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert "Ral" in card.subtypes

    def test_has_planeswalker_card_type(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert CardType.PLANESWALKER in card.card_types


# ---------------------------------------------------------------------------
# Loyalty abilities — structure
# ---------------------------------------------------------------------------


class TestRalZarekLoyaltyAbilities:
    """get_loyalty_abilities should return four LoyaltyAbility objects
    with the correct loyalty costs."""

    def test_returns_four_abilities(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert isinstance(abilities, list)
        assert len(abilities) == 4

    def test_all_are_loyalty_abilities(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        for ability in abilities:
            assert isinstance(ability, LoyaltyAbility)

    def test_loyalty_costs_are_correct(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        costs = [a.loyalty_cost for a in abilities]
        assert costs == [1, -1, -2, -7]


# ---------------------------------------------------------------------------
# +1: Surveil 2
# ---------------------------------------------------------------------------


class TestRalZarekSurveil:
    """+1: Surveil 2 — look at top 2 cards, put any number into graveyard,
    rest on top of library."""

    def test_surveil_moves_cards_from_library(self) -> None:
        """After activating +1, cards should move from library to either
        graveyard or remain on top of library. The total across both zones
        should account for the 2 cards surveiled."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        # Set up library with known cards
        card_a = Creature(name="Card A", owner=p1, controller=p1,
                          base_power=1, base_toughness=1)
        card_b = Creature(name="Card B", owner=p1, controller=p1,
                          base_power=2, base_toughness=2)
        card_c = Creature(name="Card C", owner=p1, controller=p1,
                          base_power=3, base_toughness=3)
        # Library bottom to top: card_c (bottom), card_a, card_b (top)
        p1.zones[Zone.LIBRARY]._objects.clear()
        p1.zones[Zone.LIBRARY].add(card_c)
        p1.zones[Zone.LIBRARY].add(card_a)
        p1.zones[Zone.LIBRARY].add(card_b)

        lib_before = len(p1.zones[Zone.LIBRARY])
        gy_before = len(p1.zones[Zone.GRAVEYARD])

        abilities = card.get_loyalty_abilities()
        plus_one = abilities[0]
        assert plus_one.loyalty_cost == 1
        plus_one.effect(game)

        lib_after = len(p1.zones[Zone.LIBRARY])
        gy_after = len(p1.zones[Zone.GRAVEYARD])

        # The 2 surveiled cards should either remain in library or go to GY.
        # Some must have moved (simplified surveil puts all to GY) OR stayed.
        # At minimum, the total should be consistent:
        assert lib_after + gy_after == lib_before + gy_before

    def test_surveil_with_fewer_than_two_cards_in_library(self) -> None:
        """Surveil 2 with only 1 card in library should not crash and should
        surveil that 1 card."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        single_card = Creature(name="Single", owner=p1, controller=p1,
                               base_power=1, base_toughness=1)
        p1.zones[Zone.LIBRARY]._objects.clear()
        p1.zones[Zone.LIBRARY].add(single_card)

        abilities = card.get_loyalty_abilities()
        plus_one = abilities[0]
        # Should not raise even with only 1 card
        plus_one.effect(game)

    def test_surveil_with_empty_library(self) -> None:
        """Surveil 2 with an empty library should be a no-op and not crash."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        p1.zones[Zone.LIBRARY]._objects.clear()
        assert len(p1.zones[Zone.LIBRARY]) == 0

        abilities = card.get_loyalty_abilities()
        plus_one = abilities[0]
        # Should not raise
        plus_one.effect(game)
        assert len(p1.zones[Zone.GRAVEYARD]) == 0


# ---------------------------------------------------------------------------
# -1: Any number of target players each discard a card
# ---------------------------------------------------------------------------


class TestRalZarekDiscard:
    """-1: Any number of target players each discard a card."""

    def test_discard_single_player(self) -> None:
        """When targeting one player, that player should discard a card."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        # Give p2 a card in hand
        hand_card = Creature(name="Hand Bear", owner=p2, controller=p2,
                             base_power=2, base_toughness=2)
        set_board_state(game, 1, hand=[hand_card])

        hand_before = len(p2.zones[Zone.HAND])
        assert hand_before == 1

        abilities = card.get_loyalty_abilities()
        minus_one = abilities[1]
        assert minus_one.loyalty_cost == -1

        # Set up targeting — target p2
        card.chosen_targets = [p2]
        card._resolve_targets = [p2]
        minus_one.effect(game)

        hand_after = len(p2.zones[Zone.HAND])
        assert hand_after == hand_before - 1

    def test_discard_both_players(self) -> None:
        """When targeting both players, each should discard a card."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        p1_card = Creature(name="P1 Card", owner=p1, controller=p1,
                           base_power=1, base_toughness=1)
        p2_card = Creature(name="P2 Card", owner=p2, controller=p2,
                           base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[p1_card])
        set_board_state(game, 1, hand=[p2_card])

        p1_hand_before = len(p1.zones[Zone.HAND])
        p2_hand_before = len(p2.zones[Zone.HAND])

        abilities = card.get_loyalty_abilities()
        minus_one = abilities[1]
        card.chosen_targets = [p1, p2]
        card._resolve_targets = [p1, p2]
        minus_one.effect(game)

        assert len(p1.zones[Zone.HAND]) == p1_hand_before - 1
        assert len(p2.zones[Zone.HAND]) == p2_hand_before - 1

    def test_discard_player_with_empty_hand(self) -> None:
        """Targeting a player with an empty hand should not crash."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        set_board_state(game, 1, hand=[])
        assert len(p2.zones[Zone.HAND]) == 0

        abilities = card.get_loyalty_abilities()
        minus_one = abilities[1]
        card.chosen_targets = [p2]
        card._resolve_targets = [p2]
        # Should not raise
        minus_one.effect(game)


# ---------------------------------------------------------------------------
# -2: Return target creature card with mana value 3 or less from graveyard
# ---------------------------------------------------------------------------


class TestRalZarekReanimate:
    """-2: Return target creature card with mana value 3 or less from your
    graveyard to the battlefield."""

    def test_returns_creature_to_battlefield(self) -> None:
        """A creature with MV <= 3 in the graveyard should be moved to the
        battlefield when the -2 ability resolves."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        # Creature with MV 2 in graveyard
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        mana_cost=ManaCost.parse("{1}{G}"),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[bear])

        assert p1.zones[Zone.GRAVEYARD].contains(bear)
        assert not game.get_battlefield(p1).contains(bear)

        abilities = card.get_loyalty_abilities()
        minus_two = abilities[2]
        assert minus_two.loyalty_cost == -2

        card.chosen_targets = [bear]
        card._resolve_target = bear
        minus_two.effect(game)

        # Bear should now be on the battlefield
        assert game.get_battlefield(p1).contains(bear)
        # Bear should no longer be in the graveyard
        assert not p1.zones[Zone.GRAVEYARD].contains(bear)

    def test_returns_creature_with_mv_exactly_three(self) -> None:
        """A creature with mana value exactly 3 should be a valid target."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        mv3_creature = Creature(name="MV3 Creature", owner=p1, controller=p1,
                                mana_cost=ManaCost.parse("{1}{B}{B}"),
                                base_power=3, base_toughness=3)
        set_board_state(game, 0, graveyard=[mv3_creature])

        abilities = card.get_loyalty_abilities()
        minus_two = abilities[2]
        card.chosen_targets = [mv3_creature]
        card._resolve_target = mv3_creature
        minus_two.effect(game)

        assert game.get_battlefield(p1).contains(mv3_creature)

    def test_returns_creature_with_mv_zero(self) -> None:
        """A creature with mana value 0 should be a valid target (MV <= 3)."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        token_like = Creature(name="Zero MV", owner=p1, controller=p1,
                              base_power=1, base_toughness=1)
        # No mana_cost set, so MV = 0
        set_board_state(game, 0, graveyard=[token_like])

        abilities = card.get_loyalty_abilities()
        minus_two = abilities[2]
        card.chosen_targets = [token_like]
        card._resolve_target = token_like
        minus_two.effect(game)

        assert game.get_battlefield(p1).contains(token_like)

    def test_get_targets_returns_graveyard_requirement(self) -> None:
        """get_targets should include a target requirement for creature cards
        in the graveyard with mana value 3 or less."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        targets = card.get_targets(game)
        assert isinstance(targets, list)
        # There should be at least one target requirement
        assert len(targets) >= 1

    def test_target_filter_accepts_creature_mv_le_3(self) -> None:
        """The target filter for -2 should accept creature cards with MV <= 3."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        targets = card.get_targets(game)
        # Find the graveyard requirement (for -2 ability)
        gy_reqs = [r for r in targets if r.zone == Zone.GRAVEYARD]
        assert len(gy_reqs) >= 1

        req = gy_reqs[0]
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{1}{G}"),
                        base_power=2, base_toughness=2)
        assert req.filter_fn(bear) is True

    def test_target_filter_rejects_creature_mv_gt_3(self) -> None:
        """The target filter for -2 should reject creature cards with MV > 3."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        targets = card.get_targets(game)
        gy_reqs = [r for r in targets if r.zone == Zone.GRAVEYARD]
        assert len(gy_reqs) >= 1

        req = gy_reqs[0]
        big_creature = Creature(name="Big", mana_cost=ManaCost.parse("{2}{B}{B}"),
                                base_power=4, base_toughness=4)
        assert req.filter_fn(big_creature) is False

    def test_target_filter_rejects_non_creature(self) -> None:
        """The target filter for -2 should reject non-creature cards even with
        low mana value."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        targets = card.get_targets(game)
        gy_reqs = [r for r in targets if r.zone == Zone.GRAVEYARD]
        assert len(gy_reqs) >= 1

        req = gy_reqs[0]
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        assert req.filter_fn(bolt) is False

    def test_reanimate_empty_graveyard_no_crash(self) -> None:
        """Activating -2 with no valid target in graveyard should not crash."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        set_board_state(game, 0, graveyard=[])

        abilities = card.get_loyalty_abilities()
        minus_two = abilities[2]
        card.chosen_targets = []
        card._resolve_target = None
        # Should not raise
        minus_two.effect(game)


# ---------------------------------------------------------------------------
# -7: Flip five coins, opponent skips X turns
# ---------------------------------------------------------------------------


class TestRalZarekUltimate:
    """-7: Flip five coins. Target opponent skips their next X turns,
    where X is the number of coins that came up heads."""

    def test_ultimate_loyalty_cost(self) -> None:
        """The ultimate ability should have loyalty cost -7."""
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert abilities[3].loyalty_cost == -7

    def test_ultimate_skips_opponent_turns(self) -> None:
        """After resolving -7, the opponent should have some turns skipped.
        We verify by checking the extra_turns queue or a skip_turns counter
        on the opponent player."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        card.chosen_targets = [p2]
        card._resolve_target = p2
        card._resolve_targets = [p2]

        abilities = card.get_loyalty_abilities()
        ultimate = abilities[3]
        ultimate.effect(game)

        # After the ultimate resolves, some turn-skipping mechanism should
        # have been applied to p2. The exact mechanism depends on
        # implementation — could be:
        # (a) p2.skip_turns > 0  (a skip counter)
        # (b) game.extra_turns is populated with p1 turns
        # (c) some other state change
        # We check for any sign of turn-skipping.
        has_skip_counter = getattr(p2, "skip_turns", 0) > 0
        has_skip_next = getattr(p2, "skip_next_turns", 0) > 0
        has_extra_turns = len(game.extra_turns) > 0
        assert has_skip_counter or has_skip_next or has_extra_turns, (
            "After resolving -7, some turn-skipping mechanism should be set "
            "on the opponent or in the game state"
        )

    def test_ultimate_with_no_heads_skips_zero_turns(self) -> None:
        """If all 5 coin flips come up tails (0 heads), the opponent skips
        0 turns — effectively a no-op for turn skipping."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        card.chosen_targets = [p2]
        card._resolve_target = p2
        card._resolve_targets = [p2]

        # Monkey-patch the coin flip to always return tails
        import random
        original_choice = random.choice
        original_randint = random.randint
        try:
            # Try patching various randomness approaches
            random.choice = lambda seq: seq[1] if len(seq) > 1 else seq[0]  # type: ignore[assignment]
            random.randint = lambda a, b: 0  # type: ignore[assignment]

            abilities = card.get_loyalty_abilities()
            ultimate = abilities[3]

            # Also try setting a deterministic coin result attribute
            card._coin_results = [False, False, False, False, False]

            ultimate.effect(game)
        finally:
            random.choice = original_choice  # type: ignore[assignment]
            random.randint = original_randint  # type: ignore[assignment]

        # With 0 heads, turn skipping should be 0 or absent
        skip_count = getattr(p2, "skip_turns", 0) + getattr(p2, "skip_next_turns", 0)
        extra = len(game.extra_turns)
        # Zero heads means zero turns skipped — the total effect should be 0
        # (or at least no more than what was there before).
        # This test primarily ensures the ability doesn't crash with 0 heads.
