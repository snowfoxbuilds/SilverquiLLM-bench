"""Tests for Together as One (SOS 4)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import CardType, ManaType, Zone
from test_utils import create_game, set_board_state


def _dummy_library(game, player, n):
    lib = player.zones[Zone.LIBRARY]
    for i in range(n):
        lib.add(Creature(name=f"Lib{i}", base_power=1, base_toughness=1,
                         owner=player, controller=player))


class TestProperties:
    def test_static_data(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"
        from engine.types import ManaCost
        assert card.mana_cost == ManaCost.parse("{6}")
        assert CardType.SORCERY in card.card_types


class TestResolve:
    def test_x_two_draws_damages_gains(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _dummy_library(game, p1, 5)
        target_creature = Creature(name="Goon", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target_creature], life=20)
        set_board_state(game, 0, life=20)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p1, target_creature]
        hand_before = len(game.get_hand(p1).get_all())
        card.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) - hand_before == 2
        assert target_creature.damage_marked == 2
        assert p1.life == 22

    def test_damage_to_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _dummy_library(game, p1, 5)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p1, p2]
        card.on_resolve(game)
        assert p2.life == 17
        assert p1.life == 23

    def test_x_zero_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _dummy_library(game, p1, 5)
        target_creature = Creature(name="Goon", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target_creature])
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p1, target_creature]
        hand_before = len(game.get_hand(p1).get_all())
        card.on_resolve(game)
        assert len(game.get_hand(p1).get_all()) == hand_before
        assert target_creature.damage_marked == 0
        assert p1.life == 20

    def test_real_cast_converge(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _dummy_library(game, p1, 5)
        card = TogetherAsOne(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card],
                        mana={ManaType.WHITE: 3, ManaType.BLUE: 3})
        from test_utils import cast_spell
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        # Paid {6} with W and U -> two colors -> X=2
        assert p2.life == 18
        assert p1.life == 22
