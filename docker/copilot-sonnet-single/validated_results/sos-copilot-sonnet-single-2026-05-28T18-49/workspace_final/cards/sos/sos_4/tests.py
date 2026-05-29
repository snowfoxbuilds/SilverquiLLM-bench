"""Tests for Together as One (sos_4) — Converge sorcery."""

from __future__ import annotations

import pytest
from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestTogetherAsOneProperties:
    """Static card properties."""

    def test_name(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"

    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)
        assert CardType.SORCERY in TogetherAsOne(owner=None).card_types

    def test_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}")

    def test_colors_spent_defaults_to_empty(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.colors_spent == []


class TestTogetherAsOneTargeting:
    """get_targets() returns two requirements."""

    def test_returns_two_target_requirements(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        reqs = card.get_targets(game)
        assert len(reqs) == 2

    def test_first_target_is_player(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        req = card.get_targets(game)[0]
        assert req.filter_fn(game.players[0]) is True
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        assert req.filter_fn(bear) is False

    def test_second_target_accepts_player(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        req = card.get_targets(game)[1]
        assert req.filter_fn(game.players[0]) is True

    def test_second_target_accepts_creature(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        req = card.get_targets(game)[1]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        assert req.filter_fn(bear) is True


class TestTogetherAsOneConverge:
    """Converge: X = distinct colors of mana spent."""

    def test_zero_colors_no_effect(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = []
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[bear])
        card.chosen_targets = [p2, bear]
        p2_life_before = p2.life
        card.on_resolve(game)
        # No effect when X = 0
        assert p2.life == p2_life_before
        assert len(p1.zones[Zone.HAND].get_all()) == 0

    def test_two_colors_draws_two_cards_for_target_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = ["R", "W"]  # 2 colors

        # Target player is p2; damage target is p2 as well
        from engine.card import Instant
        # Put cards in p2 library for drawing
        for i in range(5):
            lib_card = Instant(name=f"Card{i}", owner=p2, controller=p2)
            p2.zones[Zone.LIBRARY].add(lib_card)

        card.chosen_targets = [p2, p2]
        p2_life_before = p2.life
        card.on_resolve(game)
        # p2 drew 2 cards
        assert len(p2.zones[Zone.HAND].get_all()) == 2
        # p2 took 2 damage
        assert p2.life == p2_life_before - 2
        # p1 gained 2 life
        assert p1.life == 22

    def test_five_colors_effects_scale(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne(owner=p1, controller=p1)
        from engine.types import Color
        card.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN]

        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[bear])
        for i in range(10):
            from engine.card import Instant
            lib_card = Instant(name=f"Card{i}", owner=p1, controller=p1)
            p1.zones[Zone.LIBRARY].add(lib_card)

        card.chosen_targets = [p1, bear]
        p1_life_before = p1.life
        card.on_resolve(game)
        # p1 drew 5 cards
        assert len(p1.zones[Zone.HAND].get_all()) == 5
        # bear took 5 damage
        assert bear.damage_marked == 5
        # p1 gained 5 life
        assert p1.life == p1_life_before + 5
