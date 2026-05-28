"""Tests for SOS 4 — Together as One.

Requirements under test:
1. Static properties: Sorcery type, name "Together as One", mana cost {6}.
2. Converge attribute: colors_spent defaults to 0.
3. on_resolve with X=0 (no colored mana): draws 0, deals 0 damage, gains 0 life.
4. on_resolve with X=1: draws 1 card for the target player, deals 1 damage to a
   target, and controller gains 1 life.
5. on_resolve with X=3: draws 3, deals 3 damage, gains 3 life.
6. on_resolve with X=5 (all 5 colors): draws 5, deals 5 damage, gains 5 life.
7. Damage can target a player (reduces life).
8. Damage can target a creature (marks damage on the creature).
9. Life gain is credited to the *controller*, not necessarily the target player.
10. The target player draws X cards (not necessarily the controller).
"""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestTogetherAsOneProperties:
    """Static characteristics should match the SOS 4 card spec."""

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)

    def test_card_type_includes_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")


# ---------------------------------------------------------------------------
# Converge attribute — colors_spent default
# ---------------------------------------------------------------------------


class TestTogetherAsOneConverge:
    """The converge attribute should default to 0 and be settable by the cast
    pipeline or test code."""

    def test_colors_spent_defaults_to_zero(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.colors_spent == 0

    def test_colors_spent_is_settable(self) -> None:
        card = TogetherAsOne(owner=None)
        card.colors_spent = 3
        assert card.colors_spent == 3


# ---------------------------------------------------------------------------
# on_resolve: X = 0 (no colored mana spent)
# ---------------------------------------------------------------------------


class TestTogetherAsOneResolveXZero:
    """With X=0, no cards are drawn, no damage is dealt, no life is gained."""

    def test_x_zero_no_cards_drawn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        # p2 is the target player for drawing
        card.chosen_targets = [p2, p2]
        before_hand = len(game.get_hand(p2).get_all())
        card.on_resolve(game)
        assert len(game.get_hand(p2).get_all()) == before_hand

    def test_x_zero_no_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p2]
        before_life = p2.life
        card.on_resolve(game)
        assert p2.life == before_life

    def test_x_zero_no_life_gained(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p2]
        before_life = p1.life
        card.on_resolve(game)
        assert p1.life == before_life


# ---------------------------------------------------------------------------
# on_resolve: X = 1 (one color spent)
# ---------------------------------------------------------------------------


class TestTogetherAsOneResolveXOne:
    """With X=1, target player draws 1, damage target takes 1, controller gains 1."""

    def test_x_one_target_player_draws_one_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Give p2 a library to draw from
        dummy = Creature(name="Library Card", base_power=1, base_toughness=1,
                         owner=p2, controller=p2)
        game.get_library(p2).add(dummy)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        # Target player is p2 for draw; damage target is also p2
        card.chosen_targets = [p2, p2]
        before_hand = len(game.get_hand(p2).get_all())
        card.on_resolve(game)
        assert len(game.get_hand(p2).get_all()) == before_hand + 1

    def test_x_one_damage_target_player_takes_one_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        card.chosen_targets = [p2, p2]
        before_life = p2.life
        card.on_resolve(game)
        assert p2.life == before_life - 1

    def test_x_one_controller_gains_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        card.chosen_targets = [p2, p2]
        before_life = p1.life
        card.on_resolve(game)
        assert p1.life == before_life + 1


# ---------------------------------------------------------------------------
# on_resolve: X = 3 (three colors spent)
# ---------------------------------------------------------------------------


class TestTogetherAsOneResolveXThree:
    """With X=3, all three effects scale to 3."""

    def test_x_three_target_player_draws_three_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        for i in range(5):
            dummy = Creature(name=f"Library Card {i}", base_power=1, base_toughness=1,
                             owner=p2, controller=p2)
            game.get_library(p2).add(dummy)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p2, p2]
        before_hand = len(game.get_hand(p2).get_all())
        card.on_resolve(game)
        assert len(game.get_hand(p2).get_all()) == before_hand + 3

    def test_x_three_damage_target_takes_three(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p2, p2]
        before_life = p2.life
        card.on_resolve(game)
        assert p2.life == before_life - 3

    def test_x_three_controller_gains_three_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p2, p2]
        before_life = p1.life
        card.on_resolve(game)
        assert p1.life == before_life + 3


# ---------------------------------------------------------------------------
# on_resolve: X = 5 (all five colors spent)
# ---------------------------------------------------------------------------


class TestTogetherAsOneResolveXFive:
    """With X=5 (all five colors), all effects scale to 5."""

    def test_x_five_target_player_draws_five_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        for i in range(7):
            dummy = Creature(name=f"Library Card {i}", base_power=1, base_toughness=1,
                             owner=p2, controller=p2)
            game.get_library(p2).add(dummy)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p2, p2]
        before_hand = len(game.get_hand(p2).get_all())
        card.on_resolve(game)
        assert len(game.get_hand(p2).get_all()) == before_hand + 5

    def test_x_five_damage_target_takes_five(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p2, p2]
        before_life = p2.life
        card.on_resolve(game)
        assert p2.life == before_life - 5

    def test_x_five_controller_gains_five_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p2, p2]
        before_life = p1.life
        card.on_resolve(game)
        assert p1.life == before_life + 5


# ---------------------------------------------------------------------------
# Damage targets any target — creature target
# ---------------------------------------------------------------------------


class TestTogetherAsOneDamageTargetCreature:
    """Damage can be directed at a creature, marking damage on it."""

    def test_damage_marks_on_creature_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        creature = Creature(
            name="Test Bear",
            base_power=3,
            base_toughness=3,
            owner=p2,
            controller=p2,
        )
        game.get_battlefield(p2).add(creature)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        # Target player for draw is p2; damage target is creature
        card.chosen_targets = [p2, creature]
        before_damage = creature.damage_marked
        card.on_resolve(game)
        assert creature.damage_marked == before_damage + 2

    def test_damage_to_creature_does_not_reduce_player_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        creature = Creature(
            name="Test Bear",
            base_power=3,
            base_toughness=3,
            owner=p2,
            controller=p2,
        )
        game.get_battlefield(p2).add(creature)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p2, creature]
        before_life_p2 = p2.life
        card.on_resolve(game)
        # p2 took no life loss — the creature absorbed the damage
        assert p2.life == before_life_p2


# ---------------------------------------------------------------------------
# Life gain goes to controller, not necessarily the draw target
# ---------------------------------------------------------------------------


class TestTogetherAsOneLifeGainToController:
    """The 'you gain X life' clause benefits the controller."""

    def test_life_gain_credits_controller_not_draw_target(self) -> None:
        """When p2 is the draw target, p1 (controller) still gains the life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        # p2 draws; p2 is also the damage target
        card.chosen_targets = [p2, p2]
        before_p1_life = p1.life
        before_p2_life = p2.life
        card.on_resolve(game)
        # Controller gains life
        assert p1.life == before_p1_life + 2
        # p2 loses life from damage
        assert p2.life == before_p2_life - 2
