"""Tests for sos_120 — Improvisation Capstone."""

from __future__ import annotations

import pytest
from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land, Sorcery
from engine.casting import cast_spell as _engine_cast
from engine.game_state import Phase
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, _resolve_top_of_stack


class TestCapstoneProperties:
    def test_name(self) -> None:
        assert ImprovisationCapstone().name == "Improvisation Capstone"

    def test_is_sorcery(self) -> None:
        assert CardType.SORCERY in ImprovisationCapstone().card_types

    def test_mana_cost(self) -> None:
        c = ImprovisationCapstone()
        assert c.mana_cost.cmc == 7


class TestLibraryExile:
    def test_exiles_until_total_cmc_four(self) -> None:
        """Cards are exiled until cumulative CMC >= 4."""
        game = create_game()
        p0 = game.players[0]

        # Library: two cards with CMC 2 each (total 4 = stop after both)
        c1 = Instant(name="Spell1", mana_cost=ManaCost(generic=2))
        c2 = Instant(name="Spell2", mana_cost=ManaCost(generic=2))
        c3 = Instant(name="Spell3", mana_cost=ManaCost(generic=1))  # should not be exiled
        set_board_state(game, 0, graveyard=[])

        p0.zones[Zone.LIBRARY]._objects.clear()
        for card in [c3, c2, c1]:  # top = c1 (last = top)
            card.owner = p0
            card.controller = p0
            p0.zones[Zone.LIBRARY]._objects.append(card)

        # Script: decline to cast both
        p0._script.extend([False, False])

        capstone = ImprovisationCapstone()
        capstone.controller = p0
        capstone.owner = p0
        capstone.on_resolve(game)

        exile = p0.zones[Zone.EXILE]
        assert exile.contains(c1)
        assert exile.contains(c2)
        assert not exile.contains(c3)

    def test_lands_exiled_but_not_offered_for_cast(self) -> None:
        """Land cards are exiled (count toward CMC=0) but not offered to cast."""
        game = create_game()
        p0 = game.players[0]

        land = Land(name="Plains")
        spell = Instant(name="Bolt", mana_cost=ManaCost(generic=4))
        p0.zones[Zone.LIBRARY]._objects.clear()
        for card in [spell, land]:  # top = land
            card.owner = p0
            card.controller = p0
            p0.zones[Zone.LIBRARY]._objects.append(card)

        # Land has CMC=0, so we continue to spell (CMC=4, total=4 → stop)
        # No cast offer for land; one yes/no for spell
        p0._script.append(False)  # decline spell

        capstone = ImprovisationCapstone()
        capstone.controller = p0
        capstone.owner = p0
        capstone.on_resolve(game)

        exile = p0.zones[Zone.EXILE]
        assert exile.contains(land)
        assert exile.contains(spell)

    def test_library_runs_out(self) -> None:
        """Stops when library is empty even if CMC < 4."""
        game = create_game()
        p0 = game.players[0]

        c1 = Instant(name="Tiny", mana_cost=ManaCost(generic=1))
        p0.zones[Zone.LIBRARY]._objects.clear()
        c1.owner = p0
        c1.controller = p0
        p0.zones[Zone.LIBRARY]._objects.append(c1)

        # Decline to cast
        p0._script.append(False)

        capstone = ImprovisationCapstone()
        capstone.controller = p0
        capstone.owner = p0
        capstone.on_resolve(game)

        exile = p0.zones[Zone.EXILE]
        assert exile.contains(c1)
        assert len(p0.zones[Zone.LIBRARY]._objects) == 0


class TestParadigm:
    def _cast_capstone(self, game, p0, capstone):
        """Helper: cast capstone and resolve it."""
        set_board_state(game, 0, hand=[capstone], mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        _engine_cast(game, p0, capstone)
        _resolve_top_of_stack(game)

    def test_first_resolution_exiles_capstone(self) -> None:
        """After first resolution, the Capstone goes to exile (Paradigm)."""
        game = create_game()
        p0 = game.players[0]
        capstone = ImprovisationCapstone()

        # No library cards for simplicity
        p0.zones[Zone.LIBRARY]._objects.clear()
        # Decline Paradigm trigger offer
        p0._script.append(False)  # choose_yes_no for paradigm on next main phase

        self._cast_capstone(game, p0, capstone)

        assert p0.zones[Zone.EXILE].contains(capstone)
        assert not p0.zones[Zone.GRAVEYARD].contains(capstone)

    def test_paradigm_trigger_fires_at_next_precombat_main(self) -> None:
        """Recurring Paradigm trigger fires at each precombat main phase."""
        game = create_game()
        p0 = game.players[0]
        capstone = ImprovisationCapstone()
        p0.zones[Zone.LIBRARY]._objects.clear()

        self._cast_capstone(game, p0, capstone)

        # Now fire the BeginningOfPrecombatMainTriggeredEvent for p0
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        game.active_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfPrecombatMainTriggeredEvent())

        # Trigger is on the stack — resolve it with "decline" choice
        p0._script.append(False)  # decline to cast copy
        _resolve_top_of_stack(game)

        # Original should still be in exile
        assert p0.zones[Zone.EXILE].contains(capstone)

    def test_paradigm_copy_resolves_main_effect(self) -> None:
        """The Paradigm copy performs the main exile-from-library effect."""
        game = create_game()
        p0 = game.players[0]
        capstone = ImprovisationCapstone()
        p0.zones[Zone.LIBRARY]._objects.clear()

        self._cast_capstone(game, p0, capstone)

        # Set up a spell in library for the copy to exile
        bolt = Instant(name="Bolt", mana_cost=ManaCost(generic=4))
        bolt.owner = p0
        bolt.controller = p0
        p0.zones[Zone.LIBRARY]._objects.append(bolt)

        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        game.active_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfPrecombatMainTriggeredEvent())

        # Resolve trigger: accept copy, decline to cast Bolt
        p0._script.append(True)   # yes, cast the Paradigm copy
        p0._script.append(False)  # decline to cast Bolt
        _resolve_top_of_stack(game)

        # Bolt should be exiled (original capstone stays exiled too)
        assert p0.zones[Zone.EXILE].contains(bolt)

    def test_paradigm_triggers_repeatedly(self) -> None:
        """The Paradigm trigger fires on each subsequent precombat main phase."""
        game = create_game()
        p0 = game.players[0]
        capstone = ImprovisationCapstone()
        p0.zones[Zone.LIBRARY]._objects.clear()

        self._cast_capstone(game, p0, capstone)

        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        game.active_player_index = 0

        # Fire twice — trigger should be present both times (recurring)
        for _ in range(2):
            game.trigger_manager.fire_event(game, BeginningOfPrecombatMainTriggeredEvent())
            p0._script.append(False)  # decline
            _resolve_top_of_stack(game)

        # Original capstone still in exile
        assert p0.zones[Zone.EXILE].contains(capstone)
