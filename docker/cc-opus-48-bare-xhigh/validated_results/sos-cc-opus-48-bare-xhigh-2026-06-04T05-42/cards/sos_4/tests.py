"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestProperties:
    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")


class TestTargeting:
    def test_two_target_requirements(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)
        assert len(reqs) == 2
        assert all(isinstance(r, TargetRequirement) for r in reqs)

    def test_first_target_is_player_only(self) -> None:
        game = create_game()
        p1 = game.players[0]
        req = TogetherAsOne(owner=None).get_targets(game)[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        assert req.filter_fn(p1) is True
        assert req.filter_fn(bear) is False

    def test_second_target_accepts_creature_or_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        req = TogetherAsOne(owner=None).get_targets(game)[1]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        assert req.filter_fn(p1) is True
        assert req.filter_fn(bear) is True


class TestConvergeX:
    def test_int_colors_spent(self) -> None:
        c = TogetherAsOne(owner=None)
        c.colors_spent = 3
        assert c._converge_x() == 3

    def test_list_colors_spent(self) -> None:
        c = TogetherAsOne(owner=None)
        c.colors_spent = ["W", "U", "B"]
        assert c._converge_x() == 3

    def test_zero_default(self) -> None:
        assert TogetherAsOne(owner=None)._converge_x() == 0


class TestResolution:
    def test_draw_damage_and_lifegain(self) -> None:
        game = create_game()
        p1, p2 = game.players
        library = [Creature(name=f"C{i}", base_power=1, base_toughness=1) for i in range(5)]
        set_board_state(game, 0, life=20)
        for c in library:
            c.owner = p1
            c.controller = p1
            p1.zones[Zone.LIBRARY].add(c)
        set_board_state(game, 1, life=20)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 3
        spell.chosen_targets = [p1, p2]
        before_hand = len(p1.zones[Zone.HAND])
        spell.on_resolve(game)

        assert len(p1.zones[Zone.HAND]) == before_hand + 3
        assert p2.life == 17
        assert p1.life == 23

    def test_zero_x_is_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 0
        spell.chosen_targets = [p1, p2]
        spell.on_resolve(game)
        assert p1.life == 20
        assert p2.life == 20

    def test_damage_to_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=4)
        set_board_state(game, 1, battlefield=[bear])
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = ["W", "U"]
        spell.chosen_targets = [p1, bear]
        spell.on_resolve(game)
        assert bear.damage_marked == 2
        assert p1.life == 22
