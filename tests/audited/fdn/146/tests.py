"""Audited tests for Savannah Lions (FDN collector number 146) — vanilla creature."""

from __future__ import annotations

import pytest

from card_impl import SavannahLions

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestSavannahLionsProperties:
    def test_is_creature(self) -> None:
        card = SavannahLions(name="Savannah Lions", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SavannahLions(name="Savannah Lions", owner=None)
        assert card.name == "Savannah Lions"

    def test_power(self) -> None:
        card = SavannahLions(name="Savannah Lions", owner=None)
        assert card.power == 2

    def test_toughness(self) -> None:
        card = SavannahLions(name="Savannah Lions", owner=None)
        assert card.toughness == 1

    def test_has_cat_subtype(self) -> None:
        card = SavannahLions(name="Savannah Lions", owner=None)
        assert "Cat" in card.subtypes

    def test_no_keywords(self) -> None:
        card = SavannahLions(name="Savannah Lions", owner=None)
        assert card.keywords == Keyword(0)

    def test_mana_cost_cmc(self) -> None:
        """Savannah Lions costs {W} — converted mana cost 1."""
        card = SavannahLions(name="Savannah Lions", owner=None)
        assert card.mana_cost.cmc == 1


@pytest.mark.behavior
class TestSavannahLionsBehavior:
    """Casting and combat behavior tests for Savannah Lions."""

    def test_can_be_placed_on_battlefield(self) -> None:
        """Savannah Lions can be placed on the battlefield via set_board_state."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone

        game = create_game()
        card = SavannahLions(name="Savannah Lions", owner=game.players[0])
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(game.players[0])
        assert card in bf.get_all()

    def test_can_be_cast_from_hand(self) -> None:
        """Savannah Lions can be cast from hand with sufficient mana."""
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType, Zone

        game = create_game()
        card = SavannahLions(name="Savannah Lions", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.WHITE: 1})
        cast_spell(game, 0, "Savannah Lions")
        bf = game.get_battlefield(game.players[0])
        assert card in bf.get_all()

    def test_has_summoning_sickness(self) -> None:
        """A freshly cast creature has summoning sickness."""
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType

        game = create_game()
        card = SavannahLions(name="Savannah Lions", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.WHITE: 1})
        cast_spell(game, 0, "Savannah Lions")
        assert card.summoning_sick

    def test_deals_combat_damage_equal_to_power(self) -> None:
        """Savannah Lions deals damage equal to its power (2) when attacking unblocked."""
        from tests.test_utils import create_game, set_board_state, declare_attackers
        from engine.combat import combat_damage_step

        game = create_game()
        card = SavannahLions(name="Savannah Lions", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        declare_attackers(game, ["Savannah Lions"])
        combat_damage_step(game)
        assert game.players[1].life == 20 - card.power
