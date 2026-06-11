"""Tests for Improvisation Capstone (sos_120)."""

import pytest
from test_utils import create_game, set_board_state
from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import _resolve_top_of_stack


def _sorcery_speed(game, player_idx=0):
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = player_idx


class TestImprovisationCapstone:
    def test_exiles_until_mv_4(self):
        """Exiles cards until total MV >= 4."""
        game = create_game()
        p1 = game.players[0]

        # Library (top = last added): mv1 + mv1 + mv3 = mv5 >= 4 → stop after 3
        c1 = Instant(name="One", mana_cost=ManaCost.parse("{R}"))       # mv 1
        c2 = Instant(name="Two", mana_cost=ManaCost.parse("{U}"))       # mv 1
        c3 = Sorcery(name="Three", mana_cost=ManaCost.parse("{2}{G}"))  # mv 3
        c4 = Instant(name="Four", mana_cost=ManaCost.parse("{G}"))      # mv 1 (should NOT be exiled)
        for card in [c4, c3, c2, c1]:  # c1 on top
            c_ref = card
            c_ref.owner = p1
            p1.zones[Zone.LIBRARY].add(c_ref)
        # Library bottom→top: c4, c3, c2, c1 → top is c1

        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone], mana={ManaType.RED: 10, ManaType.COLORLESS: 10})
        _sorcery_speed(game)

        # Decline casting all exiled cards
        for _ in range(3):
            p1._script.appendleft(False)

        from engine.casting import cast_spell
        cast_spell(game, p1, capstone)
        _resolve_top_of_stack(game)

        exile = p1.zones[Zone.EXILE].get_all()
        # c1, c2, c3 should be exiled; c4 should remain in library
        assert c1 in exile
        assert c2 in exile
        assert c3 in exile
        assert c4 not in exile
        # Library still has c4
        assert c4 in p1.zones[Zone.LIBRARY].get_all()

    def test_can_cast_exiled_spells_free(self):
        """Player may cast exiled spells without paying mana costs."""
        game = create_game()
        p1 = game.players[0]

        target_instant = Instant(name="FreeSpell", mana_cost=ManaCost.parse("{5}{R}{R}"))
        target_instant.owner = p1
        p1.zones[Zone.LIBRARY].add(target_instant)  # only card in library

        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone], mana={ManaType.RED: 10, ManaType.COLORLESS: 10})
        _sorcery_speed(game)

        # Only 1 card (mv 7 >= 4), say yes to cast it
        p1._script.appendleft(True)  # cast the instant

        from engine.casting import cast_spell
        cast_spell(game, p1, capstone)
        _resolve_top_of_stack(game)

        # The free spell was cast and resolved (it's an instant, goes to graveyard).
        # Verify it left the library and exile (was cast), ending in graveyard.
        assert target_instant not in p1.zones[Zone.LIBRARY].get_all()
        assert target_instant not in p1.zones[Zone.EXILE].get_all()
        assert target_instant in p1.zones[Zone.GRAVEYARD].get_all()

    def test_paradigm_exiles_capstone(self):
        """Capstone exiles itself (not graveyard) after resolving."""
        game = create_game()
        p1 = game.players[0]

        # Empty library — no cards to exile
        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone], mana={ManaType.RED: 10, ManaType.COLORLESS: 10})
        _sorcery_speed(game)

        from engine.casting import cast_spell
        cast_spell(game, p1, capstone)
        _resolve_top_of_stack(game)

        # Capstone should be in exile, not graveyard
        assert capstone in p1.zones[Zone.EXILE].get_all()
        assert capstone not in p1.zones[Zone.GRAVEYARD].get_all()

    def test_paradigm_trigger_registered_once(self):
        """Paradigm trigger is registered once for the controller."""
        game = create_game()
        p1 = game.players[0]

        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone], mana={ManaType.RED: 10, ManaType.COLORLESS: 10})
        _sorcery_speed(game)

        from engine.casting import cast_spell
        cast_spell(game, p1, capstone)
        _resolve_top_of_stack(game)

        triggers = game.trigger_manager.get_triggers_for_source(capstone)
        assert len(triggers) == 1

    def test_paradigm_copy_cast_at_main_phase(self):
        """At beginning of each main phase, a copy can be cast from exile."""
        game = create_game()
        p1 = game.players[0]

        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone], mana={ManaType.RED: 10, ManaType.COLORLESS: 10})
        _sorcery_speed(game)

        from engine.casting import cast_spell
        cast_spell(game, p1, capstone)
        _resolve_top_of_stack(game)  # capstone resolves, trigger registered

        # Clear library for clean test
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        game.active_player_index = 0

        # Decline casting the copy
        p1._script.appendleft(False)
        game.trigger_manager.fire_event(game, BeginningOfPrecombatMainTriggeredEvent())
        _resolve_top_of_stack(game)  # Paradigm trigger resolves, offers copy

        # The copy was placed in exile (even if we declined casting)
        exile_cards = p1.zones[Zone.EXILE].get_all()
        # capstone itself + copy in exile
        assert len([c for c in exile_cards if isinstance(c, ImprovisationCapstone)]) >= 2
