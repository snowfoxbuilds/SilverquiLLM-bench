"""Audited tests for FDN 119 — Elenda, Saint of Dusk."""

from __future__ import annotations

from card_impl import ElendaSaintOfDusk
from engine.card import Creature
from engine.types import Keyword, ManaCost
from tests.test_utils import create_game


class TestElendaBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = ElendaSaintOfDusk(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ElendaSaintOfDusk(owner=None)
        assert card.name == "Elenda, Saint of Dusk"

    def test_mana_cost(self) -> None:
        card = ElendaSaintOfDusk(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_power_toughness(self) -> None:
        card = ElendaSaintOfDusk(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_is_legendary(self) -> None:
        card = ElendaSaintOfDusk(owner=None)
        assert "Legendary" in getattr(card, "supertypes", set())

    def test_has_lifelink(self) -> None:
        card = ElendaSaintOfDusk(owner=None)
        assert Keyword.LIFELINK in card.keywords

    def test_subtypes(self) -> None:
        card = ElendaSaintOfDusk(owner=None)
        assert "Vampire" in card.subtypes
        assert "Knight" in card.subtypes

    def test_hexproof_from_instants_flag(self) -> None:
        card = ElendaSaintOfDusk(owner=None)
        assert getattr(card, "_hexproof_from_instants", False) is True


class TestElendaLifeBonus:
    """Continuous effect: P/T boost based on life total."""

    def test_no_bonus_at_starting_life(self) -> None:
        game = create_game(player1_life=20)
        p1 = game.players[0]
        p1.starting_life = 20
        elenda = ElendaSaintOfDusk(owner=p1, controller=p1)
        game.get_battlefield(p1).add(elenda)
        elenda.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert elenda.base_power == 4
        assert elenda.base_toughness == 4

    def test_plus_one_when_life_above_starting(self) -> None:
        game = create_game(player1_life=21)
        p1 = game.players[0]
        p1.starting_life = 20
        elenda = ElendaSaintOfDusk(owner=p1, controller=p1)
        game.get_battlefield(p1).add(elenda)
        elenda.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert elenda.modified_power >= 5
        assert elenda.modified_toughness >= 5

    def test_gains_menace_when_life_above_starting(self) -> None:
        game = create_game(player1_life=22)
        p1 = game.players[0]
        p1.starting_life = 20
        elenda = ElendaSaintOfDusk(owner=p1, controller=p1)
        game.get_battlefield(p1).add(elenda)
        elenda.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert Keyword.MENACE in elenda.keywords

    def test_additional_plus_five_at_ten_above(self) -> None:
        game = create_game(player1_life=30)
        p1 = game.players[0]
        p1.starting_life = 20
        elenda = ElendaSaintOfDusk(owner=p1, controller=p1)
        game.get_battlefield(p1).add(elenda)
        elenda.register_triggers(game)
        game.effect_manager.apply_all(game)
        # +1 from > starting + +5 from >= starting+10 = +6 total
        assert elenda.modified_power >= 10
        assert elenda.modified_toughness >= 10
