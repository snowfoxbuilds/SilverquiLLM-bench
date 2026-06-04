"""Tests for Together as One (SOS 4)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Supertype, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestTogetherAsOneProperties:
    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)
        assert CardType.SORCERY in TogetherAsOne(owner=None).card_types

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneTargets:
    def test_two_target_requirements(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)
        assert len(reqs) == 2
        assert all(isinstance(r, TargetRequirement) for r in reqs)

    def test_any_target_filter_accepts_player_and_creature(self) -> None:
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[1]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        assert req.filter_fn(creature) is True
        assert req.filter_fn(game.players[0]) is True


class TestTogetherAsOneResolution:
    def _make(self, x):
        game = create_game()
        p1, p2 = game.players
        # Stock p1's library so draws have something to take.
        for i in range(5):
            c = Creature(name=f"L{i}", base_power=1, base_toughness=1)
            c.owner = p1
            p1.zones[Zone.LIBRARY].add(c)
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = x
        return game, p1, p2, spell

    def test_x_zero_is_noop(self) -> None:
        game, p1, p2, spell = self._make(0)
        spell.chosen_targets = [p1, p2]
        spell.on_resolve(game)
        assert p1.life == 20 and p2.life == 20
        assert len(p1.zones[Zone.HAND]) == 0

    def test_three_colors(self) -> None:
        game, p1, p2, spell = self._make(3)
        spell.chosen_targets = [p1, p2]
        before_hand = len(p1.zones[Zone.HAND])
        spell.on_resolve(game)
        assert len(p1.zones[Zone.HAND]) == before_hand + 3  # drew 3
        assert p2.life == 17  # took 3 damage
        assert p1.life == 23  # gained 3

    def test_colors_spent_as_list(self) -> None:
        from engine.types import Color

        game, p1, p2, spell = self._make(0)
        spell.colors_spent = [Color.WHITE, Color.BLUE, Color.WHITE]  # 2 distinct
        spell.chosen_targets = [p1, p2]
        spell.on_resolve(game)
        assert p2.life == 18
        assert p1.life == 22

    def test_damage_to_creature(self) -> None:
        game, p1, p2, spell = self._make(2)
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[bear])
        spell.chosen_targets = [p1, bear]
        spell.on_resolve(game)
        assert bear.damage_marked == 2
