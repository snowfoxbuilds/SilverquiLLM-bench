"""Audited tests for Bear Cub (FDN collector number 552) — vanilla creature."""

from __future__ import annotations

import pytest

from card_impl import BearCub

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestBearCubProperties:
    def test_is_creature(self) -> None:
        card = BearCub(name="Bear Cub", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = BearCub(name="Bear Cub", owner=None)
        assert card.name == "Bear Cub"

    def test_power(self) -> None:
        card = BearCub(name="Bear Cub", owner=None)
        assert card.power == 2

    def test_toughness(self) -> None:
        card = BearCub(name="Bear Cub", owner=None)
        assert card.toughness == 2

    def test_has_bear_subtype(self) -> None:
        card = BearCub(name="Bear Cub", owner=None)
        assert "Bear" in card.subtypes

    def test_no_keywords(self) -> None:
        card = BearCub(name="Bear Cub", owner=None)
        assert card.keywords == Keyword(0)

    def test_mana_cost_cmc(self) -> None:
        """Bear Cub costs {1}{G} — converted mana cost 2."""
        card = BearCub(name="Bear Cub", owner=None)
        assert card.mana_cost.cmc == 2


@pytest.mark.behavior
class TestBearCubBehavior:
    """Casting and combat behavior tests for Bear Cub."""

    def test_can_be_cast_from_hand(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType

        game = create_game()
        card = BearCub(name="Bear Cub", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.GREEN: 2})
        cast_spell(game, 0, "Bear Cub")
        bf = game.get_battlefield(game.players[0])
        assert card in bf.get_all()

    def test_has_summoning_sickness_when_cast(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType

        game = create_game()
        card = BearCub(name="Bear Cub", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.GREEN: 2})
        cast_spell(game, 0, "Bear Cub")
        assert card.summoning_sick

    def test_deals_combat_damage_equal_to_power(self) -> None:
        """Bear Cub deals 2 damage when attacking unblocked."""
        from tests.test_utils import create_game, set_board_state, declare_attackers
        from engine.combat import combat_damage_step

        game = create_game()
        card = BearCub(name="Bear Cub", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        declare_attackers(game, ["Bear Cub"])
        combat_damage_step(game)
        assert game.players[1].life == 20 - 2
