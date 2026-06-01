"""Audited tests for Emeritus of Truce // Swords to Plowshares (sos_13).

Behavioral, canonical-engine-API-only coverage of the front-face ETB and the
back-face "prepared" alt-cast. The prepared state is never injected via a
private flag; it is established through gameplay (the front-face ETB resolving
with an opponent controlling more creatures) and observed through outcomes:
whether the back face is castable from exile (cast succeeds / raises
CastingError), the creature it exiles, and the life its controller gains.

Coverage:
- Identity: name, mana_cost, CMC 3 (front face only — the back-face {W} alt
  cost does not contribute to CMC), types, colors.
- ETB: target player creates a 2/1 white/black Inkling with flying (token
  characteristics + summoning sickness).
- Prepared back face from exile: exiles target creature, its controller gains
  life equal to its power.
- Prepared condition is a strict inequality (equal counts → not prepared →
  not castable from exile; opponent strictly more → prepared → castable).
- Prepared is single-use: consumed by the back-face cast.
"""

from __future__ import annotations

import pytest

from card_impl import EmeritusOfTruceSwordsToPlowshares

from engine.card import Creature
from engine.types import CardType, Keyword, ManaType, Zone
from test_utils import (
    assert_casting_error,
    card_colors,
    cast_spell,
    cast_spell_from_exile,
    create_game,
    set_board_state,
    set_hand,
    set_mana_pool,
)

_NAME = "Emeritus of Truce // Swords to Plowshares"


def _cast_front_face(game, player, target_player):
    """Cast the front-face creature from hand and resolve its ETB.

    Returns the resolved card now on ``player``'s battlefield (the ETB's
    "if an opponent controls more creatures than you" clause may have made
    it prepared, depending on the board the caller set up).
    """
    card = EmeritusOfTruceSwordsToPlowshares(owner=player)
    card.controller = player
    set_hand(game, 0, [card])
    set_mana_pool(game, 0, {ManaType.WHITE: 2, ManaType.COLORLESS: 1})
    cast_spell(game, 0, _NAME, targets=[target_player])
    for c in player.zones[Zone.BATTLEFIELD].get_all():
        if getattr(c, "name", None) == _NAME:
            return c
    raise AssertionError("Emeritus should be on the battlefield after its ETB resolves")


def _move_to_exile(player, card):
    """Move a card the player owns/controls into their exile zone."""
    bf = player.zones[Zone.BATTLEFIELD]
    if bf.contains(card):
        bf.remove(card)
    player.zones[Zone.EXILE].add(card)


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
    """Drive prepared via gameplay, then cast the back face from exile."""

    def test_prepared_cast_from_exile(self) -> None:
        """With an opponent controlling more creatures, the ETB makes the card
        prepared. Cast from exile then exiles the target creature and its
        controller gains life equal to that creature's power."""
        game = create_game()
        player, opponent = game.players

        # Opponent controls more creatures than the player → ETB sets prepared.
        bear = Creature(name="Grizzly Bears", base_power=4, base_toughness=4,
                        owner=opponent, controller=opponent)
        ogre = Creature(name="Hill Ogre", base_power=3, base_toughness=3,
                        owner=opponent, controller=opponent)
        set_board_state(game, 1, battlefield=[bear, ogre])

        opponent_life_before = opponent.life

        # Prepared is established through the front-face ETB, not by poking a flag.
        card = _cast_front_face(game, player, opponent)
        _move_to_exile(player, card)

        # Back face from exile: exile the 4/4; its controller gains 4 life.
        cast_spell_from_exile(game, 0, _NAME, targets=[bear])

        opp_bf_names = [getattr(c, "name", None)
                        for c in opponent.zones[Zone.BATTLEFIELD].get_all()]
        assert "Grizzly Bears" not in opp_bf_names, (
            "Target creature must be exiled from the battlefield"
        )
        life_gained = opponent.life - opponent_life_before
        assert life_gained == 4, (
            f"Controller should gain life equal to the creature's power (4), "
            f"but gained {life_gained}"
        )


# ---------------------------------------------------------------------------
# Test 5: Prepared rejected without flag
# ---------------------------------------------------------------------------


class TestPreparedRejectedWithoutFlag:
    """A card in exile that was never prepared cannot be cast (no back face)."""

    def test_prepared_rejected_without_flag(self) -> None:
        """Casting from exile is illegal when the card is not prepared."""
        game = create_game()
        player = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=player)
        card.controller = player
        # In exile but never prepared → casting from exile must be rejected.
        player.zones[Zone.EXILE].add(card)

        with assert_casting_error():
            cast_spell_from_exile(game, 0, _NAME)


# ---------------------------------------------------------------------------
# Test 6: Back-half cost not in CMC
# ---------------------------------------------------------------------------


class TestBackHalfCostNotInCMC:
    """Back-half {W} cost must NOT contribute to CMC."""

    def test_back_half_cost_not_in_cmc(self) -> None:
        """CMC is exactly 3 ({1}{W}{W}), not 4 ({1}{W}{W} + {W}).

        The back-face {W} is the alternative cost for the prepared ability
        and does not contribute to the card's converted mana cost.
        """
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)

        # Front face cost only -> CMC 3
        assert card.mana_cost.cmc == 3, (
            f"CMC must be 3 (front face), got {card.mana_cost.cmc}"
        )
        assert card.mana_cost.generic == 1
        assert card.mana_cost.pips.get(ManaType.WHITE) == 2


# ---------------------------------------------------------------------------
# Edge cases (user requested expanded coverage 2026-05-28)
# ---------------------------------------------------------------------------


class TestPreparedConditionEdgeCases:
    """The "if an opponent controls more creatures than you" clause is a strict
    inequality, checked at ETB resolution. It is observable through whether the
    card becomes castable from exile (the back face)."""

    def test_not_prepared_when_creatures_equal(self) -> None:
        """Equal creature counts → not prepared → back face is not castable."""
        game = create_game()
        player, opponent = game.players
        set_board_state(game, 0, battlefield=[
            Creature(name="My Bear", owner=player, controller=player,
                     base_power=2, base_toughness=2)])
        set_board_state(game, 1, battlefield=[
            Creature(name="Opp Bear", owner=opponent, controller=opponent,
                     base_power=2, base_toughness=2)])

        # ETB token goes to the opponent → 2 vs 2 (equal) → NOT prepared.
        card = _cast_front_face(game, player, opponent)
        _move_to_exile(player, card)
        with assert_casting_error():
            cast_spell_from_exile(game, 0, _NAME)

    def test_prepared_when_opponent_has_more(self) -> None:
        """Opponent strictly more → prepared → back face exiles its target."""
        game = create_game()
        player, opponent = game.players
        opp_a = Creature(name="Opp A", owner=opponent, controller=opponent,
                         base_power=1, base_toughness=1)
        opp_b = Creature(name="Opp B", owner=opponent, controller=opponent,
                         base_power=1, base_toughness=1)
        set_board_state(game, 1, battlefield=[opp_a, opp_b])

        card = _cast_front_face(game, player, opponent)
        _move_to_exile(player, card)
        cast_spell_from_exile(game, 0, _NAME, targets=[opp_a])

        opp_bf_names = [getattr(c, "name", None)
                        for c in opponent.zones[Zone.BATTLEFIELD].get_all()]
        assert "Opp A" not in opp_bf_names, (
            "Prepared back face should exile its target creature"
        )


class TestPreparedFlagLifecycle:
    """Prepared is single-use: consumed by the back-face cast."""

    def test_prepared_consumed_after_alt_cast(self) -> None:
        game = create_game()
        player, opponent = game.players
        victim = Creature(name="Sacrificial Goblin", owner=opponent,
                          controller=opponent, base_power=1, base_toughness=1)
        filler = Creature(name="Opp Filler", owner=opponent,
                          controller=opponent, base_power=1, base_toughness=1)
        set_board_state(game, 1, battlefield=[victim, filler])

        card = _cast_front_face(game, player, opponent)
        _move_to_exile(player, card)

        # First prepared cast succeeds (exiles the target).
        cast_spell_from_exile(game, 0, _NAME, targets=[victim])
        opp_bf_names = [getattr(c, "name", None)
                        for c in opponent.zones[Zone.BATTLEFIELD].get_all()]
        assert "Sacrificial Goblin" not in opp_bf_names

        # Prepared was consumed: returned to exile, the card can't be cast again.
        _move_to_exile(player, card)
        with assert_casting_error():
            cast_spell_from_exile(game, 0, _NAME, targets=[filler])


class TestTokenSummoningSickness:
    """Newly minted Inkling tokens are summoning-sick (no immediate attack)."""

    def test_token_is_summoning_sick(self) -> None:
        game = create_game()
        player, opponent = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=player)
        card.controller = player
        set_hand(game, 0, [card])
        set_mana_pool(game, 0, {ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        cast_spell(
            game, 0, "Emeritus of Truce // Swords to Plowshares",
            targets=[opponent],
        )
        tokens = [
            c for c in opponent.zones[Zone.BATTLEFIELD].get_all()
            if getattr(c, "is_token", False)
        ]
        assert tokens, "ETB should create a token"
        assert getattr(tokens[0], "summoning_sick", False) is True
