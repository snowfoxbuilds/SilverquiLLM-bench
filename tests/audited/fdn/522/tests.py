"""Audited tests for Highborn Vampire (FDN collector number 522) — vanilla creature."""

from __future__ import annotations

import pytest

from card_impl import HighbornVampire

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestHighbornVampireProperties:
    def test_is_creature(self) -> None:
        card = HighbornVampire(name="Highborn Vampire", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = HighbornVampire(name="Highborn Vampire", owner=None)
        assert card.name == "Highborn Vampire"

    def test_power(self) -> None:
        card = HighbornVampire(name="Highborn Vampire", owner=None)
        assert card.power == 4

    def test_toughness(self) -> None:
        card = HighbornVampire(name="Highborn Vampire", owner=None)
        assert card.toughness == 3

    def test_has_vampire_subtype(self) -> None:
        card = HighbornVampire(name="Highborn Vampire", owner=None)
        assert "Vampire" in card.subtypes

    def test_has_warrior_subtype(self) -> None:
        card = HighbornVampire(name="Highborn Vampire", owner=None)
        assert "Warrior" in card.subtypes

    def test_no_keywords(self) -> None:
        card = HighbornVampire(name="Highborn Vampire", owner=None)
        assert card.keywords == Keyword(0)

    def test_mana_cost_cmc(self) -> None:
        """Highborn Vampire costs {3}{B} — converted mana cost 4."""
        card = HighbornVampire(name="Highborn Vampire", owner=None)
        assert card.mana_cost.cmc == 4


@pytest.mark.behavior
class TestHighbornVampireBehavior:
    """Casting and combat behavior tests for Highborn Vampire."""

    def test_can_be_cast_from_hand(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType

        game = create_game()
        card = HighbornVampire(name="Highborn Vampire", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.BLACK: 4})
        cast_spell(game, 0, "Highborn Vampire")
        bf = game.get_battlefield(game.players[0])
        assert card in bf.get_all()

    def test_has_summoning_sickness_when_cast(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType

        game = create_game()
        card = HighbornVampire(name="Highborn Vampire", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.BLACK: 4})
        cast_spell(game, 0, "Highborn Vampire")
        assert card.summoning_sick

    def test_deals_combat_damage_equal_to_power(self) -> None:
        """Highborn Vampire deals 4 damage when attacking unblocked."""
        from tests.test_utils import create_game, set_board_state, declare_attackers
        from engine.combat import combat_damage_step

        game = create_game()
        card = HighbornVampire(name="Highborn Vampire", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        declare_attackers(game, ["Highborn Vampire"])
        combat_damage_step(game)
        assert game.players[1].life == 20 - 4
