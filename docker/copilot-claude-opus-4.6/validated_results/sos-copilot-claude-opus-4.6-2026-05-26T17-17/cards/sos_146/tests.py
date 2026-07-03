"""Tests for SOS 146 — Emil, Vastlands Roamer."""

from __future__ import annotations

import pytest

from cards.sos.sos_146.card_impl import EmilVastlandsRoamer
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestEmilVastlandsRoamerProperties:
    """Static card data should match the SOS 146 spec."""

    def test_is_creature(self) -> None:
        card = EmilVastlandsRoamer(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert EmilVastlandsRoamer(owner=None).name == "Emil, Vastlands Roamer"

    def test_mana_cost(self) -> None:
        assert EmilVastlandsRoamer(owner=None).mana_cost == ManaCost.parse("{2}{G}")

    def test_power_toughness(self) -> None:
        card = EmilVastlandsRoamer(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_legendary(self) -> None:
        card = EmilVastlandsRoamer(owner=None)
        from engine.types import Supertype
        assert Supertype.LEGENDARY in card.supertypes


class TestEmilTrampleGranting:
    """Creatures with +1/+1 counters should have trample."""

    def test_creature_with_counter_has_trample(self) -> None:
        game = create_game()
        p1 = game.players[0]
        emil = EmilVastlandsRoamer(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        bear.plus_one_counters = 1
        game.get_battlefield(p1).add(emil)
        game.get_battlefield(p1).add(bear)
        assert Keyword.TRAMPLE in bear.keywords

    def test_creature_without_counter_no_trample(self) -> None:
        game = create_game()
        p1 = game.players[0]
        emil = EmilVastlandsRoamer(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        bear.plus_one_counters = 0
        game.get_battlefield(p1).add(emil)
        game.get_battlefield(p1).add(bear)
        assert Keyword.TRAMPLE not in bear.keywords

    def test_emil_with_counter_has_trample(self) -> None:
        """Emil itself should also gain trample if it has a +1/+1 counter."""
        game = create_game()
        p1 = game.players[0]
        emil = EmilVastlandsRoamer(owner=p1, controller=p1)
        emil.plus_one_counters = 1
        game.get_battlefield(p1).add(emil)
        assert Keyword.TRAMPLE in emil.keywords


class TestEmilActivatedAbility:
    """The {4}{G}, {T} ability creates a Fractal token with counters."""

    def test_ability_creates_fractal_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        emil = EmilVastlandsRoamer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(emil)
        set_board_state(game, 0, mana={ManaType.GREEN: 5})
        # Activate ability
        emil.activated_abilities[0].effect(game)
        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield if "Fractal" in c.name]
        assert len(tokens) >= 1

    def test_fractal_counters_equal_differently_named_lands(self) -> None:
        """X = number of differently named lands you control."""
        game = create_game()
        p1 = game.players[0]
        emil = EmilVastlandsRoamer(owner=p1, controller=p1)
        from engine.card import Land
        forest = Land(name="Forest", owner=p1, controller=p1)
        island = Land(name="Island", owner=p1, controller=p1)
        forest2 = Land(name="Forest", owner=p1, controller=p1)
        game.get_battlefield(p1).add(emil)
        game.get_battlefield(p1).add(forest)
        game.get_battlefield(p1).add(island)
        game.get_battlefield(p1).add(forest2)
        set_board_state(game, 0, mana={ManaType.GREEN: 5})
        emil.activated_abilities[0].effect(game)
        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield if "Fractal" in c.name]
        # 2 differently named lands: Forest and Island
        assert tokens[0].plus_one_counters == 2

    def test_fractal_is_zero_zero_base(self) -> None:
        """Fractal token should be a 0/0 base creature."""
        game = create_game()
        p1 = game.players[0]
        emil = EmilVastlandsRoamer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(emil)
        set_board_state(game, 0, mana={ManaType.GREEN: 5})
        emil.activated_abilities[0].effect(game)
        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield if "Fractal" in c.name]
        assert tokens[0].base_power == 0
        assert tokens[0].base_toughness == 0
