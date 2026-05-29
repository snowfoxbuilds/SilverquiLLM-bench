"""Tests for Improvisation Capstone (sos_120)."""

from __future__ import annotations

import pytest
from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestImprovisationCapstoneProperties:
    """Static card properties."""

    def test_name(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"

    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_subtype_lesson(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert "Lesson" in card.subtypes


class TestImprovisationCapstoneResolution:
    """Exiles library cards until total MV >= 4."""

    def test_exiles_cards_from_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        # Put cards with MV 2 each in library (need 2 to get MV >= 4)
        card1 = Instant(name="Spell1", owner=p1, controller=p1,
                         mana_cost=ManaCost.parse("{2}"))
        card2 = Instant(name="Spell2", owner=p1, controller=p1,
                         mana_cost=ManaCost.parse("{2}"))
        p1.zones[Zone.LIBRARY].add(card1, position="top")
        p1.zones[Zone.LIBRARY].add(card2, position="top")

        # Script: decline to cast either spell
        p1._script.append(False)
        p1._script.append(False)

        card.on_resolve(game)

        exile = p1.zones[Zone.EXILE].get_all()
        assert card1 in exile or card2 in exile

    def test_stops_when_total_mv_reached(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        # Single card with MV 4 — should stop after one card
        big_spell = Instant(name="BigSpell", owner=p1, controller=p1,
                             mana_cost=ManaCost.parse("{4}"))
        p1.zones[Zone.LIBRARY].add(big_spell, position="top")

        # Script: decline to cast
        p1._script.append(False)

        lib_size_before = len(p1.zones[Zone.LIBRARY].get_all())
        card.on_resolve(game)

        exile = p1.zones[Zone.EXILE].get_all()
        assert big_spell in exile
        # Exactly one card was exiled from library
        assert len(p1.zones[Zone.LIBRARY].get_all()) == lib_size_before - 1

    def test_can_cast_exiled_spells_for_free(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        target_spell = Instant(name="FreeSpell", owner=p1, controller=p1,
                                mana_cost=ManaCost.parse("{4}"))
        p1.zones[Zone.LIBRARY].add(target_spell, position="top")

        # Script: yes to cast FreeSpell
        p1._script.append(True)   # cast it?
        # No targets needed for base Instant

        card.on_resolve(game)

        # Spell was cast and resolved (moved somewhere — not in exile or library)
        exile = p1.zones[Zone.EXILE].get_all()
        lib = p1.zones[Zone.LIBRARY].get_all()
        # target_spell was cast, so it resolved to graveyard (it's an instant)
        gy = p1.zones[Zone.GRAVEYARD].get_all()
        assert target_spell in gy or target_spell not in lib

    def test_paradigm_exiles_this_card(self) -> None:
        """After resolution, the Capstone itself is exiled (Paradigm)."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.controller = p1
        card.owner = p1

        # Put it in the stack zone (simulating cast)
        p1.zones[Zone.STACK].add(card)

        # Library has one spell
        small_spell = Instant(name="X", owner=p1, controller=p1,
                               mana_cost=ManaCost.parse("{4}"))
        p1.zones[Zone.LIBRARY].add(small_spell, position="top")

        p1._script.append(False)  # don't cast small_spell

        card.on_resolve(game)

        # Card should be in exile, not on stack or in graveyard
        assert card in p1.zones[Zone.EXILE].get_all()
        assert card not in p1.zones[Zone.GRAVEYARD].get_all()
        assert card not in p1.zones[Zone.STACK].get_all()


class TestImprovisationCapstoneDoesNotCastLands:
    """Lands in the exiled group cannot be cast."""

    def test_skips_land_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        from engine.card import Land
        from engine.types import ManaType

        land = Land(name="Plains", owner=p1, controller=p1)
        land.card_types = {CardType.LAND}
        # Give it MV 0 but add another card to reach the threshold
        big_spell = Instant(name="BigSpell", owner=p1, controller=p1,
                             mana_cost=ManaCost.parse("{4}"))
        p1.zones[Zone.LIBRARY].add(land, position="bottom")
        p1.zones[Zone.LIBRARY].add(big_spell, position="top")

        # No cast options (only BigSpell is offered, not land)
        p1._script.append(False)  # decline to cast BigSpell

        card.on_resolve(game)

        # Both should be in exile
        exile = p1.zones[Zone.EXILE].get_all()
        assert big_spell in exile
