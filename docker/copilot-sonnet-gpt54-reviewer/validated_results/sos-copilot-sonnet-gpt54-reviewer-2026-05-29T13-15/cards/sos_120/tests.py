"""Tests for sos_120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Sorcery
from engine.types import ManaCost, Zone
from test_utils import create_game


class TestImprovisationCapstoneProperties:
    def test_name(self) -> None:
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_is_sorcery(self) -> None:
        assert isinstance(ImprovisationCapstone(owner=None), Sorcery)


class TestImprovisationCapstoneMainEffect:
    """Exile cards from top of library until total MV >= 4. Cast them for free."""

    def _setup_library(self, game, player, cards):
        for c in cards:
            player.zones[Zone.LIBRARY].add(c)

    def test_exiles_cards_until_mv_threshold(self) -> None:
        """Should exile cards until cumulative MV >= 4."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        # Cards: 2 mana, 2 mana, 3 mana (total: 7 mana when all exiled)
        c1 = Creature(name="C1", mana_cost=ManaCost.parse("{2}"), owner=p1)
        c2 = Creature(name="C2", mana_cost=ManaCost.parse("{2}"), owner=p1)
        c3 = Creature(name="C3", mana_cost=ManaCost.parse("{3}"), owner=p1)
        # Add from bottom: c1 at bottom, c3 at top
        self._setup_library(game, p1, [c1, c2, c3])

        initial_exile = len(p1.zones[Zone.EXILE].get_all())
        # Player declines to cast all (or no choices needed)
        for _ in range(3):
            p1._script.appendleft(False)  # decline each cast

        spell.on_resolve(game)

        exile_after = len(p1.zones[Zone.EXILE].get_all())
        # At least some cards were exiled
        assert exile_after > initial_exile

    def test_exiled_cards_can_be_cast_for_free(self) -> None:
        """Player may cast the exiled cards without paying their mana cost."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        instant = Instant(
            name="Free Instant",
            mana_cost=ManaCost.parse("{3}"),
            owner=p1, controller=p1,
        )
        dummy = Creature(
            name="Dummy",
            mana_cost=ManaCost.parse("{2}"),
            owner=p1, controller=p1,
        )
        self._setup_library(game, p1, [dummy, instant])  # instant is on top

        # Choose to cast the instant
        p1._script.appendleft(False)   # decline dummy
        p1._script.appendleft(True)    # cast instant

        spell.on_resolve(game)

        # The instant should no longer be in exile (was cast)
        exile = p1.zones[Zone.EXILE].get_all()
        assert instant not in exile

    def test_stops_when_mv_reaches_threshold(self) -> None:
        """Should stop exiling when total MV >= 4."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        # One card with MV 5 — should stop immediately after exiling it
        big = Creature(
            name="BigCard",
            mana_cost=ManaCost.parse("{5}"),
            owner=p1, controller=p1,
        )
        extra = Creature(
            name="ExtraCard",
            mana_cost=ManaCost.parse("{1}"),
            owner=p1, controller=p1,
        )
        self._setup_library(game, p1, [extra, big])  # big is on top

        # Decline to cast
        p1._script.appendleft(False)

        spell.on_resolve(game)

        # Only big card should be exiled (MV >= 4 reached after first card)
        exile = p1.zones[Zone.EXILE].get_all()
        lib = p1.zones[Zone.LIBRARY].get_all()
        assert big in exile
        # extra should still be in library (not exiled)
        assert extra in lib

    def test_empty_library_does_not_raise(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)  # should not raise with empty library


class TestImprovisationCapstoneParadigm:
    """Paradigm: spell goes to exile; registers a per-main-phase copy cast trigger."""

    def test_spell_moves_to_exile_after_on_resolve(self) -> None:
        """The spell itself should be moved to exile by on_resolve (not graveyard)."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        # Simulate: card is in stack zone when on_resolve is called
        p1.zones[Zone.STACK].add(spell)

        spell.on_resolve(game)

        # Should be in exile, not stack zone or graveyard
        assert p1.zones[Zone.EXILE].contains(spell)
        assert not p1.zones[Zone.STACK].contains(spell)
        assert not p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_paradigm_registers_main_phase_trigger(self) -> None:
        """After first resolution, a main phase trigger should be registered."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.STACK].add(spell)

        before = len(game.trigger_manager.get_triggers())
        spell.on_resolve(game)
        after = len(game.trigger_manager.get_triggers())

        assert after > before

    def test_paradigm_trigger_fires_at_main_phase(self) -> None:
        """The paradigm trigger fires at beginning of main phase."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.STACK].add(spell)
        spell.on_resolve(game)

        # Fire main phase event
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, is_precombat=True),
        )

        # A trigger effect should be on the stack
        assert not game.stack.is_empty()
