"""Tests for SOS 165 — Topiary Lecturer.

A 1/2 Elf Druid for {2}{G} with:
- Increment (Whenever you cast a spell, if the amount of mana you spent is
  greater than this creature's power or toughness, put a +1/+1 counter on
  this creature.)
- {T}: Add an amount of {G} equal to this creature's power.
"""

from __future__ import annotations

from cards.sos.sos_165.card_impl import TopiaryLecturer
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType
from test_utils import create_game


class TestTopiaryLecturerProperties:
    """Static card data should match the SOS 165 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(TopiaryLecturer(owner=None), Creature)

    def test_name(self) -> None:
        assert TopiaryLecturer(owner=None).name == "Topiary Lecturer"

    def test_mana_cost(self) -> None:
        assert TopiaryLecturer(owner=None).mana_cost == ManaCost.parse("{2}{G}")

    def test_power_toughness(self) -> None:
        card = TopiaryLecturer(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 2


class TestTopiaryLecturerIncrement:
    """Increment — gets +1/+1 counter when you spend more mana than P or T."""

    def test_counter_when_mana_spent_exceeds_power(self) -> None:
        """Casting a spell for 2+ mana should trigger increment (power is 1)."""
        game = create_game()
        p1 = game.players[0]
        card = TopiaryLecturer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        counters_before = card.plus_one_counters
        # Notify increment: mana spent = 2 > power (1)
        card.on_spell_cast(game, mana_spent=2)
        assert card.plus_one_counters == counters_before + 1

    def test_counter_when_mana_spent_exceeds_toughness(self) -> None:
        """Casting a spell for 3+ mana should trigger (toughness is 2)."""
        game = create_game()
        p1 = game.players[0]
        card = TopiaryLecturer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        counters_before = card.plus_one_counters
        card.on_spell_cast(game, mana_spent=3)
        assert card.plus_one_counters == counters_before + 1

    def test_no_counter_when_mana_spent_equals_power(self) -> None:
        """Spending mana equal to power (not greater) should NOT trigger."""
        game = create_game()
        p1 = game.players[0]
        card = TopiaryLecturer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        counters_before = card.plus_one_counters
        # Spend 1 mana, equal to power (1) but not greater
        card.on_spell_cast(game, mana_spent=1)
        assert card.plus_one_counters == counters_before

    def test_no_counter_when_mana_spent_less_than_both(self) -> None:
        """Spending 0 mana (free spell) shouldn't trigger."""
        game = create_game()
        p1 = game.players[0]
        card = TopiaryLecturer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        counters_before = card.plus_one_counters
        card.on_spell_cast(game, mana_spent=0)
        assert card.plus_one_counters == counters_before

    def test_increment_uses_current_power_with_counters(self) -> None:
        """After getting counters, threshold increases."""
        game = create_game()
        p1 = game.players[0]
        card = TopiaryLecturer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # Add a counter (now power=2, toughness=3)
        card.plus_one_counters = 1
        counters_before = card.plus_one_counters
        # Spending 2 mana no longer exceeds power (which is now 2)
        # But we need to check if it exceeds toughness (3) — it doesn't
        # Actually, "greater than power OR toughness" means > power or > toughness
        # power=2, toughness=3; spending 2 is not > 2, not > 3
        card.on_spell_cast(game, mana_spent=2)
        assert card.plus_one_counters == counters_before


class TestTopiaryLecturerManaAbility:
    """Tap ability: Add {G} equal to this creature's power."""

    def test_produces_green_mana_equal_to_power(self) -> None:
        """With base power 1, should produce 1 green mana."""
        game = create_game()
        p1 = game.players[0]
        card = TopiaryLecturer(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)
        mana_produced = card.activate_mana_ability(game)
        assert mana_produced[ManaType.GREEN] == 1

    def test_produces_more_mana_with_counters(self) -> None:
        """With +1/+1 counters increasing power, produces more mana."""
        game = create_game()
        p1 = game.players[0]
        card = TopiaryLecturer(owner=p1, controller=p1)
        card.is_tapped = False
        card.plus_one_counters = 2  # power is now 3
        game.get_battlefield(p1).add(card)
        mana_produced = card.activate_mana_ability(game)
        assert mana_produced[ManaType.GREEN] == 3

    def test_taps_when_activated(self) -> None:
        """Activating the mana ability should tap the creature."""
        game = create_game()
        p1 = game.players[0]
        card = TopiaryLecturer(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)
        card.activate_mana_ability(game)
        assert card.is_tapped is True

    def test_cannot_activate_when_tapped(self) -> None:
        """Should not be able to activate mana ability when already tapped."""
        game = create_game()
        p1 = game.players[0]
        card = TopiaryLecturer(owner=p1, controller=p1)
        card.is_tapped = True
        game.get_battlefield(p1).add(card)
        result = card.can_activate_mana_ability(game)
        assert result is False
