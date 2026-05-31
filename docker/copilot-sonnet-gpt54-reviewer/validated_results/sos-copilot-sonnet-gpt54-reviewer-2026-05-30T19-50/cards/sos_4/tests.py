"""Tests for Together as One (SOS #4)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestTogetherAsOneProperties:
    """Static card data tests."""

    def test_name(self) -> None:
        card = TogetherAsOne()
        assert card.name == "Together as One"

    def test_mana_cost(self) -> None:
        card = TogetherAsOne()
        assert card.mana_cost == ManaCost.parse("{6}")

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne()
        assert CardType.SORCERY in card.card_types

    def test_colors_spent_default_zero(self) -> None:
        card = TogetherAsOne()
        assert card._get_x() == 0


class TestTogetherAsOneXZero:
    """X=0 case: no colored mana spent."""

    def test_x_zero_no_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0

        # Give p2 a library card so draw would be visible
        from engine.card import CardImpl
        lib_card = CardImpl(name="Dummy")
        lib_card.owner = p2
        p2.zones[Zone.LIBRARY].add(lib_card)

        hand_before = len(p2.zones[Zone.HAND].get_all())
        card.chosen_targets = [p2, p1]
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == hand_before

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


class TestTogetherAsOneXOne:
    """X=1 case: one color of mana spent."""

    def _make_library(self, game, player, n: int) -> None:
        from engine.card import CardImpl
        for i in range(n):
            c = CardImpl(name=f"Lib{i}")
            c.owner = player
            player.zones[Zone.LIBRARY].add(c)

    def test_x_one_draws_one_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        self._make_library(game, p2, 5)
        hand_before = len(p2.zones[Zone.HAND].get_all())
        card.chosen_targets = [p2, p1]
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == hand_before + 1

    def test_x_one_deals_one_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        card.chosen_targets = [p2, p2]
        life_before = p2.life
        card.on_resolve(game)
        assert p2.life == life_before - 1

    def test_x_one_gains_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        card.chosen_targets = [p2, p2]
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before + 1


class TestTogetherAsOneXTwo:
    """X=2 case: two colors of mana spent."""

    def _make_library(self, game, player, n: int) -> None:
        from engine.card import CardImpl
        for i in range(n):
            c = CardImpl(name=f"Lib{i}")
            c.owner = player
            player.zones[Zone.LIBRARY].add(c)

    def test_x_two_draws_two_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        self._make_library(game, p2, 5)
        hand_before = len(p2.zones[Zone.HAND].get_all())
        card.chosen_targets = [p2, p1]
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == hand_before + 2

    def test_x_two_deals_two_damage_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        creature = Creature(name="Bear", base_power=2, base_toughness=2,
                            owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p1, creature]
        card.on_resolve(game)
        assert creature.damage_marked == 2

    def test_x_two_gains_two_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p2, p2]
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before + 2


class TestTogetherAsOneXThree:
    """X=3 or more colors."""

    def _make_library(self, game, player, n: int) -> None:
        from engine.card import CardImpl
        for i in range(n):
            c = CardImpl(name=f"Lib{i}")
            c.owner = player
            player.zones[Zone.LIBRARY].add(c)

    def test_x_three_all_effects(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        self._make_library(game, p2, 10)
        hand_before = len(p2.zones[Zone.HAND].get_all())
        p2_life_before = p2.life
        p1_life_before = p1.life
        card.chosen_targets = [p2, p2]
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == hand_before + 3
        assert p2.life == p2_life_before - 3
        assert p1.life == p1_life_before + 3

    def test_x_five_all_effects(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        self._make_library(game, p2, 10)
        hand_before = len(p2.zones[Zone.HAND].get_all())
        p1_life_before = p1.life
        p2_life_before = p2.life
        card.chosen_targets = [p2, p2]
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == hand_before + 5
        assert p2.life == p2_life_before - 5
        assert p1.life == p1_life_before + 5


class TestTogetherAsOneColorsList:
    """Test that colors_spent as a list (from cast pipeline) also works."""

    def _make_library(self, game, player, n: int) -> None:
        from engine.card import CardImpl
        for i in range(n):
            c = CardImpl(name=f"Lib{i}")
            c.owner = player
            player.zones[Zone.LIBRARY].add(c)

    def test_colors_spent_as_list(self) -> None:
        from engine.types import Color
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        # Simulate what the cast pipeline stores
        card.colors_spent = [Color.WHITE, Color.BLUE, Color.RED]
        self._make_library(game, p2, 10)
        hand_before = len(p2.zones[Zone.HAND].get_all())
        p1_life_before = p1.life
        card.chosen_targets = [p2, p2]
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == hand_before + 3
        assert p1.life == p1_life_before + 3
