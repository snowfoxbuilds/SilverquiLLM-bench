"""Tests for sos_4 — Together as One (Converge Sorcery).

Covers:
- Static properties: name, mana cost, card type, colors_spent default
- Converge X=0: no draw, no damage, no life gain
- Converge X=1: draw 1, deal 1 damage, gain 1 life
- Converge X=2: draw 2, deal 2 damage, gain 2 life
- Converge X=5: draw 5, deal 5 damage, gain 5 life (maximum)
- Draw goes to the TARGET player, not always the controller
- Damage can target a player OR a creature
"""
from __future__ import annotations

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import CardImpl, Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


def _populate_library(player, count: int = 10) -> None:
    """Add blank cards to player's library for draw tests."""
    for i in range(count):
        player.zones[Zone.LIBRARY].add(CardImpl(name=f"LibCard{i}", owner=player))


class TestTogetherAsOneProperties:
    """Static card data should match the sos_4 spec."""

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"

    def test_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}")

    def test_has_sorcery_card_type(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_colors_spent_defaults_to_zero(self) -> None:
        """Converge attribute must exist and default to 0 before casting."""
        card = TogetherAsOne(owner=None)
        assert card.colors_spent == 0


class TestTogetherAsOneConvergeZero:
    """X=0 (no colors spent): draw 0, 0 damage, 0 life gain."""

    def test_zero_colors_no_draw(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        _populate_library(p2)
        card.chosen_targets = [p2, p2]
        initial_hand = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == initial_hand

    def test_zero_colors_no_damage(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p2]
        initial_life_p2 = p2.life
        card.on_resolve(game)
        assert p2.life == initial_life_p2

    def test_zero_colors_no_life_gain(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p2]
        initial_life_p1 = p1.life
        card.on_resolve(game)
        assert p1.life == initial_life_p1


class TestTogetherAsOneConvergeOne:
    """X=1: target player draws 1, deals 1 damage, controller gains 1 life."""

    def test_one_color_target_player_draws_one(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        _populate_library(p2)
        card.chosen_targets = [p2, p2]
        initial_hand = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == initial_hand + 1

    def test_one_color_deals_one_damage(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        card.chosen_targets = [p2, p2]
        initial_life_p2 = p2.life
        card.on_resolve(game)
        assert p2.life == initial_life_p2 - 1

    def test_one_color_controller_gains_one_life(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        card.chosen_targets = [p2, p2]
        initial_life_p1 = p1.life
        card.on_resolve(game)
        assert p1.life == initial_life_p1 + 1


class TestTogetherAsOneConvergeTwo:
    """X=2: all three effects scale to 2."""

    def test_two_colors_target_player_draws_two(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        _populate_library(p2)
        card.chosen_targets = [p2, p2]
        initial_hand = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == initial_hand + 2

    def test_two_colors_deals_two_damage(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p2, p2]
        initial_life_p2 = p2.life
        card.on_resolve(game)
        assert p2.life == initial_life_p2 - 2

    def test_two_colors_controller_gains_two_life(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p2, p2]
        initial_life_p1 = p1.life
        card.on_resolve(game)
        assert p1.life == initial_life_p1 + 2


class TestTogetherAsOneConvergeFive:
    """X=5 (maximum — all five colors spent): all effects at full scale."""

    def test_five_colors_target_player_draws_five(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        _populate_library(p2, count=20)
        card.chosen_targets = [p2, p2]
        initial_hand = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == initial_hand + 5

    def test_five_colors_deals_five_damage(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p2, p2]
        initial_life_p2 = p2.life
        card.on_resolve(game)
        assert p2.life == initial_life_p2 - 5

    def test_five_colors_controller_gains_five_life(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p2, p2]
        initial_life_p1 = p1.life
        card.on_resolve(game)
        assert p1.life == initial_life_p1 + 5


class TestTogetherAsOneDrawTarget:
    """The TARGET PLAYER draws cards -- not always the controller."""

    def test_draw_target_is_opponent_not_controller(self) -> None:
        """When p2 is the draw target, p2 draws X and p1 draws 0."""
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        _populate_library(p2)
        card.chosen_targets = [p2, p2]
        initial_hand_p1 = len(p1.zones[Zone.HAND].get_all())
        initial_hand_p2 = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == initial_hand_p2 + 3
        assert len(p1.zones[Zone.HAND].get_all()) == initial_hand_p1  # controller did NOT draw

    def test_draw_target_can_be_controller(self) -> None:
        """When controller is named as the draw target, controller draws X."""
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        _populate_library(p1)
        # Draw target = p1 (controller); damage target = p2
        card.chosen_targets = [p1, p2]
        initial_hand_p1 = len(p1.zones[Zone.HAND].get_all())
        initial_hand_p2 = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p1.zones[Zone.HAND].get_all()) == initial_hand_p1 + 2
        assert len(p2.zones[Zone.HAND].get_all()) == initial_hand_p2  # p2 did NOT draw


class TestTogetherAsOneDamageFlexibility:
    """Damage can hit 'any target' -- a player OR a creature."""

    def test_damage_targets_player(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p2, p2]
        initial_life = p2.life
        card.on_resolve(game)
        assert p2.life == initial_life - 2

    def test_damage_targets_creature(self) -> None:
        """Damage can be aimed at a creature; it uses damage_marked."""
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        _populate_library(p1)
        creature = Creature(
            name="Bear", base_power=2, base_toughness=4, owner=p2, controller=p2
        )
        game.get_battlefield(p2).add(creature)
        # Draw target = p1, damage target = creature
        card.chosen_targets = [p1, creature]
        initial_damage = creature.damage_marked
        card.on_resolve(game)
        assert creature.damage_marked == initial_damage + 3
