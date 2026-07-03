"""Tests for SOS 117 — Goblin Glasswright // Craft with Pride."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_117.card_impl import GoblinGlasswrightCraftWithPride
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestGoblinGlasswrightCraftWithPrideProperties:
    """Static front-face data should match the SOS 117 spec."""

    def test_is_goblin_sorcerer_creature(self) -> None:
        card = GoblinGlasswrightCraftWithPride(owner=None)

        assert isinstance(card, Creature)
        assert "Goblin" in card.subtypes
        assert "Sorcerer" in card.subtypes

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = GoblinGlasswrightCraftWithPride(owner=None)

        assert card.name == "Goblin Glasswright"
        assert card.mana_cost == ManaCost.parse("{1}{R}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestGoblinGlasswrightCraftWithPridePrepared:
    """Goblin Glasswright should use the prepared-state contract."""

    def test_enters_prepared_on_resolve(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GoblinGlasswrightCraftWithPride(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.on_resolve(game)

        assert card.is_prepared is True

    def test_prepared_spell_copy_is_craft_with_pride_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GoblinGlasswrightCraftWithPride(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Craft with Pride"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{R}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card
