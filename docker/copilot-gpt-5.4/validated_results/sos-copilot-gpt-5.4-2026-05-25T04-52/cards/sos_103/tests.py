"""Tests for SOS 103 — Ulna Alley Shopkeep."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_103.card_impl import UlnaAlleyShopkeep
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestUlnaAlleyShopkeepProperties:
    """Static card data should match the SOS 103 spec."""

    def test_is_goblin_warlock_creature_with_menace(self) -> None:
        card = UlnaAlleyShopkeep(owner=None)

        assert isinstance(card, Creature)
        assert "Goblin" in card.subtypes
        assert "Warlock" in card.subtypes
        assert Keyword.MENACE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = UlnaAlleyShopkeep(owner=None)

        assert card.name == "Ulna Alley Shopkeep"
        assert card.mana_cost == ManaCost.parse("{2}{B}")
        assert card.base_power == 2
        assert card.base_toughness == 3


class TestUlnaAlleyShopkeepInfusion:
    """Ulna Alley Shopkeep should get +2/+0 only while you gained life this turn."""

    def test_without_life_gain_apply_continuous_effect_leaves_it_at_base_stats(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = UlnaAlleyShopkeep(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.apply_continuous_effect(game)
        game.effect_manager.apply_all(game)

        assert card.power == 2
        assert card.toughness == 3

    def test_if_you_gained_life_this_turn_apply_continuous_effect_gives_plus_two_plus_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = UlnaAlleyShopkeep(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        p1.life_gained_this_turn = 1

        card.apply_continuous_effect(game)
        game.effect_manager.apply_all(game)

        assert card.power == 4
        assert card.toughness == 3
