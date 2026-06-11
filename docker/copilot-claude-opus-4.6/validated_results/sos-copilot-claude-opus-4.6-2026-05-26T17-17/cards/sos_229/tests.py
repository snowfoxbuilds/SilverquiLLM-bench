"""Tests for SOS 229 — Spectacular Skywhale.

A 1/4 Elemental Whale for {2}{U}{R} with Flying.
Opus — Whenever you cast an instant or sorcery spell, this creature gets
+3/+0 until end of turn. If five or more mana was spent to cast that spell,
put three +1/+1 counters on this creature instead.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_229.card_impl import SpectacularSkywhale
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestSpectacularSkywhaleProperties:
    """Static card data should match the SOS 229 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(SpectacularSkywhale(owner=None), Creature)

    def test_name(self) -> None:
        assert SpectacularSkywhale(owner=None).name == "Spectacular Skywhale"

    def test_mana_cost(self) -> None:
        assert SpectacularSkywhale(owner=None).mana_cost == ManaCost.parse("{2}{U}{R}")

    def test_power_toughness(self) -> None:
        card = SpectacularSkywhale(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 4

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in SpectacularSkywhale(owner=None).keywords


class TestSpectacularSkywhaleOpus:
    """Opus trigger: +3/+0 on instant/sorcery, or three +1/+1 counters if 5+ mana spent."""

    def test_gets_plus_3_power_on_cheap_spell(self) -> None:
        """Casting a cheap instant/sorcery (<5 mana) gives +3/+0 until end of turn."""
        game = create_game()
        p1 = game.players[0]

        whale = SpectacularSkywhale(owner=p1, controller=p1)
        game.get_battlefield(p1).add(whale)

        spell = Instant(name="Cheap Spell", owner=p1, controller=p1)
        spell.mana_cost = ManaCost.parse("{U}")
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Cheap Spell")

        # Whale should have +3 power (base 1 + 3 = 4)
        assert whale.power == 4
        assert whale.toughness == 4  # toughness unchanged

    def test_no_counters_on_cheap_spell(self) -> None:
        """A cheap spell should NOT give +1/+1 counters."""
        game = create_game()
        p1 = game.players[0]

        whale = SpectacularSkywhale(owner=p1, controller=p1)
        game.get_battlefield(p1).add(whale)

        spell = Instant(name="Cheap Spell", owner=p1, controller=p1)
        spell.mana_cost = ManaCost.parse("{U}")
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1})

        counters_before = getattr(whale, 'plus_one_counters', 0)
        cast_spell(game, 0, "Cheap Spell")

        assert getattr(whale, 'plus_one_counters', 0) == counters_before

    def test_gets_three_counters_on_expensive_spell(self) -> None:
        """Casting a spell with 5+ mana spent gives three +1/+1 counters instead."""
        game = create_game()
        p1 = game.players[0]

        whale = SpectacularSkywhale(owner=p1, controller=p1)
        game.get_battlefield(p1).add(whale)

        spell = Sorcery(name="Expensive Spell", owner=p1, controller=p1)
        spell.mana_cost = ManaCost.parse("{3}{U}{R}")  # 5 mana total
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1, ManaType.RED: 1, ManaType.COLORLESS: 3})

        counters_before = getattr(whale, 'plus_one_counters', 0)
        cast_spell(game, 0, "Expensive Spell")

        # Should get 3 +1/+1 counters
        assert getattr(whale, 'plus_one_counters', 0) == counters_before + 3

    def test_no_temp_boost_on_expensive_spell(self) -> None:
        """The 'instead' clause means no +3/+0 when 5+ mana was spent."""
        game = create_game()
        p1 = game.players[0]

        whale = SpectacularSkywhale(owner=p1, controller=p1)
        game.get_battlefield(p1).add(whale)

        spell = Sorcery(name="Expensive Spell", owner=p1, controller=p1)
        spell.mana_cost = ManaCost.parse("{3}{U}{R}")
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1, ManaType.RED: 1, ManaType.COLORLESS: 3})
        cast_spell(game, 0, "Expensive Spell")

        # Power should be base + counters only, no temporary +3 boost
        # base 1 + 3 counters = 4 power
        assert whale.power == 4
        assert whale.toughness == 7  # base 4 + 3 counters

    def test_multiple_cheap_spells_stack(self) -> None:
        """Casting multiple cheap spells should stack the +3/+0 boosts."""
        game = create_game()
        p1 = game.players[0]

        whale = SpectacularSkywhale(owner=p1, controller=p1)
        game.get_battlefield(p1).add(whale)

        spell1 = Instant(name="Spell One", owner=p1, controller=p1)
        spell1.mana_cost = ManaCost.parse("{U}")
        spell2 = Instant(name="Spell Two", owner=p1, controller=p1)
        spell2.mana_cost = ManaCost.parse("{R}")

        set_board_state(game, 0, hand=[spell1, spell2], mana={ManaType.BLUE: 1, ManaType.RED: 1})
        cast_spell(game, 0, "Spell One")
        cast_spell(game, 0, "Spell Two")

        # Two triggers: +3+3 = +6 power total
        assert whale.power == 7  # base 1 + 6

    def test_temp_boost_ends_at_end_of_turn(self) -> None:
        """The +3/+0 boost should wear off at end of turn."""
        game = create_game()
        p1 = game.players[0]

        whale = SpectacularSkywhale(owner=p1, controller=p1)
        game.get_battlefield(p1).add(whale)

        spell = Instant(name="Cheap Spell", owner=p1, controller=p1)
        spell.mana_cost = ManaCost.parse("{U}")
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Cheap Spell")

        assert whale.power == 4  # boosted

        # End turn
        game.end_turn()

        # After end of turn, power should return to base
        assert whale.power == 1
