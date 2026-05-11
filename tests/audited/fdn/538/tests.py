"""Audited tests for Fire Elemental (FDN collector number 538) — vanilla creature."""

from __future__ import annotations

import pytest

from card_impl import FireElemental

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestFireElementalProperties:
    def test_is_creature(self) -> None:
        card = FireElemental(name="Fire Elemental", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = FireElemental(name="Fire Elemental", owner=None)
        assert card.name == "Fire Elemental"

    def test_power(self) -> None:
        card = FireElemental(name="Fire Elemental", owner=None)
        assert card.power == 5

    def test_toughness(self) -> None:
        card = FireElemental(name="Fire Elemental", owner=None)
        assert card.toughness == 4

    def test_has_elemental_subtype(self) -> None:
        card = FireElemental(name="Fire Elemental", owner=None)
        assert "Elemental" in card.subtypes

    def test_no_keywords(self) -> None:
        card = FireElemental(name="Fire Elemental", owner=None)
        assert card.keywords == Keyword(0)

    def test_mana_cost_cmc(self) -> None:
        """Fire Elemental costs {3}{R}{R} — converted mana cost 5."""
        card = FireElemental(name="Fire Elemental", owner=None)
        assert card.mana_cost.cmc == 5


@pytest.mark.behavior
class TestFireElementalBehavior:
    """Casting and combat behavior tests for Fire Elemental."""

    def test_can_be_cast_from_hand(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType

        game = create_game()
        card = FireElemental(name="Fire Elemental", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.RED: 5})
        cast_spell(game, 0, "Fire Elemental")
        bf = game.get_battlefield(game.players[0])
        assert card in bf.get_all()

    def test_has_summoning_sickness_when_cast(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType

        game = create_game()
        card = FireElemental(name="Fire Elemental", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.RED: 5})
        cast_spell(game, 0, "Fire Elemental")
        assert card.summoning_sick

    def test_deals_combat_damage_equal_to_power(self) -> None:
        """Fire Elemental deals 5 damage when attacking unblocked."""
        from tests.test_utils import create_game, set_board_state, declare_attackers
        from engine.combat import combat_damage_step

        game = create_game()
        card = FireElemental(name="Fire Elemental", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        declare_attackers(game, ["Fire Elemental"])
        combat_damage_step(game)
        assert game.players[1].life == 20 - 5
