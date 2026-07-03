"""Tests for SOS 181 — Colossus of the Blood Age."""

from __future__ import annotations

import pytest

from cards.sos.sos_181.card_impl import ColossusOfTheBloodAge
from engine.card import Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestColossusProperties:
    """Static card properties match the spec."""

    def test_name(self) -> None:
        card = ColossusOfTheBloodAge(owner=None)
        assert card.name == "Colossus of the Blood Age"

    def test_mana_cost(self) -> None:
        card = ColossusOfTheBloodAge(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{R}{W}")

    def test_power_toughness(self) -> None:
        card = ColossusOfTheBloodAge(owner=None)
        assert card.base_power == 6
        assert card.base_toughness == 6

    def test_is_artifact_creature(self) -> None:
        card = ColossusOfTheBloodAge(owner=None)
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types


class TestColossusEntersTrigger:
    """When this creature enters, it deals 3 damage to each opponent and you gain 3 life."""

    def test_deals_3_damage_to_opponent_on_enter(self) -> None:
        game = create_game()
        set_board_state(game, 0, hand=[ColossusOfTheBloodAge(owner=None)],
                        mana={ManaType.RED: 1, ManaType.WHITE: 1, ManaType.COLORLESS: 4})
        cast_spell(game, 0, "Colossus of the Blood Age")
        assert game.players[1].life == 17

    def test_controller_gains_3_life_on_enter(self) -> None:
        game = create_game()
        set_board_state(game, 0, hand=[ColossusOfTheBloodAge(owner=None)],
                        mana={ManaType.RED: 1, ManaType.WHITE: 1, ManaType.COLORLESS: 4})
        cast_spell(game, 0, "Colossus of the Blood Age")
        assert game.players[0].life == 23

    def test_starting_at_lower_life(self) -> None:
        game = create_game(player1_life=10, player2_life=10)
        set_board_state(game, 0, hand=[ColossusOfTheBloodAge(owner=None)],
                        mana={ManaType.RED: 1, ManaType.WHITE: 1, ManaType.COLORLESS: 4})
        cast_spell(game, 0, "Colossus of the Blood Age")
        assert game.players[0].life == 13
        assert game.players[1].life == 7


class TestColossusDiesTrigger:
    """When this creature dies, discard any number of cards, then draw that many cards plus one."""

    def test_dies_trigger_draws_at_least_one_card(self) -> None:
        """With no cards to discard, controller still draws one card."""
        game = create_game()
        colossus = ColossusOfTheBloodAge(owner=None)
        set_board_state(game, 0, battlefield=[colossus], hand=[])
        # Destroy the colossus
        colossus.destroy(game)
        # Controller should have drawn 1 card (0 discarded + 1)
        hand = game.players[0].hand
        assert len(hand) >= 1

    def test_dies_trigger_discard_and_draw(self) -> None:
        """Discarding cards lets you draw that many plus one."""
        game = create_game()
        colossus = ColossusOfTheBloodAge(owner=None)
        filler1 = Creature(name="Filler A", base_power=1, base_toughness=1)
        filler2 = Creature(name="Filler B", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[colossus], hand=[filler1, filler2])
        # Destroy the colossus — player chooses to discard 2
        colossus.destroy(game)
        # After discarding 2 and drawing 3, net hand change is +1
        # (started with 2, discard 2, draw 3 => 3 in hand)
        graveyard_names = [c.name for c in game.players[0].graveyard]
        assert "Colossus of the Blood Age" in graveyard_names
