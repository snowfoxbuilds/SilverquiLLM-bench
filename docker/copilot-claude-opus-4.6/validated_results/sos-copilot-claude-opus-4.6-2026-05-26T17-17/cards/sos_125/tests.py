"""Tests for SOS 125 — Molten-Core Maestro."""

from __future__ import annotations

import pytest

from cards.sos.sos_125.card_impl import MoltenCoreMaestro
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestMoltenCoreMaestroProperties:
    """Static card data should match the SOS 125 spec."""

    def test_is_creature(self) -> None:
        card = MoltenCoreMaestro(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert MoltenCoreMaestro(owner=None).name == "Molten-Core Maestro"

    def test_mana_cost(self) -> None:
        assert MoltenCoreMaestro(owner=None).mana_cost == ManaCost.parse("{1}{R}")

    def test_power_toughness(self) -> None:
        card = MoltenCoreMaestro(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_menace(self) -> None:
        card = MoltenCoreMaestro(owner=None)
        assert Keyword.MENACE in card.keywords


class TestMoltenCoreMaestroOpusTrigger:
    """Whenever you cast an instant or sorcery, put a +1/+1 counter on this creature."""

    def test_gets_counter_on_spell_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        maestro.card_types = {CardType.CREATURE}
        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[maestro],
                        hand=[bolt],
                        mana={ManaType.RED: 1})
        initial_counters = maestro.plus_one_counters
        cast_spell(game, 0, "Test Bolt")
        assert maestro.plus_one_counters == initial_counters + 1

    def test_no_counter_on_creature_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        maestro.card_types = {CardType.CREATURE}
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        set_board_state(game, 0, battlefield=[maestro],
                        hand=[bear],
                        mana={ManaType.COLORLESS: 2})
        initial_counters = maestro.plus_one_counters
        cast_spell(game, 0, "Grizzly Bears")
        assert maestro.plus_one_counters == initial_counters


class TestMoltenCoreMaestroManaGeneration:
    """If five or more mana was spent to cast that spell, add {R} equal to this creature's power."""

    def test_five_mana_spell_adds_red_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        maestro.card_types = {CardType.CREATURE}
        maestro.plus_one_counters = 1  # power = 3
        expensive_spell = Instant(name="Big Spell", owner=p1, controller=p1)
        expensive_spell.mana_cost = ManaCost.parse("{4}{R}")
        set_board_state(game, 0, battlefield=[maestro],
                        hand=[expensive_spell],
                        mana={ManaType.RED: 1, ManaType.COLORLESS: 4})
        cast_spell(game, 0, "Big Spell")
        # Should have added R equal to maestro's power (3 after counter from trigger)
        # Maestro gets a counter from the trigger too, so power=4 at resolution
        mana_pool = game.get_mana_pool(p1)
        assert mana_pool.get(ManaType.RED, 0) >= 3

    def test_cheap_spell_no_mana_added(self) -> None:
        game = create_game()
        p1 = game.players[0]
        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        maestro.card_types = {CardType.CREATURE}
        bolt = Instant(name="Cheap Bolt", owner=p1, controller=p1)
        bolt.mana_cost = ManaCost.parse("{R}")
        set_board_state(game, 0, battlefield=[maestro],
                        hand=[bolt],
                        mana={ManaType.RED: 1})
        cast_spell(game, 0, "Cheap Bolt")
        # Only 1 mana spent, no red mana generated
        mana_pool = game.get_mana_pool(p1)
        assert mana_pool.get(ManaType.RED, 0) == 0
