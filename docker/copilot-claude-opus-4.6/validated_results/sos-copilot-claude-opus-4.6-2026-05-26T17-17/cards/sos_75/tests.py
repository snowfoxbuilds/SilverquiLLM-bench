"""Tests for SOS 75 — Burrog Banemaker."""

from __future__ import annotations

import pytest

from cards.sos.sos_75.card_impl import BurrogBanemaker
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestBurrogBanemakerProperties:
    """Static card data should match the SOS 75 spec."""

    def test_is_creature(self) -> None:
        card = BurrogBanemaker(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert BurrogBanemaker(owner=None).name == "Burrog Banemaker"

    def test_mana_cost(self) -> None:
        assert BurrogBanemaker(owner=None).mana_cost == ManaCost.parse("{B}")

    def test_power_toughness(self) -> None:
        card = BurrogBanemaker(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_has_deathtouch(self) -> None:
        card = BurrogBanemaker(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords


class TestBurrogBanemakerActivatedAbility:
    """{1}{B}: This creature gets +1/+1 until end of turn."""

    def test_has_activated_ability(self) -> None:
        card = BurrogBanemaker(owner=None)
        assert len(card.activated_abilities) >= 1

    def test_ability_grants_plus_one_plus_one(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = BurrogBanemaker(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1})

        power_before = card.power
        toughness_before = card.toughness

        # Activate the ability
        card.activated_abilities[0].effect(game)

        assert card.power == power_before + 1
        assert card.toughness == toughness_before + 1

    def test_ability_stacks_multiple_activations(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = BurrogBanemaker(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.BLACK: 3, ManaType.COLORLESS: 3})

        power_before = card.power

        # Activate twice
        card.activated_abilities[0].effect(game)
        card.activated_abilities[0].effect(game)

        assert card.power == power_before + 2
        assert card.toughness == 3  # 1 base + 2 pumps

    def test_pump_is_until_end_of_turn(self) -> None:
        """The +1/+1 bonus should expire at end of turn."""
        game = create_game()
        p1 = game.players[0]

        card = BurrogBanemaker(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1})

        card.activated_abilities[0].effect(game)
        assert card.power == 2

        # Simulate end of turn cleanup
        card.end_of_turn_cleanup(game)
        assert card.power == 1
        assert card.toughness == 1
