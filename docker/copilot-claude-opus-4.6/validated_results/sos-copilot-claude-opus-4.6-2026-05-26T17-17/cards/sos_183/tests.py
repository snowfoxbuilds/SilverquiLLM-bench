"""Tests for SOS 183 — Cuboid Colony."""

from __future__ import annotations

import pytest

from cards.sos.sos_183.card_impl import CuboidColony
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestCuboidColonyProperties:
    """Static card properties match the spec."""

    def test_name(self) -> None:
        card = CuboidColony(owner=None)
        assert card.name == "Cuboid Colony"

    def test_mana_cost(self) -> None:
        card = CuboidColony(owner=None)
        assert card.mana_cost == ManaCost.parse("{G}{U}")

    def test_power_toughness(self) -> None:
        card = CuboidColony(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_has_flash(self) -> None:
        card = CuboidColony(owner=None)
        assert Keyword.FLASH in card.keywords

    def test_has_flying(self) -> None:
        card = CuboidColony(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_trample(self) -> None:
        card = CuboidColony(owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_is_creature(self) -> None:
        card = CuboidColony(owner=None)
        assert CardType.CREATURE in card.card_types


class TestCuboidColonyIncrement:
    """Increment — Whenever you cast a spell, if the amount of mana spent is
    greater than this creature's power or toughness, put a +1/+1 counter on it."""

    def test_increment_triggers_when_mana_spent_exceeds_power(self) -> None:
        """Casting a 3-mana spell when Colony is 1/1 should add a counter."""
        game = create_game()
        colony = CuboidColony(owner=None)
        spell = Instant(name="Big Spell")
        spell.mana_cost = ManaCost.parse("{2}{U}")
        set_board_state(game, 0, battlefield=[colony], hand=[spell],
                        mana={ManaType.BLUE: 3, ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Big Spell")
        # Colony should now be 2/2 (1/1 + one +1/+1 counter)
        assert colony.power >= 2
        assert colony.toughness >= 2

    def test_increment_does_not_trigger_when_mana_equal_to_power(self) -> None:
        """Casting a 1-mana spell when Colony is 1/1 should NOT trigger (not greater)."""
        game = create_game()
        colony = CuboidColony(owner=None)
        spell = Instant(name="Tiny Spell")
        spell.mana_cost = ManaCost.parse("{U}")
        set_board_state(game, 0, battlefield=[colony], hand=[spell],
                        mana={ManaType.BLUE: 3})
        cast_spell(game, 0, "Tiny Spell")
        # Colony should remain 1/1
        assert colony.power == 1
        assert colony.toughness == 1

    def test_increment_triggers_multiple_times(self) -> None:
        """Multiple qualifying spells should each add a counter."""
        game = create_game()
        colony = CuboidColony(owner=None)
        spell1 = Instant(name="Spell One")
        spell1.mana_cost = ManaCost.parse("{1}{U}")
        spell2 = Instant(name="Spell Two")
        spell2.mana_cost = ManaCost.parse("{2}{U}")
        set_board_state(game, 0, battlefield=[colony], hand=[spell1, spell2],
                        mana={ManaType.BLUE: 5, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Spell One")
        cast_spell(game, 0, "Spell Two")
        # Both spells cost more than initial 1 power, so 2 counters total
        assert colony.power >= 3
        assert colony.toughness >= 3

    def test_increment_checks_current_power_or_toughness(self) -> None:
        """After getting a counter (now 2/2), a 2-mana spell should NOT trigger
        (2 is not greater than 2)."""
        game = create_game()
        colony = CuboidColony(owner=None)
        spell1 = Instant(name="Spell One")
        spell1.mana_cost = ManaCost.parse("{1}{U}")
        spell2 = Instant(name="Spell Two")
        spell2.mana_cost = ManaCost.parse("{1}{U}")
        set_board_state(game, 0, battlefield=[colony], hand=[spell1, spell2],
                        mana={ManaType.BLUE: 5, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Spell One")
        # Colony is now 2/2; casting a 2-mana spell should not trigger
        cast_spell(game, 0, "Spell Two")
        assert colony.power == 2
        assert colony.toughness == 2
