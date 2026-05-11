"""Audited tests for Charming Prince (FDN collector number 568)."""
from __future__ import annotations
import pytest
from card_impl import CharmingPrince
from engine.card import Creature
from engine.types import ManaCost


@pytest.mark.basic
class TestCharmingPrinceBasic:
    def test_is_creature(self) -> None:
        card = CharmingPrince()
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = CharmingPrince()
        assert card.name == "Charming Prince"

    def test_mana_cost(self) -> None:
        card = CharmingPrince()
        assert card.mana_cost == ManaCost.parse("{1}{W}")

    def test_power_toughness(self) -> None:
        card = CharmingPrince()
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = CharmingPrince()
        assert "Human" in card.subtypes
        assert "Noble" in card.subtypes


@pytest.mark.ability
class TestCharmingPrinceModes:
    def test_has_three_modes(self) -> None:
        card = CharmingPrince()
        modes = card.get_modes()
        assert len(modes) == 3

    def test_mode_names(self) -> None:
        card = CharmingPrince()
        modes = card.get_modes()
        names = [m.name for m in modes]
        assert "Scry" in names
        assert "Life" in names
        assert "Flicker" in names

    def test_register_triggers_succeeds(self) -> None:
        from tests.test_utils import create_game, set_board_state
        game = create_game()
        p = game.players[0]
        card = CharmingPrince(owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

    def test_etb_life_mode_gains_three_life(self) -> None:
        """ETB mode 1 should gain 3 life."""
        from tests.test_utils import create_game, set_board_state
        from engine.triggers import EventType
        game = create_game()
        p = game.players[0]
        card = CharmingPrince(owner=p)
        card.controller = p
        card.chosen_mode = 1
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        life_before = p.life
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD,
                                        {"permanent": card, "controller": p})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        assert p.life == life_before + 3
