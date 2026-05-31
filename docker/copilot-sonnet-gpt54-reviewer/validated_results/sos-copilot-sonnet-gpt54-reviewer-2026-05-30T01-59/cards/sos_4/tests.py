"""Tests for SOS 4 — Together as One.

Converge: X = number of distinct colors of mana spent to cast.
Effects: target player draws X cards, deals X damage to any target,
         controller gains X life.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestTogetherAsOneProperties:
    def test_name(self) -> None:
        card = TogetherAsOne()
        assert card.name == "Together as One"

    def test_mana_cost(self) -> None:
        card = TogetherAsOne()
        assert card.mana_cost == ManaCost.parse("{6}")

    def test_card_type_is_sorcery(self) -> None:
        card = TogetherAsOne()
        assert CardType.SORCERY in card.card_types

    def test_colors_spent_defaults_to_zero(self) -> None:
        card = TogetherAsOne()
        assert card._converge_x() == 0

    def test_converge_x_from_int(self) -> None:
        card = TogetherAsOne()
        card.colors_spent = 3
        assert card._converge_x() == 3

    def test_converge_x_from_list(self) -> None:
        from engine.types import Color
        card = TogetherAsOne()
        card.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK]
        assert card._converge_x() == 3


# ---------------------------------------------------------------------------
# X == 0: no effects
# ---------------------------------------------------------------------------


class TestConvergeZero:
    def test_x_zero_no_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0

        # give p2 a card to draw
        dummy = TogetherAsOne(owner=p2, controller=p2)
        set_board_state(game, 1, hand=[dummy])

        hand_before = len(game.get_hand(p2).get_all())
        card.chosen_targets = [p2, p1]
        card.on_resolve(game)
        assert len(game.get_hand(p2).get_all()) == hand_before

    def test_x_zero_no_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p2]
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before

    def test_x_zero_no_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p2]
        life_before = p2.life
        card.on_resolve(game)
        assert p2.life == life_before


# ---------------------------------------------------------------------------
# X > 0: effects scale with X
# ---------------------------------------------------------------------------


class TestConvergeEffects:
    """All effects bypass the cast pipeline by setting colors_spent and
    chosen_targets directly, exactly as the fdn_205 reference tests do."""

    def _setup(self, x: int):
        """Return (game, p1, p2, card) with colors_spent=x."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = x
        return game, p1, p2, card

    # --- Draw ---

    def test_x2_target_player_draws_two_cards(self) -> None:
        game, p1, p2, card = self._setup(2)
        # Give p2 cards in library
        lib_cards = [TogetherAsOne(owner=p2) for _ in range(5)]
        for c in lib_cards:
            p2.zones[Zone.LIBRARY].add(c)

        hand_before = len(game.get_hand(p2).get_all())
        card.chosen_targets = [p2, p1]
        card.on_resolve(game)
        assert len(game.get_hand(p2).get_all()) == hand_before + 2

    def test_x3_target_player_draws_three_cards(self) -> None:
        game, p1, p2, card = self._setup(3)
        lib_cards = [TogetherAsOne(owner=p2) for _ in range(5)]
        for c in lib_cards:
            p2.zones[Zone.LIBRARY].add(c)

        hand_before = len(game.get_hand(p2).get_all())
        card.chosen_targets = [p2, p1]
        card.on_resolve(game)
        assert len(game.get_hand(p2).get_all()) == hand_before + 3

    def test_x1_controller_can_target_self_for_draw(self) -> None:
        game, p1, p2, card = self._setup(1)
        lib_cards = [TogetherAsOne(owner=p1) for _ in range(3)]
        for c in lib_cards:
            p1.zones[Zone.LIBRARY].add(c)

        hand_before = len(game.get_hand(p1).get_all())
        card.chosen_targets = [p1, p2]
        card.on_resolve(game)
        assert len(game.get_hand(p1).get_all()) == hand_before + 1

    # --- Damage to player ---

    def test_x3_deals_three_damage_to_player(self) -> None:
        game, p1, p2, card = self._setup(3)
        card.chosen_targets = [p1, p2]
        life_before = p2.life
        card.on_resolve(game)
        assert p2.life == life_before - 3

    def test_x5_deals_five_damage_to_player(self) -> None:
        game, p1, p2, card = self._setup(5)
        card.chosen_targets = [p1, p2]
        life_before = p2.life
        card.on_resolve(game)
        assert p2.life == life_before - 5

    # --- Damage to creature ---

    def test_x2_deals_two_damage_to_creature(self) -> None:
        game, p1, p2, card = self._setup(2)
        creature = Creature(
            name="Test Creature",
            base_power=2,
            base_toughness=4,
            owner=p2,
            controller=p2,
        )
        set_board_state(game, 1, battlefield=[creature])

        card.chosen_targets = [p1, creature]
        card.on_resolve(game)
        assert creature.damage_marked == 2

    def test_x4_kills_small_creature(self) -> None:
        from engine.state_based_actions import resolve_state_based_actions

        game, p1, p2, card = self._setup(4)
        creature = Creature(
            name="Small Creature",
            base_power=1,
            base_toughness=2,
            owner=p2,
            controller=p2,
        )
        set_board_state(game, 1, battlefield=[creature])

        card.chosen_targets = [p1, creature]
        card.on_resolve(game)
        resolve_state_based_actions(game)

        # Creature took 4 damage (> toughness 2) → goes to graveyard
        bf_creatures = [
            obj for obj in game.get_battlefield(p2).get_all()
            if getattr(obj, "name", None) == "Small Creature"
        ]
        assert len(bf_creatures) == 0

    # --- Life gain ---

    def test_x2_controller_gains_two_life(self) -> None:
        game, p1, p2, card = self._setup(2)
        card.chosen_targets = [p2, p2]
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before + 2

    def test_x5_controller_gains_five_life(self) -> None:
        game, p1, p2, card = self._setup(5)
        card.chosen_targets = [p2, p2]
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before + 5

    # --- All three effects together ---

    def test_x3_all_effects_simultaneously(self) -> None:
        game, p1, p2, card = self._setup(3)
        lib_cards = [TogetherAsOne(owner=p2) for _ in range(5)]
        for c in lib_cards:
            p2.zones[Zone.LIBRARY].add(c)

        p2_hand_before = len(game.get_hand(p2).get_all())
        p1_life_before = p1.life
        p2_life_before = p2.life

        # p2 draws, p2 takes damage, p1 gains life
        card.chosen_targets = [p2, p2]
        card.on_resolve(game)

        assert len(game.get_hand(p2).get_all()) == p2_hand_before + 3
        assert p2.life == p2_life_before - 3
        assert p1.life == p1_life_before + 3

    # --- colors_spent as list (pipeline path) ---

    def test_colors_spent_as_list_of_colors(self) -> None:
        from engine.types import Color

        game, p1, p2, card = self._setup(0)
        card.colors_spent = [Color.WHITE, Color.BLUE]  # 2 colors

        card.chosen_targets = [p2, p2]
        life_before = p1.life
        p2_life_before = p2.life
        card.on_resolve(game)

        assert p1.life == life_before + 2
        assert p2.life == p2_life_before - 2

    def test_x1_all_effects(self) -> None:
        game, p1, p2, card = self._setup(1)
        lib_cards = [TogetherAsOne(owner=p2) for _ in range(3)]
        for c in lib_cards:
            p2.zones[Zone.LIBRARY].add(c)

        p2_hand_before = len(game.get_hand(p2).get_all())
        p1_life_before = p1.life
        p2_life_before = p2.life

        card.chosen_targets = [p2, p2]
        card.on_resolve(game)

        assert len(game.get_hand(p2).get_all()) == p2_hand_before + 1
        assert p2.life == p2_life_before - 1
        assert p1.life == p1_life_before + 1
