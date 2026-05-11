"""Audited tests for Paradise Druid (SPG collector number 80)."""
from __future__ import annotations
import pytest
from card_impl import ParadiseDruid
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestParadiseDruidBasic:
    def test_is_creature(self) -> None:
        card = ParadiseDruid()
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ParadiseDruid()
        assert card.name == "Paradise Druid"

    def test_mana_cost(self) -> None:
        card = ParadiseDruid()
        assert card.mana_cost == ManaCost.parse("{1}{G}")

    def test_power_toughness(self) -> None:
        card = ParadiseDruid()
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_subtypes(self) -> None:
        card = ParadiseDruid()
        assert "Elf" in card.subtypes
        assert "Druid" in card.subtypes


@pytest.mark.ability
class TestParadiseDruidMana:
    def test_has_five_mana_abilities(self) -> None:
        """One for each color of mana."""
        card = ParadiseDruid()
        abilities = card.get_mana_abilities()
        assert len(abilities) == 5

    def test_taps_for_green(self) -> None:
        game = create_game()
        p = game.players[0]
        card = ParadiseDruid(owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[card])
        # Find the green mana ability
        abilities = card.get_mana_abilities()
        green_ability = [a for a in abilities if "{G}" in a.description]
        assert len(green_ability) == 1
        green_ability[0].cost(game, card)
        green_ability[0].mana_produced(game)
        assert p.mana_pool.get(ManaType.GREEN) >= 1


@pytest.mark.ability
class TestParadiseDruidHexproof:
    def test_hexproof_while_untapped(self) -> None:
        """Paradise Druid should have hexproof when untapped after effects applied."""
        game = create_game()
        p = game.players[0]
        card = ParadiseDruid(owner=p)
        card.controller = p
        card.is_tapped = False
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert Keyword.HEXPROOF & card.keywords

    def test_no_hexproof_when_tapped(self) -> None:
        """Paradise Druid should lose hexproof when tapped after effects applied."""
        game = create_game()
        p = game.players[0]
        card = ParadiseDruid(owner=p)
        card.controller = p
        card.is_tapped = False
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert Keyword.HEXPROOF & card.keywords
        # Now tap and reapply
        card.is_tapped = True
        game.effect_manager.apply_all(game)
        assert not (Keyword.HEXPROOF & card.keywords)
