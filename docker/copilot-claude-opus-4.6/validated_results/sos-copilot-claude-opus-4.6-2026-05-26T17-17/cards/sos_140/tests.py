"""Tests for SOS 140 — Ambitious Augmenter.

A {G} 1/1 Creature — Turtle Wizard with:
- Increment (Whenever you cast a spell, if the amount of mana spent is greater
  than this creature's power or toughness, put a +1/+1 counter on this creature.)
- When this creature dies, if it had one or more counters on it, create a 0/0
  green and blue Fractal creature token, then put this creature's counters on
  that token.
"""

from __future__ import annotations

from cards.sos.sos_140.card_impl import AmbitiousAugmenter
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestAmbitiousAugmenterProperties:
    """Static card data should match the SOS 140 spec."""

    def test_is_creature(self) -> None:
        card = AmbitiousAugmenter(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = AmbitiousAugmenter(owner=None)
        assert card.name == "Ambitious Augmenter"

    def test_mana_cost(self) -> None:
        card = AmbitiousAugmenter(owner=None)
        assert card.mana_cost == ManaCost.parse("{G}")

    def test_power_toughness(self) -> None:
        card = AmbitiousAugmenter(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1


class TestAmbitiousAugmenterIncrement:
    """Increment: put +1/+1 counter when mana spent > power or toughness."""

    def test_increment_triggers_when_mana_spent_exceeds_power(self) -> None:
        game = create_game()
        p1 = game.players[0]

        augmenter = AmbitiousAugmenter(owner=p1, controller=p1)
        augmenter.plus_one_counters = 0
        game.get_battlefield(p1).add(augmenter)

        # Cast a spell costing 2 mana (> power 1)
        spell = Instant(name="Test Spell", owner=p1)
        spell.mana_spent = 2

        augmenter.on_spell_cast(game, spell)

        assert augmenter.plus_one_counters == 1

    def test_increment_does_not_trigger_when_mana_equal_to_power(self) -> None:
        game = create_game()
        p1 = game.players[0]

        augmenter = AmbitiousAugmenter(owner=p1, controller=p1)
        augmenter.plus_one_counters = 0
        game.get_battlefield(p1).add(augmenter)

        # Cast a spell costing 1 mana (= power 1, not greater)
        spell = Instant(name="Test Spell", owner=p1)
        spell.mana_spent = 1

        augmenter.on_spell_cast(game, spell)

        assert augmenter.plus_one_counters == 0

    def test_increment_checks_current_power_with_counters(self) -> None:
        """After getting counters, the threshold increases."""
        game = create_game()
        p1 = game.players[0]

        augmenter = AmbitiousAugmenter(owner=p1, controller=p1)
        augmenter.plus_one_counters = 2  # effective power = 3, toughness = 3
        game.get_battlefield(p1).add(augmenter)

        # Cast a spell costing 3 (not greater than 3)
        spell = Instant(name="Test Spell", owner=p1)
        spell.mana_spent = 3

        augmenter.on_spell_cast(game, spell)

        # Should NOT get a counter (3 is not > 3)
        assert augmenter.plus_one_counters == 2

    def test_increment_triggers_when_mana_exceeds_grown_stats(self) -> None:
        """After counters raise stats, higher cost spells still trigger."""
        game = create_game()
        p1 = game.players[0]

        augmenter = AmbitiousAugmenter(owner=p1, controller=p1)
        augmenter.plus_one_counters = 2  # effective power = 3, toughness = 3
        game.get_battlefield(p1).add(augmenter)

        # Cast a spell costing 4 (> 3)
        spell = Instant(name="Big Spell", owner=p1)
        spell.mana_spent = 4

        augmenter.on_spell_cast(game, spell)

        assert augmenter.plus_one_counters == 3


class TestAmbitiousAugmenterDiesTrigger:
    """When this dies with counters, create Fractal token and transfer counters."""

    def test_creates_fractal_token_on_death_with_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]

        augmenter = AmbitiousAugmenter(owner=p1, controller=p1)
        augmenter.plus_one_counters = 2
        game.get_battlefield(p1).add(augmenter)

        bf_before = len(game.get_battlefield(p1).get_all())
        augmenter.on_death(game)

        # Should create a fractal token (net change: +1 token, -1 augmenter = 0 or +1)
        bf_after = len(game.get_battlefield(p1).get_all())
        # A new fractal token should exist
        fractals = [c for c in game.get_battlefield(p1).get_all()
                    if "Fractal" in getattr(c, "subtypes", set())
                    or "Fractal" in getattr(c, "name", "")]
        assert len(fractals) >= 1

    def test_fractal_token_receives_counters_from_augmenter(self) -> None:
        game = create_game()
        p1 = game.players[0]

        augmenter = AmbitiousAugmenter(owner=p1, controller=p1)
        augmenter.plus_one_counters = 3
        game.get_battlefield(p1).add(augmenter)

        augmenter.on_death(game)

        fractals = [c for c in game.get_battlefield(p1).get_all()
                    if "Fractal" in getattr(c, "subtypes", set())
                    or "Fractal" in getattr(c, "name", "")]
        assert len(fractals) >= 1
        fractal = fractals[0]

        # Fractal should have the same number of counters
        assert fractal.plus_one_counters == 3

    def test_no_token_created_if_no_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]

        augmenter = AmbitiousAugmenter(owner=p1, controller=p1)
        augmenter.plus_one_counters = 0
        game.get_battlefield(p1).add(augmenter)

        augmenter.on_death(game)

        # No fractal token should be created
        fractals = [c for c in game.get_battlefield(p1).get_all()
                    if "Fractal" in getattr(c, "subtypes", set())
                    or "Fractal" in getattr(c, "name", "")]
        assert len(fractals) == 0
