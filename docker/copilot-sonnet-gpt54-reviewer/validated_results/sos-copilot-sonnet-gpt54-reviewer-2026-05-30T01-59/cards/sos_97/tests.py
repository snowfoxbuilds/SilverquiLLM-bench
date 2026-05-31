"""Tests for sos_97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import pytest
from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ral(game, player_index=0):
    """Place Ral Zarek, Guest Lecturer on the battlefield for player."""
    ral = RalZarekGuestLecturer()
    set_board_state(game, player_index, battlefield=[ral])
    return ral


def make_creature(name="Bear", power=2, toughness=2, mana_cost_str="{1}{G}"):
    c = Creature(
        name=name,
        base_power=power,
        base_toughness=toughness,
        mana_cost=ManaCost.parse(mana_cost_str),
    )
    return c


# ---------------------------------------------------------------------------
# Identity tests
# ---------------------------------------------------------------------------

class TestCardIdentity:
    def test_name(self):
        ral = RalZarekGuestLecturer()
        assert ral.name == "Ral Zarek, Guest Lecturer"

    def test_type_is_planeswalker(self):
        ral = RalZarekGuestLecturer()
        assert CardType.PLANESWALKER in ral.card_types

    def test_starting_loyalty(self):
        ral = RalZarekGuestLecturer()
        assert ral.starting_loyalty == 3
        assert ral.loyalty == 3

    def test_is_legendary(self):
        ral = RalZarekGuestLecturer()
        assert Supertype.LEGENDARY in ral.supertypes

    def test_subtype_ral(self):
        ral = RalZarekGuestLecturer()
        assert "Ral" in ral.subtypes

    def test_mana_cost(self):
        ral = RalZarekGuestLecturer()
        assert ral.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_has_four_loyalty_abilities(self):
        ral = RalZarekGuestLecturer()
        abilities = ral.get_loyalty_abilities()
        assert len(abilities) == 4

    def test_loyalty_costs(self):
        ral = RalZarekGuestLecturer()
        abilities = ral.get_loyalty_abilities()
        costs = [a.loyalty_cost for a in abilities]
        assert +1 in costs
        assert -1 in costs
        assert -2 in costs
        assert -7 in costs


# ---------------------------------------------------------------------------
# +1 Surveil 2 tests
# ---------------------------------------------------------------------------

class TestPlusOneSurveil:
    def test_surveil2_both_to_graveyard(self):
        """Put both surveiled cards in the graveyard."""
        game = create_game()
        ral = make_ral(game, 0)
        p1 = game.players[0]

        card_a = make_creature("CardA")
        card_b = make_creature("CardB")
        card_c = make_creature("CardC")
        library = p1.zones[Zone.LIBRARY]
        graveyard = p1.zones[Zone.GRAVEYARD]

        for c in [card_a, card_b, card_c]:
            c.owner = p1
            c.controller = p1
            library.add(c)

        # Set up: CardC is top (last added), CardB is second from top
        # Script: put both in graveyard
        ral._surveil_to_graveyard = [card_c, card_b]
        ral.loyalty = 3  # reset

        ability = ral.get_loyalty_abilities()[0]  # +1
        assert ability.loyalty_cost == +1
        ability.effect(game)

        assert graveyard.contains(card_c)
        assert graveyard.contains(card_b)
        assert library.contains(card_a)
        assert not library.contains(card_b)
        assert not library.contains(card_c)

    def test_surveil2_keep_both_on_top(self):
        """Keep both surveiled cards on top of library."""
        game = create_game()
        ral = make_ral(game, 0)
        p1 = game.players[0]

        card_a = make_creature("CardA")
        card_b = make_creature("CardB")
        library = p1.zones[Zone.LIBRARY]
        graveyard = p1.zones[Zone.GRAVEYARD]

        for c in [card_a, card_b]:
            c.owner = p1
            c.controller = p1
            library.add(c)

        ral._surveil_to_graveyard = []
        ability = ral.get_loyalty_abilities()[0]
        ability.effect(game)

        assert library.contains(card_a)
        assert library.contains(card_b)
        assert len(list(graveyard.get_all())) == 0

    def test_surveil2_one_to_graveyard_one_on_top(self):
        """Put one in graveyard, keep one on top."""
        game = create_game()
        ral = make_ral(game, 0)
        p1 = game.players[0]

        card_a = make_creature("Bottom")
        card_b = make_creature("Top")
        library = p1.zones[Zone.LIBRARY]
        graveyard = p1.zones[Zone.GRAVEYARD]

        for c in [card_a, card_b]:
            c.owner = p1
            c.controller = p1
            library.add(c)

        # Put top card (card_b) in graveyard, keep card_a
        ral._surveil_to_graveyard = [card_b]
        ability = ral.get_loyalty_abilities()[0]
        ability.effect(game)

        assert graveyard.contains(card_b)
        assert library.contains(card_a)

    def test_surveil2_empty_library(self):
        """Surveil with empty library does nothing."""
        game = create_game()
        ral = make_ral(game, 0)
        p1 = game.players[0]
        # Library already empty from create_game reset
        library = p1.zones[Zone.LIBRARY]
        for card in list(library.get_all()):
            library.remove(card)

        ral._surveil_to_graveyard = []
        ability = ral.get_loyalty_abilities()[0]
        ability.effect(game)  # Should not raise

    def test_plus1_increases_loyalty(self):
        """Activating +1 should increase loyalty from 3 to 4."""
        game = create_game()
        ral = make_ral(game, 0)
        ral._surveil_to_graveyard = []

        from engine.abilities import LoyaltyAbilityInstance, activate_ability
        from engine.abilities import clear_loyalty_tracking

        clear_loyalty_tracking()
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0

        la = ral.get_loyalty_abilities()[0]  # +1
        inst = LoyaltyAbilityInstance(
            source=ral,
            controller=game.players[0],
            loyalty_cost=la.loyalty_cost,
            effect=la.effect,
        )
        activate_ability(game, game.players[0], inst)
        # Stack resolve
        obj = game.stack.pop()
        obj.on_resolve(game)
        assert ral.loyalty == 4


# ---------------------------------------------------------------------------
# -1 Discard tests
# ---------------------------------------------------------------------------

class TestMinusOneDiscard:
    def test_minus1_target_player_discards(self):
        """Target player discards a card."""
        game = create_game()
        ral = make_ral(game, 0)
        p2 = game.players[1]

        card_in_hand = make_creature("Fodder")
        hand = p2.zones[Zone.HAND]
        graveyard = p2.zones[Zone.GRAVEYARD]
        card_in_hand.owner = p2
        card_in_hand.controller = p2
        hand.add(card_in_hand)

        ral._resolve_targets = [p2]
        ability = ral.get_loyalty_abilities()[1]  # -1
        assert ability.loyalty_cost == -1
        ability.effect(game)

        assert graveyard.contains(card_in_hand)
        assert not hand.contains(card_in_hand)

    def test_minus1_multiple_targets_discard(self):
        """Multiple target players each discard."""
        game = create_game()
        ral = make_ral(game, 0)
        p1 = game.players[0]
        p2 = game.players[1]

        card1 = make_creature("Card1")
        card2 = make_creature("Card2")

        for card, player in [(card1, p1), (card2, p2)]:
            card.owner = player
            card.controller = player
            player.zones[Zone.HAND].add(card)

        ral._resolve_targets = [p1, p2]
        ability = ral.get_loyalty_abilities()[1]
        ability.effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(card1)
        assert p2.zones[Zone.GRAVEYARD].contains(card2)

    def test_minus1_empty_hand_no_error(self):
        """Target with empty hand doesn't error."""
        game = create_game()
        ral = make_ral(game, 0)
        p2 = game.players[1]

        ral._resolve_targets = [p2]
        ability = ral.get_loyalty_abilities()[1]
        ability.effect(game)  # Should not raise

    def test_minus1_reduces_loyalty(self):
        """Activating -1 reduces loyalty from 3 to 2."""
        game = create_game()
        ral = make_ral(game, 0)
        ral._resolve_targets = []

        from engine.abilities import LoyaltyAbilityInstance, activate_ability, clear_loyalty_tracking
        clear_loyalty_tracking()
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0

        la = ral.get_loyalty_abilities()[1]  # -1
        inst = LoyaltyAbilityInstance(
            source=ral,
            controller=game.players[0],
            loyalty_cost=la.loyalty_cost,
            effect=la.effect,
        )
        activate_ability(game, game.players[0], inst)
        obj = game.stack.pop()
        obj.on_resolve(game)
        assert ral.loyalty == 2


# ---------------------------------------------------------------------------
# -2 Return creature from graveyard tests
# ---------------------------------------------------------------------------

class TestMinusTwoRecur:
    def test_minus2_returns_creature_mv3_or_less(self):
        """Return a creature with MV ≤3 from graveyard to battlefield."""
        game = create_game()
        ral = make_ral(game, 0)
        p1 = game.players[0]

        creature = make_creature("SmallBear", mana_cost_str="{1}{G}")  # MV 2
        creature.owner = p1
        creature.controller = p1
        p1.zones[Zone.GRAVEYARD].add(creature)

        ral._resolve_target = creature
        ability = ral.get_loyalty_abilities()[2]  # -2
        assert ability.loyalty_cost == -2
        ability.effect(game)

        assert p1.zones[Zone.BATTLEFIELD].contains(creature)
        assert not p1.zones[Zone.GRAVEYARD].contains(creature)

    def test_minus2_returns_mv3_creature(self):
        """Return a creature with exactly MV 3."""
        game = create_game()
        ral = make_ral(game, 0)
        p1 = game.players[0]

        creature = make_creature("Vanilla3", mana_cost_str="{1}{G}{G}")  # MV 3
        creature.owner = p1
        creature.controller = p1
        p1.zones[Zone.GRAVEYARD].add(creature)

        ral._resolve_target = creature
        ability = ral.get_loyalty_abilities()[2]
        ability.effect(game)

        assert p1.zones[Zone.BATTLEFIELD].contains(creature)

    def test_minus2_rejects_mv4_creature(self):
        """Do not return a creature with MV > 3."""
        game = create_game()
        ral = make_ral(game, 0)
        p1 = game.players[0]

        big_creature = make_creature("BigBear", mana_cost_str="{3}{G}")  # MV 4
        big_creature.owner = p1
        big_creature.controller = p1
        p1.zones[Zone.GRAVEYARD].add(big_creature)

        ral._resolve_target = big_creature
        ability = ral.get_loyalty_abilities()[2]
        ability.effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(big_creature)
        assert not p1.zones[Zone.BATTLEFIELD].contains(big_creature)

    def test_minus2_only_from_own_graveyard(self):
        """Target must be in controller's graveyard."""
        game = create_game()
        ral = make_ral(game, 0)
        p2 = game.players[1]

        creature = make_creature("OpponentCreature", mana_cost_str="{G}")
        creature.owner = p2
        creature.controller = p2
        p2.zones[Zone.GRAVEYARD].add(creature)

        # Target in opponent's graveyard — should not be returned to p1's battlefield
        ral._resolve_target = creature
        ability = ral.get_loyalty_abilities()[2]
        ability.effect(game)

        # It shouldn't end up on p1's battlefield
        assert not game.players[0].zones[Zone.BATTLEFIELD].contains(creature)

    def test_minus2_reduces_loyalty(self):
        """Activating -2 reduces loyalty from 3 to 1."""
        game = create_game()
        ral = make_ral(game, 0)
        ral._resolve_target = None  # No valid target, effect is no-op

        from engine.abilities import LoyaltyAbilityInstance, activate_ability, clear_loyalty_tracking
        clear_loyalty_tracking()
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0

        la = ral.get_loyalty_abilities()[2]  # -2
        inst = LoyaltyAbilityInstance(
            source=ral,
            controller=game.players[0],
            loyalty_cost=la.loyalty_cost,
            effect=la.effect,
        )
        activate_ability(game, game.players[0], inst)
        obj = game.stack.pop()
        obj.on_resolve(game)
        assert ral.loyalty == 1


# ---------------------------------------------------------------------------
# -7 Coin flip / turn skip tests
# ---------------------------------------------------------------------------

class TestMinusSevenCoinFlip:
    def test_minus7_all_heads_skips_5_turns(self):
        """If all 5 coins land heads, opponent skips 5 turns."""
        game = create_game()
        ral = make_ral(game, 0)
        p2 = game.players[1]

        ral._coin_flip_fn = lambda: 1  # all heads
        ral._resolve_target = p2

        ability = ral.get_loyalty_abilities()[3]  # -7
        assert ability.loyalty_cost == -7
        ability.effect(game)

        assert p2.turns_to_skip == 5

    def test_minus7_all_tails_skips_0_turns(self):
        """If all 5 coins land tails, opponent skips 0 turns."""
        game = create_game()
        ral = make_ral(game, 0)
        p2 = game.players[1]

        ral._coin_flip_fn = lambda: 0  # all tails
        ral._resolve_target = p2

        ability = ral.get_loyalty_abilities()[3]
        ability.effect(game)

        assert p2.turns_to_skip == 0

    def test_minus7_partial_heads(self):
        """Partial heads skips that many turns."""
        game = create_game()
        ral = make_ral(game, 0)
        p2 = game.players[1]

        flips = iter([1, 0, 1, 0, 1])  # 3 heads
        ral._coin_flip_fn = lambda: next(flips)
        ral._resolve_target = p2

        ability = ral.get_loyalty_abilities()[3]
        ability.effect(game)

        assert p2.turns_to_skip == 3

    def test_minus7_accumulates_with_existing_skips(self):
        """turns_to_skip accumulates if already set."""
        game = create_game()
        ral = make_ral(game, 0)
        p2 = game.players[1]
        p2.turns_to_skip = 2  # already has 2 skips

        ral._coin_flip_fn = lambda: 1  # 5 heads
        ral._resolve_target = p2

        ability = ral.get_loyalty_abilities()[3]
        ability.effect(game)

        assert p2.turns_to_skip == 7

    def test_minus7_no_target_no_error(self):
        """No target: no-op."""
        game = create_game()
        ral = make_ral(game, 0)

        ral._coin_flip_fn = lambda: 1
        ral._resolve_target = None

        ability = ral.get_loyalty_abilities()[3]
        ability.effect(game)  # Should not raise

    def test_turn_skip_engine_integration(self):
        """Engine skips opponent's turn when turns_to_skip > 0."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p2.turns_to_skip = 1

        # Advance to end of p1's turn (cleanup -> next turn)
        from engine.types import Phase, Step
        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.active_player_index = 0
        game._normal_next_index = 1

        game.advance_phase()

        # p2's turn should be skipped, so p1 should be active again
        assert game.active_player_index == 0
        assert p2.turns_to_skip == 0
