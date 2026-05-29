"""Tests for sos_4 — Together as One (Converge Sorcery)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestTogetherAsOneProperties:
    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")

    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_has_sorcery_card_type(self) -> None:
        assert CardType.SORCERY in TogetherAsOne(owner=None).card_types


class TestTogetherAsOneConverge:
    """X = number of colors of mana spent."""

    def _resolve(self, game, spell, target_player, damage_target, colors_spent):
        """Set up colors_spent and resolve."""
        spell.colors_spent = colors_spent
        spell.chosen_targets = [target_player, damage_target]
        spell.on_resolve(game)

    def test_zero_colors_draws_zero(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        initial_hand = len(p2.zones[Zone.HAND].get_all())
        self._resolve(game, spell, p2, p2, 0)
        assert len(p2.zones[Zone.HAND].get_all()) == initial_hand

    def test_two_colors_draws_two_cards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        # Put 5 cards in p2's library so they can draw
        for i in range(5):
            c = Creature(name=f"Card{i}", owner=p2, controller=p2)
            p2.zones[Zone.LIBRARY].add(c)
        spell = TogetherAsOne(owner=p1, controller=p1)
        initial_hand = len(p2.zones[Zone.HAND].get_all())
        self._resolve(game, spell, p2, p2, 2)
        assert len(p2.zones[Zone.HAND].get_all()) == initial_hand + 2

    def test_three_colors_deals_three_damage_to_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(bear)
        spell = TogetherAsOne(owner=p1, controller=p1)
        self._resolve(game, spell, p2, bear, 3)
        assert bear.damage_marked == 3

    def test_two_colors_deals_two_damage_to_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        initial_life = p2.life
        self._resolve(game, spell, p2, p2, 2)
        assert p2.life == initial_life - 2

    def test_three_colors_gains_three_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        initial_life = p1.life
        self._resolve(game, spell, p2, p2, 3)
        assert p1.life == initial_life + 3

    def test_five_colors_maximum(self) -> None:
        game = create_game()
        p1, p2 = game.players
        for i in range(6):
            c = Creature(name=f"Lib{i}", owner=p2)
            p2.zones[Zone.LIBRARY].add(c)
        spell = TogetherAsOne(owner=p1, controller=p1)
        initial_hand = len(p2.zones[Zone.HAND].get_all())
        initial_p1_life = p1.life
        self._resolve(game, spell, p2, p2, 5)
        assert len(p2.zones[Zone.HAND].get_all()) == initial_hand + 5
        assert p2.life == 20 - 5
        assert p1.life == initial_p1_life + 5

    def test_colors_spent_defaults_to_empty_list(self) -> None:
        card = TogetherAsOne(owner=None)
        # colors_spent should default to 0 or empty
        val = getattr(card, "colors_spent", 0)
        x = len(val) if isinstance(val, list) else val
        assert x == 0
