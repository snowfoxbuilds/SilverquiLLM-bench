"""Tests for SOS 185 — Elemental Mascot."""

from __future__ import annotations

import pytest

from cards.sos.sos_185.card_impl import ElementalMascot
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestElementalMascotProperties:
    """Static card properties match the spec."""

    def test_name(self) -> None:
        card = ElementalMascot(owner=None)
        assert card.name == "Elemental Mascot"

    def test_mana_cost(self) -> None:
        card = ElementalMascot(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}{R}")

    def test_power_toughness(self) -> None:
        card = ElementalMascot(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 4

    def test_has_flying(self) -> None:
        card = ElementalMascot(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance(self) -> None:
        card = ElementalMascot(owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_is_creature(self) -> None:
        card = ElementalMascot(owner=None)
        assert CardType.CREATURE in card.card_types


class TestElementalMascotOpus:
    """Opus — Whenever you cast an instant or sorcery spell, this creature gets
    +1/+0 until end of turn. If five or more mana was spent to cast that spell,
    exile the top card of your library. You may play that card until the end of
    your next turn."""

    def test_gets_plus_one_power_on_instant_cast(self) -> None:
        """Any instant/sorcery should give +1/+0."""
        game = create_game()
        mascot = ElementalMascot(owner=None)
        spell = Instant(name="Cheap Spell")
        spell.mana_cost = ManaCost.parse("{U}")
        set_board_state(game, 0, battlefield=[mascot], hand=[spell],
                        mana={ManaType.BLUE: 5, ManaType.RED: 5})
        cast_spell(game, 0, "Cheap Spell")
        assert mascot.power >= 2  # 1 base + 1 from opus

    def test_power_boost_is_temporary(self) -> None:
        """The +1/+0 lasts until end of turn only."""
        game = create_game()
        mascot = ElementalMascot(owner=None)
        spell = Instant(name="Cheap Spell")
        spell.mana_cost = ManaCost.parse("{U}")
        set_board_state(game, 0, battlefield=[mascot], hand=[spell],
                        mana={ManaType.BLUE: 5, ManaType.RED: 5})
        cast_spell(game, 0, "Cheap Spell")
        # Advance to cleanup/next turn
        from test_utils import advance_to_phase
        from engine.types import Phase, Step
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        assert mascot.power == 1

    def test_multiple_spells_stack_power_boost(self) -> None:
        """Multiple instant/sorcery casts each add +1/+0."""
        game = create_game()
        mascot = ElementalMascot(owner=None)
        spell1 = Instant(name="Spell A")
        spell1.mana_cost = ManaCost.parse("{U}")
        spell2 = Instant(name="Spell B")
        spell2.mana_cost = ManaCost.parse("{R}")
        set_board_state(game, 0, battlefield=[mascot], hand=[spell1, spell2],
                        mana={ManaType.BLUE: 5, ManaType.RED: 5})
        cast_spell(game, 0, "Spell A")
        cast_spell(game, 0, "Spell B")
        assert mascot.power >= 3  # 1 base + 2 from two triggers

    def test_five_mana_spell_exiles_top_of_library(self) -> None:
        """If five or more mana was spent, exile the top card of library."""
        game = create_game()
        mascot = ElementalMascot(owner=None)
        big_spell = Instant(name="Big Spell")
        big_spell.mana_cost = ManaCost.parse("{3}{U}{R}")
        top_card = Creature(name="Library Top", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[mascot], hand=[big_spell],
                        mana={ManaType.BLUE: 5, ManaType.RED: 5, ManaType.COLORLESS: 5})
        game.players[0].library = [top_card]
        cast_spell(game, 0, "Big Spell")
        # The top card should now be in exile
        exile_names = [c.name for c in game.players[0].exile]
        assert "Library Top" in exile_names

    def test_less_than_five_mana_does_not_exile(self) -> None:
        """If less than five mana was spent, no exile occurs."""
        game = create_game()
        mascot = ElementalMascot(owner=None)
        small_spell = Instant(name="Small Spell")
        small_spell.mana_cost = ManaCost.parse("{1}{U}")
        top_card = Creature(name="Library Top", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[mascot], hand=[small_spell],
                        mana={ManaType.BLUE: 5, ManaType.RED: 5, ManaType.COLORLESS: 5})
        game.players[0].library = [top_card]
        cast_spell(game, 0, "Small Spell")
        # Library top should still be in library
        assert len(game.players[0].library) == 1

    def test_does_not_trigger_on_creature_spell(self) -> None:
        """Opus only triggers on instant or sorcery, not creature spells."""
        game = create_game()
        mascot = ElementalMascot(owner=None)
        creature = Creature(name="Random Creature", base_power=2, base_toughness=2)
        creature.mana_cost = ManaCost.parse("{1}{U}")
        set_board_state(game, 0, battlefield=[mascot], hand=[creature],
                        mana={ManaType.BLUE: 5, ManaType.RED: 5, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Random Creature")
        assert mascot.power == 1  # No boost
