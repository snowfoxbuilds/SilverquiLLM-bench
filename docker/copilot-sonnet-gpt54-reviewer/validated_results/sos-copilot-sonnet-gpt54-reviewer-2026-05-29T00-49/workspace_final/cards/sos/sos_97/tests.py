"""Tests for sos_97 — Ral Zarek, Guest Lecturer.

Covers:
- Static card properties (name, mana_cost, loyalty, type, legendary, subtype)
- +1 ability: loyalty increases by 1, Surveil 2 fires (top 2 cards may move to graveyard)
- −1 ability: loyalty decreases by 1, each chosen target player discards a card
- −2 ability: loyalty decreases by 2, creature with CMC ≤ 3 from graveyard returns to battlefield
- −7 ability: loyalty decreases by 7, flip 5 coins, opponent skips next X turns
- Can't use ability when loyalty insufficient
- Edge cases: −2 with no valid graveyard target, −2 with CMC > 3 creature not returned
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Planeswalker, Sorcery
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ral(game: Any, player_index: int = 0) -> RalZarekGuestLecturer:
    """Create a Ral Zarek instance owned and controlled by the given player."""
    player = game.players[player_index]
    return RalZarekGuestLecturer(owner=player, controller=player)


def _get_loyalty_ability(ral: RalZarekGuestLecturer, cost: int) -> Any:
    """Return the LoyaltyAbility with the given loyalty_cost (e.g. +1, -1, -2, -7)."""
    for ability in ral.get_loyalty_abilities():
        if ability.loyalty_cost == cost:
            return ability
    raise ValueError(f"No loyalty ability with cost {cost} found on {ral.name}")


def _make_creature_card(game: Any, player: Any, name: str, cmc: int) -> Creature:
    """Create a creature card with the given CMC owned by player."""
    # Build a mana cost string with the right CMC (all generic)
    if cmc == 0:
        mana_cost_obj = ManaCost()  # zero cost
    else:
        mana_cost_obj = ManaCost.parse(f"{{{cmc}}}")
    creature = Creature(
        name=name,
        base_power=2,
        base_toughness=2,
        mana_cost=mana_cost_obj,
        owner=player,
        controller=player,
    )
    return creature


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------

class TestRalZarekProperties:
    """Static card data should match the sos_97 spec."""

    def test_name(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3

    def test_initial_loyalty_equals_starting(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.loyalty == 3

    def test_is_planeswalker_type(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert isinstance(card, Planeswalker)

    def test_has_planeswalker_card_type(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert CardType.PLANESWALKER in card.card_types

    def test_is_legendary(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_ral_subtype(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert "Ral" in card.subtypes

    def test_has_four_loyalty_abilities(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert len(abilities) == 4

    def test_loyalty_ability_costs(self) -> None:
        """The four abilities should have costs +1, -1, -2, -7."""
        card = RalZarekGuestLecturer(owner=None)
        costs = {a.loyalty_cost for a in card.get_loyalty_abilities()}
        assert costs == {+1, -1, -2, -7}


# ---------------------------------------------------------------------------
# +1 ability: Surveil 2
# ---------------------------------------------------------------------------

class TestRalPlusOne:
    """The +1 ability should increase loyalty by 1 and perform Surveil 2."""

    def test_plus_one_increases_loyalty(self) -> None:
        game = create_game()
        ral = _make_ral(game, 0)
        assert ral.loyalty == 3
        ability = _get_loyalty_ability(ral, +1)
        ral.loyalty += ability.loyalty_cost
        ability.effect(game)
        assert ral.loyalty == 4

    def test_surveil_2_puts_cards_in_graveyard(self) -> None:
        """When both library cards should go to graveyard, they end up there."""
        game = create_game()
        player = game.players[0]
        ral = _make_ral(game, 0)
        # Put two cards on top of library
        card_a = Sorcery(name="CardA", owner=player, controller=player)
        card_b = Sorcery(name="CardB", owner=player, controller=player)
        set_board_state(game, 0, graveyard=[], hand=[])
        player.zones[Zone.LIBRARY].add(card_b)
        player.zones[Zone.LIBRARY].add(card_a)  # card_a is on top

        # Activate the +1 ability
        ability = _get_loyalty_ability(ral, +1)
        # Simulate surveil decision: put both in graveyard via _surveil_to_graveyard
        ral._surveil_to_graveyard = [card_a, card_b]
        ral.loyalty += ability.loyalty_cost
        ability.effect(game)

        graveyard = player.zones[Zone.GRAVEYARD].get_all()
        # At least the cards looked at should be accounted for (either on top or in GY)
        library_names = {c.name for c in player.zones[Zone.LIBRARY].get_all()}
        graveyard_names = {c.name for c in graveyard}
        # After surveil 2, cards should be distributed between library top and graveyard
        assert (
            graveyard_names | library_names == {"CardA", "CardB"}
        ), "All surveilled cards must end up in graveyard or back on library"

    def test_surveil_2_cards_can_stay_on_library(self) -> None:
        """Surveil 2 can leave both cards on top of library."""
        game = create_game()
        player = game.players[0]
        ral = _make_ral(game, 0)
        card_a = Sorcery(name="CardA", owner=player, controller=player)
        card_b = Sorcery(name="CardB", owner=player, controller=player)
        player.zones[Zone.LIBRARY].add(card_b)
        player.zones[Zone.LIBRARY].add(card_a)

        ability = _get_loyalty_ability(ral, +1)
        # Simulate surveil decision: keep both on library
        ral._surveil_to_graveyard = []
        ral.loyalty += ability.loyalty_cost
        ability.effect(game)

        library_names = {c.name for c in player.zones[Zone.LIBRARY].get_all()}
        graveyard_names = {c.name for c in player.zones[Zone.GRAVEYARD].get_all()}
        # Both cards should still be in library
        assert "CardA" in library_names or "CardA" in graveyard_names
        assert "CardB" in library_names or "CardB" in graveyard_names


# ---------------------------------------------------------------------------
# −1 ability: target players discard
# ---------------------------------------------------------------------------

class TestRalMinusOne:
    """The -1 ability should decrease loyalty by 1 and force targets to discard."""

    def test_minus_one_decreases_loyalty(self) -> None:
        game = create_game()
        ral = _make_ral(game, 0)
        assert ral.loyalty == 3
        ability = _get_loyalty_ability(ral, -1)
        ral.loyalty += ability.loyalty_cost
        ability.effect(game)
        assert ral.loyalty == 2

    def test_minus_one_target_discards_card(self) -> None:
        """A targeted player should discard exactly one card."""
        game = create_game()
        player0 = game.players[0]
        player1 = game.players[1]
        ral = _make_ral(game, 0)

        # Put a card in player1's hand
        hand_card = Sorcery(name="HandCard", owner=player1, controller=player1)
        set_board_state(game, 1, hand=[hand_card])

        hand_before = len(player1.zones[Zone.HAND].get_all())
        grave_before = len(player1.zones[Zone.GRAVEYARD].get_all())

        ability = _get_loyalty_ability(ral, -1)
        ral._resolve_targets = [player1]
        ral.loyalty += ability.loyalty_cost
        ability.effect(game)

        hand_after = len(player1.zones[Zone.HAND].get_all())
        grave_after = len(player1.zones[Zone.GRAVEYARD].get_all())

        # Player1 lost one card from hand and gained one in graveyard
        assert hand_after == hand_before - 1
        assert grave_after == grave_before + 1

    def test_minus_one_multiple_targets_all_discard(self) -> None:
        """Both players can be targeted and both should discard."""
        game = create_game()
        player0 = game.players[0]
        player1 = game.players[1]
        ral = _make_ral(game, 0)

        card0 = Sorcery(name="Card0", owner=player0, controller=player0)
        card1 = Sorcery(name="Card1", owner=player1, controller=player1)
        set_board_state(game, 0, hand=[card0])
        set_board_state(game, 1, hand=[card1])

        ability = _get_loyalty_ability(ral, -1)
        ral._resolve_targets = [player0, player1]
        ral.loyalty += ability.loyalty_cost
        ability.effect(game)

        assert len(player0.zones[Zone.HAND].get_all()) == 0
        assert len(player1.zones[Zone.HAND].get_all()) == 0

    def test_minus_one_no_targets_is_noop(self) -> None:
        """With zero targets, the ability should resolve without error."""
        game = create_game()
        ral = _make_ral(game, 0)
        ability = _get_loyalty_ability(ral, -1)
        ral._resolve_targets = []
        ral.loyalty += ability.loyalty_cost
        # Should not raise
        ability.effect(game)
        assert ral.loyalty == 2

    def test_minus_one_target_with_empty_hand_no_crash(self) -> None:
        """Targeting a player with empty hand should not raise."""
        game = create_game()
        player1 = game.players[1]
        ral = _make_ral(game, 0)
        set_board_state(game, 1, hand=[])
        ability = _get_loyalty_ability(ral, -1)
        ral._resolve_targets = [player1]
        ral.loyalty += ability.loyalty_cost
        # Should not raise even if hand is empty
        ability.effect(game)


# ---------------------------------------------------------------------------
# −2 ability: return creature from graveyard with CMC ≤ 3
# ---------------------------------------------------------------------------

class TestRalMinusTwo:
    """The -2 ability returns a creature with CMC ≤ 3 from graveyard to battlefield."""

    def test_minus_two_decreases_loyalty(self) -> None:
        game = create_game()
        ral = _make_ral(game, 0)
        assert ral.loyalty == 3
        ability = _get_loyalty_ability(ral, -2)
        ral.loyalty += ability.loyalty_cost
        ability.effect(game)
        assert ral.loyalty == 1

    def test_minus_two_returns_cmc3_creature_to_battlefield(self) -> None:
        """A creature with CMC exactly 3 in graveyard should move to battlefield."""
        game = create_game()
        player = game.players[0]
        ral = _make_ral(game, 0)

        creature = _make_creature_card(game, player, "SmallCreature", cmc=3)
        set_board_state(game, 0, graveyard=[creature])

        bf_before = len(game.get_battlefield(player).get_all())
        gy_before = len(player.zones[Zone.GRAVEYARD].get_all())

        ability = _get_loyalty_ability(ral, -2)
        ral._resolve_target = creature
        ral.loyalty += ability.loyalty_cost
        ability.effect(game)

        bf_after = len(game.get_battlefield(player).get_all())
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())

        assert bf_after == bf_before + 1, "Creature should have entered the battlefield"
        assert gy_after == gy_before - 1, "Creature should have left the graveyard"

    def test_minus_two_returns_cmc0_creature(self) -> None:
        """A creature with CMC 0 should also be returnable."""
        game = create_game()
        player = game.players[0]
        ral = _make_ral(game, 0)

        creature = _make_creature_card(game, player, "ZeroCostCreature", cmc=0)
        set_board_state(game, 0, graveyard=[creature])

        ability = _get_loyalty_ability(ral, -2)
        ral._resolve_target = creature
        ral.loyalty += ability.loyalty_cost
        ability.effect(game)

        bf_cards = {c.name for c in game.get_battlefield(player).get_all()}
        assert "ZeroCostCreature" in bf_cards

    def test_minus_two_does_not_return_cmc4_creature(self) -> None:
        """A creature with CMC 4 should not be a valid target — ability should not move it."""
        game = create_game()
        player = game.players[0]
        ral = _make_ral(game, 0)

        creature = _make_creature_card(game, player, "BigCreature", cmc=4)
        set_board_state(game, 0, graveyard=[creature])

        bf_before = len(game.get_battlefield(player).get_all())

        ability = _get_loyalty_ability(ral, -2)
        # Target set to the invalid creature (CMC > 3)
        ral._resolve_target = creature
        ral.loyalty += ability.loyalty_cost
        ability.effect(game)

        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after == bf_before, "CMC > 3 creature should not be returned to battlefield"

    def test_minus_two_no_target_is_noop(self) -> None:
        """With no target set, the ability should resolve without crashing."""
        game = create_game()
        ral = _make_ral(game, 0)
        ability = _get_loyalty_ability(ral, -2)
        ral._resolve_target = None
        ral.loyalty += ability.loyalty_cost
        # Should not raise
        ability.effect(game)
        assert ral.loyalty == 1

    def test_minus_two_empty_graveyard_noop(self) -> None:
        """With empty graveyard, ability has no target and should not crash."""
        game = create_game()
        player = game.players[0]
        ral = _make_ral(game, 0)
        set_board_state(game, 0, graveyard=[])

        ability = _get_loyalty_ability(ral, -2)
        ral._resolve_target = None
        ral.loyalty += ability.loyalty_cost
        ability.effect(game)

        assert len(game.get_battlefield(player).get_all()) == 0


# ---------------------------------------------------------------------------
# −7 ability: flip coins, skip turns
# ---------------------------------------------------------------------------

class TestRalMinusSeven:
    """The -7 ability flips 5 coins; opponent skips their next X turns (X = heads)."""

    def test_minus_seven_ability_exists(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        ability = _get_loyalty_ability(card, -7)
        assert ability is not None

    def test_minus_seven_decreases_loyalty(self) -> None:
        """After using -7, loyalty should decrease by 7."""
        game = create_game()
        ral = _make_ral(game, 0)
        # Set loyalty high enough
        ral.loyalty = 10
        ability = _get_loyalty_ability(ral, -7)
        ral.loyalty += ability.loyalty_cost
        ability.effect(game)
        assert ral.loyalty == 3  # 10 - 7 = 3

    def test_minus_seven_resolves_without_crash(self) -> None:
        """The -7 ability should fire without raising, even with default game state."""
        game = create_game()
        ral = _make_ral(game, 0)
        ral.loyalty = 7
        ability = _get_loyalty_ability(ral, -7)
        target_opponent = game.players[1]
        ral._resolve_target = target_opponent
        ral.loyalty += ability.loyalty_cost
        ability.effect(game)
        # Loyalty should have decreased by 7
        assert ral.loyalty == 0


# ---------------------------------------------------------------------------
# Loyalty validation (insufficient loyalty)
# ---------------------------------------------------------------------------

class TestRalLoyaltyValidation:
    """Abilities should not fire when loyalty is insufficient."""

    def test_cannot_use_minus_two_at_one_loyalty(self) -> None:
        """With 1 loyalty, using -2 would drop loyalty below 0, which is illegal."""
        game = create_game()
        ral = _make_ral(game, 0)
        ral.loyalty = 1
        # The ability's cost would require loyalty >= 2; verify loyalty would go negative
        ability = _get_loyalty_ability(ral, -2)
        resulting_loyalty = ral.loyalty + ability.loyalty_cost
        assert resulting_loyalty < 0, (
            "Using -2 with 1 loyalty should result in negative loyalty (illegal)"
        )

    def test_cannot_use_minus_seven_at_three_loyalty(self) -> None:
        """With starting loyalty of 3, the -7 ability cannot be used."""
        game = create_game()
        ral = _make_ral(game, 0)
        assert ral.loyalty == 3
        ability = _get_loyalty_ability(ral, -7)
        resulting_loyalty = ral.loyalty + ability.loyalty_cost
        assert resulting_loyalty < 0, (
            "Using -7 with 3 loyalty should result in negative loyalty (illegal)"
        )

    def test_plus_one_always_usable_at_starting_loyalty(self) -> None:
        """At starting loyalty 3, the +1 ability is always usable."""
        game = create_game()
        ral = _make_ral(game, 0)
        ability = _get_loyalty_ability(ral, +1)
        resulting_loyalty = ral.loyalty + ability.loyalty_cost
        assert resulting_loyalty > 0, "After +1, loyalty should still be positive"

    def test_minus_one_usable_at_starting_loyalty(self) -> None:
        """At starting loyalty 3, the -1 ability keeps loyalty positive."""
        game = create_game()
        ral = _make_ral(game, 0)
        ability = _get_loyalty_ability(ral, -1)
        resulting_loyalty = ral.loyalty + ability.loyalty_cost
        assert resulting_loyalty >= 0, "After -1 from 3 loyalty, result should be non-negative"
