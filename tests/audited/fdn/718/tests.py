"""Audited tests for Gigantosaurus (FDN collector number 718) — vanilla creature."""

from __future__ import annotations

import pytest

from card_impl import Gigantosaurus

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestGigantosaurusProperties:
    def test_is_creature(self) -> None:
        card = Gigantosaurus(name="Gigantosaurus", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = Gigantosaurus(name="Gigantosaurus", owner=None)
        assert card.name == "Gigantosaurus"

    def test_power(self) -> None:
        card = Gigantosaurus(name="Gigantosaurus", owner=None)
        assert card.power == 10

    def test_toughness(self) -> None:
        card = Gigantosaurus(name="Gigantosaurus", owner=None)
        assert card.toughness == 10

    def test_has_dinosaur_subtype(self) -> None:
        card = Gigantosaurus(name="Gigantosaurus", owner=None)
        assert "Dinosaur" in card.subtypes

    def test_no_keywords(self) -> None:
        card = Gigantosaurus(name="Gigantosaurus", owner=None)
        assert card.keywords == Keyword(0)

    def test_mana_cost_cmc(self) -> None:
        """Gigantosaurus costs {G}{G}{G}{G}{G} — converted mana cost 5."""
        card = Gigantosaurus(name="Gigantosaurus", owner=None)
        assert card.mana_cost.cmc == 5


@pytest.mark.behavior
class TestGigantosaurusBehavior:
    """Casting and combat behavior tests for Gigantosaurus."""

    def test_can_be_cast_from_hand(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType

        game = create_game()
        card = Gigantosaurus(name="Gigantosaurus", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.GREEN: 5})
        cast_spell(game, 0, "Gigantosaurus")
        bf = game.get_battlefield(game.players[0])
        assert card in bf.get_all()

    def test_has_summoning_sickness_when_cast(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType

        game = create_game()
        card = Gigantosaurus(name="Gigantosaurus", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.GREEN: 5})
        cast_spell(game, 0, "Gigantosaurus")
        assert card.summoning_sick

    def test_deals_combat_damage_equal_to_power(self) -> None:
        """Gigantosaurus deals 10 damage when attacking unblocked."""
        from tests.test_utils import create_game, set_board_state, declare_attackers
        from engine.combat import combat_damage_step

        game = create_game()
        card = Gigantosaurus(name="Gigantosaurus", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        declare_attackers(game, ["Gigantosaurus"])
        combat_damage_step(game)
        assert game.players[1].life == 20 - 10
