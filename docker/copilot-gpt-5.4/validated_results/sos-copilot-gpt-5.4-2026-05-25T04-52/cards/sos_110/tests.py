"""Tests for SOS 110 — Charging Strifeknight."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_110.card_impl import ChargingStrifeknight
from benchmarks.sos.workspace.engine.card import ActivatedAbility, CardImpl, Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestChargingStrifeknightProperties:
    """Static card data should match the SOS 110 spec."""

    def test_is_spirit_knight_with_haste(self) -> None:
        card = ChargingStrifeknight(owner=None)
        assert isinstance(card, Creature)
        assert "Spirit" in card.subtypes
        assert "Knight" in card.subtypes
        assert Keyword.HASTE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = ChargingStrifeknight(owner=None)
        assert card.name == "Charging Strifeknight"
        assert card.mana_cost == ManaCost.parse("{2}{R}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestChargingStrifeknightActivatedAbility:
    """Charging Strifeknight should tap, discard, and then draw a card."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = ChargingStrifeknight(owner=None).get_activated_abilities()
        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_taps_this_creature_and_discards_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ChargingStrifeknight(owner=p1, controller=p1)
        discard_card = CardImpl(name="Spare Notes", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], hand=[discard_card])
        p1._script.append(discard_card)
        ability = card.get_activated_abilities()[0]

        assert ability.cost(game, card) is True
        assert card.is_tapped is True
        assert not game.get_hand(p1).contains(discard_card)
        assert game.get_graveyard(p1).contains(discard_card)

    def test_activation_cost_fails_if_this_creature_is_already_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ChargingStrifeknight(owner=p1, controller=p1)
        discard_card = CardImpl(name="Spare Notes", owner=p1, controller=p1)
        card.is_tapped = True
        set_board_state(game, 0, battlefield=[card], hand=[discard_card])
        p1._script.append(discard_card)
        ability = card.get_activated_abilities()[0]

        assert ability.cost(game, card) is False
        assert game.get_hand(p1).contains(discard_card)
        assert not game.get_graveyard(p1).contains(discard_card)

    def test_activation_cost_fails_without_a_card_to_discard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ChargingStrifeknight(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_activated_abilities()[0]

        assert ability.cost(game, card) is False
        assert card.is_tapped is False

    def test_effect_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        drawn = CardImpl(name="Fresh Lesson", owner=p1, controller=p1)
        game.get_library(p1).add(drawn)
        ability = ChargingStrifeknight(owner=p1, controller=p1).get_activated_abilities()[0]

        ability.effect(game)

        assert game.get_hand(p1).contains(drawn)
