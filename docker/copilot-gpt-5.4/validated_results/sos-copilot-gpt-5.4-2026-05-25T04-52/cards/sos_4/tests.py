"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_4.card_impl import TogetherAsOne
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import Color, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneResolution:
    """Converge should drive draw, damage, and life gain together."""

    def test_three_colors_applies_all_three_effects(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_creature = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 1, battlefield=[target_creature])

        for idx in range(3):
            game.get_library(p2).add(CardImpl(name=f"Draw {idx}", owner=p2, controller=p2))

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [Color.W, Color.U, Color.B]
        card.chosen_targets = [p2, target_creature]

        before_hand = len(game.get_hand(p2).get_all())
        before_life = p1.life

        card.on_resolve(game)

        assert len(game.get_hand(p2).get_all()) == before_hand + 3
        assert target_creature.damage_marked == 3
        assert p1.life == before_life + 3

    def test_zero_colors_is_a_noop_even_with_targets(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_creature = Creature(
            name="Still Safe",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 1, battlefield=[target_creature])
        game.get_library(p2).add(CardImpl(name="Only Card", owner=p2, controller=p2))

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = []
        card.chosen_targets = [p2, target_creature]

        before_hand = len(game.get_hand(p2).get_all())
        before_life = p1.life

        card.on_resolve(game)

        assert len(game.get_hand(p2).get_all()) == before_hand
        assert target_creature.damage_marked == 0
        assert p1.life == before_life
