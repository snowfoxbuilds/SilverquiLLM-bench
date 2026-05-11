"""Audited tests for Bloom Tender (SPG collector number 79)."""
from __future__ import annotations
import pytest
from card_impl import BloomTender
from engine.card import Creature
from engine.types import ManaCost, ManaType
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestBloomTenderBasic:
    def test_is_creature(self) -> None:
        card = BloomTender()
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = BloomTender()
        assert card.name == "Bloom Tender"

    def test_mana_cost(self) -> None:
        card = BloomTender()
        assert card.mana_cost == ManaCost.parse("{1}{G}")

    def test_power_toughness(self) -> None:
        card = BloomTender()
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_subtypes(self) -> None:
        card = BloomTender()
        assert "Elf" in card.subtypes
        assert "Druid" in card.subtypes


@pytest.mark.ability
class TestBloomTenderMana:
    def test_has_mana_ability(self) -> None:
        card = BloomTender()
        abilities = card.get_mana_abilities()
        assert len(abilities) == 1

    def test_mana_ability_description(self) -> None:
        card = BloomTender()
        abilities = card.get_mana_abilities()
        assert "color" in abilities[0].description.lower()

    def test_taps_when_activated(self) -> None:
        game = create_game()
        p = game.players[0]
        card = BloomTender(owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        result = abilities[0].cost(game, card)
        assert result is True
        assert card.is_tapped

    def test_cannot_tap_when_tapped(self) -> None:
        game = create_game()
        p = game.players[0]
        card = BloomTender(owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        assert abilities[0].cost(game, card) is False

    def test_produces_green_with_green_permanent(self) -> None:
        """When you control a green permanent, Bloom Tender adds {G}."""
        game = create_game()
        p = game.players[0]
        card = BloomTender(owner=p)
        card.controller = p
        # Bloom Tender itself is green (costs {1}{G}), so should produce at least green
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        abilities[0].mana_produced(game)
        assert p.mana_pool.get(ManaType.GREEN) >= 1

    def test_produces_multiple_colors_with_multicolor_permanents(self) -> None:
        """If you control permanents of different colors, adds mana of each."""
        from engine.card import Creature
        game = create_game()
        p = game.players[0]
        card = BloomTender(owner=p)
        card.controller = p
        # Create a red creature
        red_creature = Creature(name="Red Guy", owner=p, base_power=1, base_toughness=1,
                                mana_cost=ManaCost.parse("{R}"))
        red_creature.controller = p
        set_board_state(game, 0, battlefield=[card, red_creature])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        abilities[0].mana_produced(game)
        # Should produce both green (from Bloom Tender) and red (from red creature)
        assert p.mana_pool.get(ManaType.GREEN) >= 1
        assert p.mana_pool.get(ManaType.RED) >= 1

    def test_produces_no_mana_with_only_colorless_permanents(self) -> None:
        """With only colorless permanents, no mana is added."""
        from engine.card import Artifact
        game = create_game()
        p = game.players[0]
        # Use an artifact with no color
        artifact = Artifact(name="Rock", owner=p, mana_cost=ManaCost.parse("{2}"))
        artifact.controller = p
        card = BloomTender(owner=p)
        card.controller = p
        # Override Bloom Tender's colors so it's not counted
        card.colors = set()
        set_board_state(game, 0, battlefield=[card, artifact])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        abilities[0].mana_produced(game)
        assert p.mana_pool.get(ManaType.WHITE) == 0
        assert p.mana_pool.get(ManaType.BLUE) == 0
        assert p.mana_pool.get(ManaType.BLACK) == 0
        assert p.mana_pool.get(ManaType.RED) == 0
        assert p.mana_pool.get(ManaType.GREEN) == 0
