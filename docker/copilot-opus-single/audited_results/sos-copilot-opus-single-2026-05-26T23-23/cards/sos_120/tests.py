"""Tests for SOS 120 — Improvisation Capstone.

Improvisation Capstone is a {5}{R}{R} Sorcery — Lesson with Paradigm.

Oracle text:
  Exile cards from the top of your library until you exile cards with total
  mana value 4 or greater. You may cast any number of spells from among them
  without paying their mana costs.
  Paradigm (Then exile this spell. After you first resolve a spell with this
  name, you may cast a copy of it from exile without paying its mana cost at
  the beginning of each of your first main phases.)
"""

from __future__ import annotations

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Sorcery, Creature, CardImpl
from engine.types import CardType, ManaCost, ManaType, Zone, Phase


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_mana_value_is_7(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost.cmc == 7

    def test_has_sorcery_card_type(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_has_lesson_subtype(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert "Lesson" in card.subtypes

    def test_color_red(self) -> None:
        """The card should be red (has R pips in cost)."""
        card = ImprovisationCapstone(owner=None)
        assert ManaType.RED in card.mana_cost.pips


class TestImprovisationCapstoneExileAbility:
    """Test the 'exile from top until total MV >= 4' ability."""

    def test_exiles_cards_until_total_mv_4_or_greater(self) -> None:
        """Should exile cards from library top until cumulative MV >= 4."""
        from test_utils import create_game, set_board_state, cast_spell

        game = create_game()
        capstone = ImprovisationCapstone(owner=game.players[0])

        # Create library cards with known mana values:
        # Card MV 1, Card MV 1, Card MV 2 => total = 4, stop
        lib_card_1 = Creature(
            name="Tiny One", base_power=1, base_toughness=1,
            mana_cost=ManaCost.parse("{R}"), owner=game.players[0]
        )
        lib_card_2 = Creature(
            name="Tiny Two", base_power=1, base_toughness=1,
            mana_cost=ManaCost.parse("{G}"), owner=game.players[0]
        )
        lib_card_3 = Creature(
            name="Bear", base_power=2, base_toughness=2,
            mana_cost=ManaCost.parse("{1}{G}"), owner=game.players[0]
        )
        # Extra card that should NOT be exiled
        lib_card_4 = Creature(
            name="Leftover", base_power=3, base_toughness=3,
            mana_cost=ManaCost.parse("{2}{R}"), owner=game.players[0]
        )

        # Library is ordered top-first: card_1 is on top
        set_board_state(game, 0,
                        hand=[capstone],
                        mana={ManaType.RED: 7, ManaType.COLORLESS: 5})
        # Set library manually
        game.players[0].zones[Zone.LIBRARY]._objects = [
            lib_card_1, lib_card_2, lib_card_3, lib_card_4
        ]

        cast_spell(game, 0, "Improvisation Capstone")

        # After resolution, lib_card_1, lib_card_2, lib_card_3 should be exiled
        # (total MV = 1 + 1 + 2 = 4)
        exile = game.players[0].zones[Zone.EXILE]
        exiled_names = [c.name for c in exile]
        assert "Tiny One" in exiled_names
        assert "Tiny Two" in exiled_names
        assert "Bear" in exiled_names
        # Leftover should remain in library
        lib_names = [c.name for c in game.players[0].zones[Zone.LIBRARY]]
        assert "Leftover" in lib_names

    def test_stops_exiling_once_mv_threshold_reached(self) -> None:
        """If the first card has MV >= 4, only that one card is exiled."""
        from test_utils import create_game, set_board_state, cast_spell

        game = create_game()
        capstone = ImprovisationCapstone(owner=game.players[0])

        big_card = Creature(
            name="Big Beast", base_power=4, base_toughness=4,
            mana_cost=ManaCost.parse("{3}{G}"), owner=game.players[0]
        )
        remaining = Creature(
            name="Remaining", base_power=1, base_toughness=1,
            mana_cost=ManaCost.parse("{W}"), owner=game.players[0]
        )

        set_board_state(game, 0,
                        hand=[capstone],
                        mana={ManaType.RED: 7, ManaType.COLORLESS: 5})
        game.players[0].zones[Zone.LIBRARY]._objects = [big_card, remaining]

        cast_spell(game, 0, "Improvisation Capstone")

        exile = game.players[0].zones[Zone.EXILE]
        exiled_names = [c.name for c in exile]
        assert "Big Beast" in exiled_names
        # Remaining should still be in library
        lib_names = [c.name for c in game.players[0].zones[Zone.LIBRARY]]
        assert "Remaining" in lib_names

    def test_cast_exiled_spells_without_paying_mana(self) -> None:
        """Should be able to cast the exiled spells for free."""
        from test_utils import create_game, set_board_state, cast_spell

        game = create_game()
        capstone = ImprovisationCapstone(owner=game.players[0])

        # A 4-MV creature to exile
        creature = Creature(
            name="Free Cast", base_power=3, base_toughness=3,
            mana_cost=ManaCost.parse("{2}{R}{R}"), owner=game.players[0]
        )

        set_board_state(game, 0,
                        hand=[capstone],
                        mana={ManaType.RED: 7, ManaType.COLORLESS: 5})
        game.players[0].zones[Zone.LIBRARY]._objects = [creature]

        cast_spell(game, 0, "Improvisation Capstone")

        # The creature should end up on battlefield (cast for free)
        bf_names = [c.name for c in game.players[0].zones[Zone.BATTLEFIELD]]
        assert "Free Cast" in bf_names

    def test_empty_library_stops_exiling(self) -> None:
        """If library runs out before reaching MV 4, exile what's available."""
        from test_utils import create_game, set_board_state, cast_spell

        game = create_game()
        capstone = ImprovisationCapstone(owner=game.players[0])

        # Only one card with MV 1 in library
        tiny = Creature(
            name="Solo", base_power=1, base_toughness=1,
            mana_cost=ManaCost.parse("{R}"), owner=game.players[0]
        )

        set_board_state(game, 0,
                        hand=[capstone],
                        mana={ManaType.RED: 7, ManaType.COLORLESS: 5})
        game.players[0].zones[Zone.LIBRARY]._objects = [tiny]

        # Should not crash even though total MV < 4
        cast_spell(game, 0, "Improvisation Capstone")

        exile = game.players[0].zones[Zone.EXILE]
        exiled_names = [c.name for c in exile]
        assert "Solo" in exiled_names


class TestImprovisationCapstoneParadigm:
    """Test the Paradigm keyword behavior."""

    def test_capstone_exiled_after_resolution(self) -> None:
        """Paradigm: the spell itself goes to exile after resolution."""
        from test_utils import create_game, set_board_state, cast_spell

        game = create_game()
        capstone = ImprovisationCapstone(owner=game.players[0])

        # Put a card in library so the spell has something to exile
        filler = Creature(
            name="Filler", base_power=4, base_toughness=4,
            mana_cost=ManaCost.parse("{3}{R}"), owner=game.players[0]
        )

        set_board_state(game, 0,
                        hand=[capstone],
                        mana={ManaType.RED: 7, ManaType.COLORLESS: 5})
        game.players[0].zones[Zone.LIBRARY]._objects = [filler]

        cast_spell(game, 0, "Improvisation Capstone")

        # Capstone itself should be in exile (not graveyard)
        exile = game.players[0].zones[Zone.EXILE]
        exiled_names = [c.name for c in exile]
        assert "Improvisation Capstone" in exiled_names

        # Should NOT be in graveyard
        gy_names = [c.name for c in game.players[0].zones[Zone.GRAVEYARD]]
        assert "Improvisation Capstone" not in gy_names

    def test_paradigm_grants_copy_on_subsequent_main_phases(self) -> None:
        """After first resolution, get a free copy at beginning of first
        main phase on subsequent turns."""
        from test_utils import create_game, set_board_state, cast_spell, advance_to_phase

        game = create_game()
        capstone = ImprovisationCapstone(owner=game.players[0])

        filler = Creature(
            name="Filler", base_power=4, base_toughness=4,
            mana_cost=ManaCost.parse("{3}{R}"), owner=game.players[0]
        )

        set_board_state(game, 0,
                        hand=[capstone],
                        mana={ManaType.RED: 7, ManaType.COLORLESS: 5})
        game.players[0].zones[Zone.LIBRARY]._objects = [filler]

        # First resolution
        cast_spell(game, 0, "Improvisation Capstone")

        # Advance to next turn's first main phase
        # Put more cards in library for the paradigm copy to exile
        filler2 = Creature(
            name="Filler2", base_power=4, base_toughness=4,
            mana_cost=ManaCost.parse("{3}{G}"), owner=game.players[0]
        )
        game.players[0].zones[Zone.LIBRARY]._objects = [filler2]

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        # The paradigm should trigger, offering to cast a copy
        # After paradigm triggers and resolves, Filler2 should be exiled/cast
        bf_names = [c.name for c in game.players[0].zones[Zone.BATTLEFIELD]]
        assert "Filler2" in bf_names

    def test_paradigm_does_not_trigger_before_first_resolution(self) -> None:
        """Paradigm copy should not be available before the spell has been
        resolved at least once."""
        from test_utils import create_game, set_board_state, advance_to_phase

        game = create_game()

        # Put capstone directly in exile without having cast it
        capstone = ImprovisationCapstone(owner=game.players[0])
        set_board_state(game, 0, mana={ManaType.RED: 7, ManaType.COLORLESS: 5})
        game.players[0].zones[Zone.EXILE]._objects.append(capstone)

        # Put a card in library
        filler = Creature(
            name="ShouldNotBeCast", base_power=4, base_toughness=4,
            mana_cost=ManaCost.parse("{3}{R}"), owner=game.players[0]
        )
        game.players[0].zones[Zone.LIBRARY]._objects = [filler]

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        # Nothing should have been cast from paradigm
        bf_names = [c.name for c in game.players[0].zones[Zone.BATTLEFIELD]]
        assert "ShouldNotBeCast" not in bf_names
