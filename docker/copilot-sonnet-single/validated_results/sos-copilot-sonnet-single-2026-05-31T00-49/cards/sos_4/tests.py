"""Tests for sos_4 — Together as One."""

from __future__ import annotations

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Color, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestTogetherAsOneProperties:
    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.SORCERY in card.card_types


class TestTogetherAsOneTargeting:
    def test_returns_two_target_requirements(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        targets = card.get_targets(game)
        assert len(targets) == 2

    def test_first_target_is_player(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        req = card.get_targets(game)[0]
        p1 = game.players[0]
        assert req.filter_fn(p1) is True

    def test_second_target_accepts_creature(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        req = card.get_targets(game)[1]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        assert req.filter_fn(creature) is True

    def test_second_target_accepts_player(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        req = card.get_targets(game)[1]
        p2 = game.players[1]
        assert req.filter_fn(p2) is True


class TestTogetherAsOneConverge:
    """Converge resolution: X = distinct colors spent."""

    def _resolve(self, game, spell, colors_spent, target_player, damage_target):
        from engine.types import Color as C
        spell.controller = game.players[0]
        spell.colors_spent = colors_spent
        spell.chosen_targets = [target_player, damage_target]
        spell.on_resolve(game)

    def test_x_zero_no_effects(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        self._resolve(game, spell, [], p1, p2)
        # No draws, no damage, no life gain when X=0.
        assert p1.life == 20
        assert p2.life == 20

    def test_x_one_draws_one_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        from engine.card import Instant as I
        for _ in range(5):
            p1.zones[Zone.LIBRARY].add(I(name=f"Card{_}"))
        hand_before = len(p1.zones[Zone.HAND].get_all())
        spell = TogetherAsOne(owner=p1, controller=p1)
        self._resolve(game, spell, [Color.WHITE], p1, p2)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 1

    def test_x_one_deals_one_damage(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        self._resolve(game, spell, [Color.WHITE], p1, p2)
        assert p2.life == 19

    def test_x_one_gains_one_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        self._resolve(game, spell, [Color.WHITE], p1, p2)
        assert p1.life == 21

    def test_x_three_gains_three_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        self._resolve(game, spell, [Color.WHITE, Color.BLUE, Color.BLACK], p1, p2)
        assert p1.life == 23

    def test_x_three_deals_three_damage(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        self._resolve(game, spell, [Color.WHITE, Color.BLUE, Color.BLACK], p1, p2)
        assert p2.life == 17

    def test_duplicate_colors_count_once(self) -> None:
        """Two White pips still count as 1 color."""
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        self._resolve(game, spell, [Color.WHITE, Color.WHITE], p1, p2)
        assert p1.life == 21  # X=1

    def test_max_five_colors(self) -> None:
        game = create_game()
        p1, p2 = game.players
        all_colors = [Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN]
        spell = TogetherAsOne(owner=p1, controller=p1)
        self._resolve(game, spell, all_colors, p1, p2)
        assert p1.life == 25
        assert p2.life == 15
