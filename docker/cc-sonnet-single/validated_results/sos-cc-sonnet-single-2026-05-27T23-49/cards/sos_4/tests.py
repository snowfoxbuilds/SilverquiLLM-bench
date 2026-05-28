"""Tests for SOS 4 — Together as One.

Together as One is a {6} Converge Sorcery:
  Converge — Target player draws X cards, Together as One deals X damage to
  any target, and you gain X life, where X is the number of colors of mana
  spent to cast this spell.

Three simultaneous effects driven by the same Converge X value:
  1. A chosen target player draws X cards.
  2. The spell deals X damage to "any target" (player or creature).
  3. The casting player gains X life.

The converge value is read from ``card.colors_spent`` (an int set by the
cast pipeline, mirroring the FDN 205 Wardens of the Cycle pattern).

Test strategy:
  - Static properties: name, mana_cost, card type.
  - Converge attribute defaults to 0.
  - on_resolve with colors_spent = 0 is a clean no-op.
  - Draws: target player hand grows by X.
  - Damage to a player: target player life decreases by X.
  - Damage to a creature: damage_marked increases by X.
  - Life gain: casting player life increases by X.
  - Multiple colors: all three effects scale with colors_spent.
  - Targeting API: get_targets returns two requirements (one for draw target
    player, one for damage target).
  - No-target / missing chosen_targets does not raise.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static property tests
# ---------------------------------------------------------------------------


class TestTogetherAsOneProperties:
    """Static card data must match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"

    def test_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}")

    def test_card_type_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.SORCERY in card.card_types


# ---------------------------------------------------------------------------
# Converge attribute initialisation
# ---------------------------------------------------------------------------


class TestTogetherAsOneConvergeAttribute:
    """colors_spent must be initialised to 0 (no colors spent by default)."""

    def test_colors_spent_defaults_to_zero(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.colors_spent == 0

    def test_colors_spent_is_integer(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card.colors_spent, int)


# ---------------------------------------------------------------------------
# Zero-color resolution (X = 0) — clean no-op
# ---------------------------------------------------------------------------


class TestTogetherAsOneZeroConverge:
    """When colors_spent is 0, all three effects should be a clean no-op."""

    def test_zero_colors_does_not_raise(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        # Provide chosen_targets with a draw target and a damage target
        card.chosen_targets = [p2, p1]
        card.on_resolve(game)  # must not raise

    def test_zero_colors_no_life_change(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p1]
        starting_life = p1.life
        card.on_resolve(game)
        assert p1.life == starting_life

    def test_zero_colors_no_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Give p2 some library cards so draws would be possible
        dummy = Creature(name="Dummy", base_power=1, base_toughness=1)
        p2.zones[Zone.LIBRARY].add(dummy)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p1]
        hand_before = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == hand_before

    def test_zero_colors_no_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p1]
        starting_life = p2.life
        card.on_resolve(game)
        assert p2.life == starting_life


# ---------------------------------------------------------------------------
# Draw effect: target player draws X cards
# ---------------------------------------------------------------------------


class TestTogetherAsOneDrawEffect:
    """The draw target player should draw exactly X cards."""

    def test_one_color_target_draws_one_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Put a card in p2's library so the draw works
        dummy = Creature(name="Dummy", base_power=1, base_toughness=1)
        p2.zones[Zone.LIBRARY].add(dummy)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        card.chosen_targets = [p2, p1]  # p2 = draw target, p1 = damage target
        hand_before = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == hand_before + 1

    def test_two_colors_target_draws_two_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        for i in range(3):
            p2.zones[Zone.LIBRARY].add(
                Creature(name=f"Lib{i}", base_power=1, base_toughness=1)
            )
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p2, p1]
        hand_before = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == hand_before + 2

    def test_three_colors_target_draws_three_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        for i in range(5):
            p2.zones[Zone.LIBRARY].add(
                Creature(name=f"Lib{i}", base_power=1, base_toughness=1)
            )
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p2, p1]
        hand_before = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == hand_before + 3

    def test_casting_player_can_also_be_draw_target(self) -> None:
        """The casting player can target themselves to draw."""
        game = create_game()
        p1 = game.players[0]
        for i in range(3):
            p1.zones[Zone.LIBRARY].add(
                Creature(name=f"Lib{i}", base_power=1, base_toughness=1)
            )
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        # p1 draws, and p1 also takes damage
        card.chosen_targets = [p1, p1]
        hand_before = len(p1.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 2


# ---------------------------------------------------------------------------
# Damage effect: X damage to any target
# ---------------------------------------------------------------------------


class TestTogetherAsOneDamageEffect:
    """The spell deals exactly X damage to the chosen damage target."""

    def test_one_color_deals_one_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p2_lib = Creature(name="Lib", base_power=1, base_toughness=1)
        p2.zones[Zone.LIBRARY].add(p2_lib)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        # draw target = p2, damage target = p2
        card.chosen_targets = [p2, p2]
        life_before = p2.life
        card.on_resolve(game)
        assert p2.life == life_before - 1

    def test_three_colors_deals_three_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        for i in range(5):
            p2.zones[Zone.LIBRARY].add(
                Creature(name=f"Lib{i}", base_power=1, base_toughness=1)
            )
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p2, p2]
        life_before = p2.life
        card.on_resolve(game)
        assert p2.life == life_before - 3

    def test_damage_to_creature_marks_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        for i in range(3):
            p2.zones[Zone.LIBRARY].add(
                Creature(name=f"Lib{i}", base_power=1, base_toughness=1)
            )
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        # draw target = p2, damage target = creature
        card.chosen_targets = [p2, creature]
        card.on_resolve(game)
        assert creature.damage_marked == 2

    def test_five_colors_deals_five_damage_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        creature = Creature(name="Big Target", base_power=3, base_toughness=6)
        set_board_state(game, 1, battlefield=[creature])
        for i in range(6):
            p2.zones[Zone.LIBRARY].add(
                Creature(name=f"Lib{i}", base_power=1, base_toughness=1)
            )
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p2, creature]
        card.on_resolve(game)
        assert creature.damage_marked == 5


# ---------------------------------------------------------------------------
# Life gain effect: casting player gains X life
# ---------------------------------------------------------------------------


class TestTogetherAsOneLifeGain:
    """The casting player gains exactly X life."""

    def test_one_color_gains_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p2.zones[Zone.LIBRARY].add(
            Creature(name="Lib", base_power=1, base_toughness=1)
        )
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        card.chosen_targets = [p2, p2]
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before + 1

    def test_three_colors_gains_three_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        for i in range(4):
            p2.zones[Zone.LIBRARY].add(
                Creature(name=f"Lib{i}", base_power=1, base_toughness=1)
            )
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p2, p2]
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before + 3

    def test_five_colors_gains_five_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        for i in range(6):
            p2.zones[Zone.LIBRARY].add(
                Creature(name=f"Lib{i}", base_power=1, base_toughness=1)
            )
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p2, p2]
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before + 5


# ---------------------------------------------------------------------------
# All three effects fire together
# ---------------------------------------------------------------------------


class TestTogetherAsOneAllEffects:
    """All three effects should trigger simultaneously with the same X."""

    def test_two_colors_all_three_effects(self) -> None:
        """With X=2: p2 draws 2, p2 loses 2 life, p1 gains 2 life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        for i in range(3):
            p2.zones[Zone.LIBRARY].add(
                Creature(name=f"Lib{i}", base_power=1, base_toughness=1)
            )
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p2, p2]
        p1_life_before = p1.life
        p2_life_before = p2.life
        p2_hand_before = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == p2_hand_before + 2
        assert p2.life == p2_life_before - 2
        assert p1.life == p1_life_before + 2


# ---------------------------------------------------------------------------
# Targeting API
# ---------------------------------------------------------------------------


class TestTogetherAsOneTargeting:
    """get_targets() should declare two targeting requirements."""

    def test_get_targets_returns_list(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        result = card.get_targets(game)
        assert isinstance(result, list)

    def test_get_targets_returns_two_requirements(self) -> None:
        """One requirement for the draw target, one for the damage target."""
        game = create_game()
        card = TogetherAsOne(owner=None)
        result = card.get_targets(game)
        assert len(result) == 2

    def test_no_chosen_targets_does_not_raise(self) -> None:
        """on_resolve with no chosen_targets should be a no-op, not raise."""
        game = create_game()
        p1 = game.players[0]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        # No chosen_targets set
        card.on_resolve(game)  # must not raise
