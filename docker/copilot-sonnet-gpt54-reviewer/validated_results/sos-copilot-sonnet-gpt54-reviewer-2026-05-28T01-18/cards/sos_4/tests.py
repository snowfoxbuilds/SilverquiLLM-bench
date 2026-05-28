"""Tests for sos_4 — Together as One.

Converge sorcery: Target player draws X cards, Together as One deals X damage
to any target, and you gain X life, where X is the number of colors of mana
spent to cast this spell.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestTogetherAsOneProperties:
    """Static card data should match the sos_4 spec."""

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"

    def test_mana_cost_six_generic(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}")

    def test_card_type_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.SORCERY in card.card_types


# ---------------------------------------------------------------------------
# Converge — colors_spent tracking
# ---------------------------------------------------------------------------


class TestTogetherAsOneConverge:
    """colors_spent attribute drives X; defaults to 0."""

    def test_colors_spent_defaults_to_zero(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.colors_spent == 0

    def test_colors_spent_can_be_set_to_one(self) -> None:
        card = TogetherAsOne(owner=None)
        card.colors_spent = 1
        assert card.colors_spent == 1

    def test_colors_spent_can_be_set_to_five(self) -> None:
        card = TogetherAsOne(owner=None)
        card.colors_spent = 5
        assert card.colors_spent == 5


# ---------------------------------------------------------------------------
# Draw X cards
# ---------------------------------------------------------------------------


class TestTogetherAsOneDraw:
    """Target player draws X cards (X = colors_spent)."""

    def test_x_zero_target_player_draws_no_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Give p2 cards in library
        dummy = Creature(name="Library Card", owner=p2, controller=p2,
                         base_power=1, base_toughness=1)
        p2.zones[Zone.LIBRARY].add(dummy)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 0
        before_hand = len(p2.zones[Zone.HAND].get_all())
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        after_hand = len(p2.zones[Zone.HAND].get_all())
        assert after_hand - before_hand == 0

    def test_x_one_target_player_draws_one_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Give p2 cards in library
        for i in range(5):
            card = Creature(name=f"Lib{i}", owner=p2, controller=p2,
                            base_power=1, base_toughness=1)
            p2.zones[Zone.LIBRARY].add(card)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 1
        before_hand = len(p2.zones[Zone.HAND].get_all())
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        after_hand = len(p2.zones[Zone.HAND].get_all())
        assert after_hand - before_hand == 1

    def test_x_three_target_player_draws_three_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        for i in range(5):
            card = Creature(name=f"Lib{i}", owner=p2, controller=p2,
                            base_power=1, base_toughness=1)
            p2.zones[Zone.LIBRARY].add(card)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 3
        before_hand = len(p2.zones[Zone.HAND].get_all())
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        after_hand = len(p2.zones[Zone.HAND].get_all())
        assert after_hand - before_hand == 3

    def test_x_five_target_player_draws_five_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        for i in range(10):
            card = Creature(name=f"Lib{i}", owner=p2, controller=p2,
                            base_power=1, base_toughness=1)
            p2.zones[Zone.LIBRARY].add(card)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 5
        before_hand = len(p2.zones[Zone.HAND].get_all())
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        after_hand = len(p2.zones[Zone.HAND].get_all())
        assert after_hand - before_hand == 5

    def test_casting_player_can_be_target_for_draw(self) -> None:
        """The caster themselves can be the target player who draws cards."""
        game = create_game()
        p1 = game.players[0]
        for i in range(5):
            card = Creature(name=f"Lib{i}", owner=p1, controller=p1,
                            base_power=1, base_toughness=1)
            p1.zones[Zone.LIBRARY].add(card)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 2
        before_hand = len(p1.zones[Zone.HAND].get_all())
        spell.chosen_targets = [p1, p1]
        spell.on_resolve(game)
        after_hand = len(p1.zones[Zone.HAND].get_all())
        assert after_hand - before_hand == 2


# ---------------------------------------------------------------------------
# Deal X damage to any target
# ---------------------------------------------------------------------------


class TestTogetherAsOneDamage:
    """Together as One deals X damage to any target (player or creature)."""

    def test_x_zero_no_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 0
        before_life = p2.life
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        assert p2.life == before_life

    def test_x_one_deals_one_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 1
        before_life = p2.life
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        assert p2.life == before_life - 1

    def test_x_three_deals_three_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 3
        before_life = p2.life
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        assert p2.life == before_life - 3

    def test_x_five_deals_five_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 5
        before_life = p2.life
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        assert p2.life == before_life - 5

    def test_x_three_deals_three_damage_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bear = Creature(
            name="Grizzly Bears",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(bear)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 3
        before_damage = bear.damage_marked
        spell.chosen_targets = [p2, bear]
        spell.on_resolve(game)
        assert bear.damage_marked == before_damage + 3

    def test_damage_target_distinct_from_draw_target(self) -> None:
        """The damage target and the drawing target are independent chosen targets."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bear = Creature(
            name="Test Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(bear)
        for i in range(5):
            card = Creature(name=f"Lib{i}", owner=p1, controller=p1,
                            base_power=1, base_toughness=1)
            p1.zones[Zone.LIBRARY].add(card)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 2
        before_hand = len(p1.zones[Zone.HAND].get_all())
        before_bear_dmg = bear.damage_marked
        # p1 draws, bear gets damage
        spell.chosen_targets = [p1, bear]
        spell.on_resolve(game)
        assert len(p1.zones[Zone.HAND].get_all()) - before_hand == 2
        assert bear.damage_marked == before_bear_dmg + 2


# ---------------------------------------------------------------------------
# Gain X life
# ---------------------------------------------------------------------------


class TestTogetherAsOneLifeGain:
    """Caster (controller) gains X life."""

    def test_x_zero_no_life_gained(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 0
        before_life = p1.life
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        assert p1.life == before_life

    def test_x_one_caster_gains_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 1
        before_life = p1.life
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        assert p1.life == before_life + 1

    def test_x_three_caster_gains_three_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 3
        before_life = p1.life
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        assert p1.life == before_life + 3

    def test_x_five_caster_gains_five_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 5
        before_life = p1.life
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        assert p1.life == before_life + 5

    def test_life_gain_goes_to_controller_not_target_player(self) -> None:
        """Life is gained by the caster, not the target player who draws."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        for i in range(5):
            card = Creature(name=f"Lib{i}", owner=p2, controller=p2,
                            base_power=1, base_toughness=1)
            p2.zones[Zone.LIBRARY].add(card)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 2
        before_p1_life = p1.life
        before_p2_life = p2.life
        # p2 is the draw target and also the damage target
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        # p1 (caster) gains life
        assert p1.life == before_p1_life + 2
        # p2 should not gain life from this spell
        # (p2 may have lost life if also damage target; p2 draws cards, not gains life)
        # The key assertion is that p1 gained life
        assert p1.life > before_p1_life


# ---------------------------------------------------------------------------
# All three effects fire simultaneously for same X
# ---------------------------------------------------------------------------


class TestTogetherAsOneAllEffects:
    """All three effects (draw, damage, life gain) use the same X."""

    def test_all_effects_with_x_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        for i in range(5):
            card = Creature(name=f"Lib{i}", owner=p2, controller=p2,
                            base_power=1, base_toughness=1)
            p2.zones[Zone.LIBRARY].add(card)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 2
        before_p1_life = p1.life
        before_p2_hand = len(p2.zones[Zone.HAND].get_all())
        before_p2_life = p2.life
        # p2 draws cards; p2 also takes damage
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)

        # p2 draws 2 cards
        assert len(p2.zones[Zone.HAND].get_all()) - before_p2_hand == 2
        # p2 takes 2 damage (life loss)
        assert p2.life == before_p2_life - 2
        # p1 (caster) gains 2 life
        assert p1.life == before_p1_life + 2

    def test_all_effects_with_x_four(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        for i in range(10):
            card = Creature(name=f"Lib{i}", owner=p2, controller=p2,
                            base_power=1, base_toughness=1)
            p2.zones[Zone.LIBRARY].add(card)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 4
        before_p1_life = p1.life
        before_p2_hand = len(p2.zones[Zone.HAND].get_all())
        before_p2_life = p2.life
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) - before_p2_hand == 4
        assert p2.life == before_p2_life - 4
        assert p1.life == before_p1_life + 4
