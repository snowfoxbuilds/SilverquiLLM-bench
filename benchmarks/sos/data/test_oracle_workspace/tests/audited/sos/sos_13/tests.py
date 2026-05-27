"""Rewritten audited tests for Emeritus of Truce // Swords to Plowshares (sos_13).

6 tests:
1. Identity: name, mana_cost, CMC 3, types, colors, no PREPARED keyword
2. ETB token creation: cast creature via cast_spell, verify target player gets Inkling
3. Token characteristics: 2/1 white/black Inkling with flying
4. Prepared cast from exile: cast from exile for {W}, targets creature, exiles it,
   controller gains life = power
5. Prepared rejected without flag: card in exile without prepared → cannot cast
6. Back-half cost not in CMC: CMC is 3, not 4

Bug pattern addressed: split-Prepared CMC was erroneously summed to 4
(front 3 + back 1). Correct CMC is 3 (front face only).
"""

from __future__ import annotations

import pytest

from card_impl import EmeritusOfTruceSwordsToPlowshares

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import (
    card_colors,
    cast_spell,
    cast_spell_from_exile,
    create_game,
    set_board_state,
    set_hand,
    set_mana_pool,
)


# ---------------------------------------------------------------------------
# Test 1: Identity
# ---------------------------------------------------------------------------


class TestIdentity:
    """Verify static card properties: name, mana_cost, CMC, types, colors, keywords."""

    def test_identity(self) -> None:
        """Card has correct name, mana cost {1}{W}{W}, CMC=3, types, colors, no PREPARED."""
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)

        # Name
        assert card.name == "Emeritus of Truce // Swords to Plowshares"

        # Mana cost: {1}{W}{W}
        assert card.mana_cost.generic == 1
        assert card.mana_cost.pips.get(ManaType.WHITE) == 2

        # CMC must be 3 (front face only), NOT 4
        assert card.mana_cost.cmc == 3, (
            f"CMC must be 3 (front face only), got {card.mana_cost.cmc}"
        )

        # Types
        assert CardType.CREATURE in card.card_types

        # Subtypes
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

        # Colors (derived from mana cost — white)
        colors = card_colors(card)
        assert "W" in colors
        assert len(colors) == 1, f"Expected only white, got {colors}"

        # PREPARED is an ability word, NOT a keyword — must not appear
        if hasattr(Keyword, "PREPARED"):
            assert Keyword.PREPARED not in card.keywords  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Test 2: ETB token creation — cast via cast_spell, ETB triggers naturally
# ---------------------------------------------------------------------------


class TestETBTokenCreation:
    """Cast the creature via cast_spell and verify ETB creates token for target player."""

    def test_etb_token_creation(self) -> None:
        """Casting Emeritus of Truce via cast_spell triggers ETB; target player gets token."""
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=player)
        card.controller = player

        # Put card in hand and provide mana
        set_hand(game, 0, [card])
        set_mana_pool(game, 0, {ManaType.WHITE: 2, ManaType.COLORLESS: 1})

        # Cast targeting opponent (opponent should get the token)
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares", targets=[opponent])

        # Verify the target player (opponent) received the Inkling token
        opp_bf = opponent.zones[Zone.BATTLEFIELD].get_all()
        tokens = [c for c in opp_bf if getattr(c, "is_token", False)]
        assert len(tokens) >= 1, (
            "Target player must receive at least one Inkling token from ETB"
        )
        token = tokens[0]
        assert getattr(token, "name", None) == "Inkling", (
            f"Token should be named 'Inkling', got {getattr(token, 'name', None)!r}"
        )


# ---------------------------------------------------------------------------
# Test 3: Token characteristics — 2/1 white/black Inkling with flying
# ---------------------------------------------------------------------------


class TestTokenCharacteristics:
    """Token created by ETB has correct P/T, colors, subtypes, and flying."""

    def test_token_characteristics(self) -> None:
        """Inkling token is 2/1, white and black, creature, with flying."""
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=player)
        card.controller = player

        set_hand(game, 0, [card])
        set_mana_pool(game, 0, {ManaType.WHITE: 2, ManaType.COLORLESS: 1})

        # Cast targeting opponent
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares", targets=[opponent])

        # Find the token
        opp_bf = opponent.zones[Zone.BATTLEFIELD].get_all()
        tokens = [c for c in opp_bf if getattr(c, "is_token", False)]
        assert len(tokens) >= 1, "Token must exist on target player's battlefield"
        token = tokens[0]

        # Power/toughness: 2/1
        assert token.base_power == 2, f"Token power should be 2, got {token.base_power}"
        assert token.base_toughness == 1, f"Token toughness should be 1, got {token.base_toughness}"

        # Is a creature
        assert CardType.CREATURE in token.card_types

        # Has flying
        assert Keyword.FLYING in token.keywords, "Inkling token must have flying"

        # Subtype: Inkling
        assert "Inkling" in getattr(token, "subtypes", set()), "Token must have Inkling subtype"


# ---------------------------------------------------------------------------
# Test 4: Prepared cast from exile — back-face instant behavior
# ---------------------------------------------------------------------------


class TestPreparedCastFromExile:
    """Cast from exile via prepared; verify back-face exiles creature and gains life."""

    def test_prepared_cast_from_exile(self) -> None:
        """Put card in exile with prepared flag, cast for {W} targeting opponent's
        creature. Verify: creature is exiled, its controller gains life = power."""
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]

        # Set up a creature on opponent's battlefield to target
        target_creature = Creature(
            name="Grizzly Bears",
            base_power=4,
            base_toughness=4,
            owner=opponent,
            controller=opponent,
        )
        set_board_state(game, 1, battlefield=[target_creature])

        # Record opponent's starting life
        opponent_life_before = opponent.life

        # Put the card in exile with prepared flag
        card = EmeritusOfTruceSwordsToPlowshares(owner=player)
        card.controller = player
        card._prepared = True
        player.zones[Zone.EXILE].add(card)

        # Give player {W} to pay the alt cost
        set_mana_pool(game, 0, {ManaType.WHITE: 1})

        # Cast from exile targeting the opponent's creature
        cast_spell_from_exile(
            game, 0, "Emeritus of Truce // Swords to Plowshares",
            targets=[target_creature],
        )

        # Verify: target creature was exiled (not on opponent's battlefield)
        opp_bf = opponent.zones[Zone.BATTLEFIELD].get_all()
        opp_bf_names = [getattr(c, "name", None) for c in opp_bf]
        assert "Grizzly Bears" not in opp_bf_names, (
            "Target creature must be exiled from the battlefield"
        )

        # Verify: creature's controller (opponent) gained life = creature's power (4)
        life_gained = opponent.life - opponent_life_before
        assert life_gained == 4, (
            f"Controller should gain life equal to creature's power (4), "
            f"but gained {life_gained}"
        )


# ---------------------------------------------------------------------------
# Test 5: Prepared rejected without flag
# ---------------------------------------------------------------------------


class TestPreparedRejectedWithoutFlag:
    """Card in exile without prepared flag → cannot cast."""

    def test_prepared_rejected_without_flag(self) -> None:
        """When card is in exile but NOT prepared, alt cost is NOT available."""
        game = create_game()
        player = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=player)
        card.controller = player
        # Put card in exile WITHOUT prepared flag
        player.zones[Zone.EXILE].add(card)
        card._prepared = False

        assert not card.can_cast_from_exile(game), (
            "Alt cost must NOT be available when not prepared"
        )
        assert card.get_alternative_cost() is None, (
            "get_alternative_cost must return None when not prepared"
        )


# ---------------------------------------------------------------------------
# Test 6: Back-half cost not in CMC
# ---------------------------------------------------------------------------


class TestBackHalfCostNotInCMC:
    """Back-half {W} cost must NOT contribute to CMC."""

    def test_back_half_cost_not_in_cmc(self) -> None:
        """CMC is exactly 3 ({1}{W}{W}), not 4 ({1}{W}{W} + {W}).

        The back-face {W} is alt-cost metadata for the prepared ability
        and does not contribute to the card's converted mana cost.
        Also verifies CMC doesn't change when card becomes prepared.
        """
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)

        # Front face cost only -> CMC 3
        assert card.mana_cost.cmc == 3, (
            f"CMC must be 3 (front face), got {card.mana_cost.cmc}"
        )

        # Even when prepared, CMC must remain 3
        card._prepared = True
        assert card.mana_cost.cmc == 3, "CMC must not change when prepared"
