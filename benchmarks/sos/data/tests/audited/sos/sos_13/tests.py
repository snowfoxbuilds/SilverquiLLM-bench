"""Audited tests for Emeritus of Truce // Swords to Plowshares (sos_13).

Oracle (front face — Creature {1}{W}{W} 3/3 Cat Cleric):
  When this creature enters, target player creates a 2/1 white and black
  Inkling creature token with flying.  Then if an opponent controls more
  creatures than you, this creature becomes prepared.
Oracle (back face — Instant, cast via Prepared from exile for {W}):
  Exile target creature.  Its controller gains life equal to its power.

Simulation-only shape (AUDITED-TEST-API.md): the prepared state is never
injected via a private flag — it is established through gameplay (the
front-face cast resolving while an opponent controls more creatures) and
observed through outcomes: whether the back face is castable from exile
(``CastSpell(..., from_zone=Zone.EXILE)`` → the test-layer
cast-from-exile helper), the creature it exiles, and the life its controller
gains.  Reaching exile itself is test setup (``set_board_state(exile=...)``).

Tests:
  1. test_card_identity (CMC is 3 — the back-face {W} alt cost does not
     contribute)
  2. test_etb_creates_inkling_for_target_player
  3. test_etb_token_can_be_given_to_self
  4. test_prepared_back_face_exiles_creature_and_grants_life
  5. test_not_prepared_when_creature_counts_equal
  6. test_prepared_consumed_after_back_face_cast
"""

from __future__ import annotations

from card_impl import EmeritusOfTruceSwordsToPlowshares

from engine.card import Creature
from engine.types import CardType, ManaType, Phase, Zone
from test_utils import (
    CastSpell,
    DeterministicPlayer,
    advance_to_phase,
    assert_in_zone,
    assert_life_total,
    assert_power_toughness,
    assert_stack_empty,
    assert_zone_count,
    create_game,
    no_op,
    perform_action,
    perform_illegal_action,
    priority_loop,
    set_board_state,
    set_player,
)

_NAME = "Emeritus of Truce // Swords to Plowshares"
_FRONT_FACE_MANA = {ManaType.WHITE: 2, ManaType.COLORLESS: 1}


def _cast_front_face(game, target_player_index: int):
    """Cast the front-face creature from hand targeting a player; return the
    card object (now on player 0's battlefield after its ETB resolves)."""
    card = EmeritusOfTruceSwordsToPlowshares()
    set_board_state(game, 0, hand=[card], mana=_FRONT_FACE_MANA)
    set_player(game, 0, DeterministicPlayer("P0", script=[
        perform_action(CastSpell(_NAME, targets=[game.players[target_player_index]])),
        no_op(),
    ]))
    set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
    priority_loop(game)
    assert_in_zone(game, 0, Zone.BATTLEFIELD, _NAME)
    return card


class TestIdentity:
    def test_card_identity(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == _NAME
        # Front face cost {1}{W}{W}; the back-face {W} alternative cost does
        # NOT contribute to the converted mana cost.
        assert card.mana_cost.generic == 1
        assert card.mana_cost.pips.get(ManaType.WHITE) == 2
        assert card.mana_cost.cmc == 3
        assert CardType.CREATURE in card.card_types
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestETBToken:
    def test_etb_creates_inkling_for_target_player(self) -> None:
        """Casting the front face creates a 2/1 Inkling on the targeted
        player's battlefield."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        _cast_front_face(game, target_player_index=1)

        assert_in_zone(game, 1, Zone.BATTLEFIELD, "Inkling")
        assert_power_toughness(game, "Inkling", 2, 1)
        # The token went to the chosen player only.
        assert_zone_count(game, 1, Zone.BATTLEFIELD, 1)
        assert_stack_empty(game)

    def test_etb_token_can_be_given_to_self(self) -> None:
        """'Target player' may be the controller — the token lands on the
        controller's battlefield and the opponent gets nothing."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        _cast_front_face(game, target_player_index=0)

        assert_in_zone(game, 0, Zone.BATTLEFIELD, "Inkling")
        assert_zone_count(game, 1, Zone.BATTLEFIELD, 0)


class TestPreparedBackFace:
    def test_prepared_back_face_exiles_creature_and_grants_life(self) -> None:
        """With an opponent controlling more creatures, the ETB makes the
        card prepared; from exile the back face exiles the targeted creature
        and its controller gains life equal to its power."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        bear = Creature(name="Grizzly Bears", base_power=4, base_toughness=4)
        ogre = Creature(name="Hill Ogre", base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[bear, ogre])

        # ETB token goes to the opponent → opponent 3 creatures vs our 1 →
        # prepared (established through gameplay, not a flag poke).
        card = _cast_front_face(game, target_player_index=1)

        # Setup: place the prepared card in exile (the one place a test may
        # write state directly).
        set_board_state(game, 0, battlefield=[], exile=[card])

        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_action(CastSpell(
                _NAME, targets=["Grizzly Bears"], from_zone=Zone.EXILE,
            )),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
        priority_loop(game)

        # The 4/4 was exiled and its controller gained 4 life.
        assert_in_zone(game, 1, Zone.EXILE, "Grizzly Bears")
        assert_life_total(game, 1, 24)
        assert_in_zone(game, 1, Zone.BATTLEFIELD, "Hill Ogre")

    def test_not_prepared_when_creature_counts_equal(self) -> None:
        """The prepared clause is a strict inequality: with equal creature
        counts after the ETB, the card is not prepared and the back face
        cannot be cast from exile."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        my_bear = Creature(name="My Bear", base_power=2, base_toughness=2)
        opp_bear = Creature(name="Opp Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[my_bear])
        set_board_state(game, 1, battlefield=[opp_bear])

        # Token to the opponent → 2 vs 2 (equal) → NOT prepared.
        card = _cast_front_face(game, target_player_index=1)
        set_board_state(game, 0, battlefield=[my_bear], exile=[card])

        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_illegal_action(CastSpell(
                _NAME, targets=["Opp Bear"], from_zone=Zone.EXILE,
            )),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
        priority_loop(game)

        # The card stayed in exile; the would-be target is untouched.
        assert_in_zone(game, 0, Zone.EXILE, _NAME)
        assert_in_zone(game, 1, Zone.BATTLEFIELD, "Opp Bear")
        assert_life_total(game, 1, 20)

    def test_prepared_consumed_after_back_face_cast(self) -> None:
        """Prepared is single-use: after the back-face cast it is consumed,
        and a re-exiled card cannot be cast again."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        victim = Creature(name="Sacrificial Goblin", base_power=1, base_toughness=1)
        filler = Creature(name="Opp Filler", base_power=1, base_toughness=1)
        set_board_state(game, 1, battlefield=[victim, filler])

        card = _cast_front_face(game, target_player_index=1)
        set_board_state(game, 0, battlefield=[], exile=[card])

        # First prepared cast succeeds (exiles the victim).
        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_action(CastSpell(
                _NAME, targets=["Sacrificial Goblin"], from_zone=Zone.EXILE,
            )),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
        priority_loop(game)
        assert_in_zone(game, 1, Zone.EXILE, "Sacrificial Goblin")

        # Prepared was consumed: back in exile, the card can't be cast again.
        set_board_state(game, 0, battlefield=[], exile=[card])
        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_illegal_action(CastSpell(
                _NAME, targets=["Opp Filler"], from_zone=Zone.EXILE,
            )),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
        priority_loop(game)

        assert_in_zone(game, 0, Zone.EXILE, _NAME)
        assert_in_zone(game, 1, Zone.BATTLEFIELD, "Opp Filler")
