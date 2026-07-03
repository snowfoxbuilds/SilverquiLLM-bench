"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast_spell
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import TestSetupError as SetupError
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state


def _counter_bear(game, *, p0_extra_battlefield=None):
    """P1 casts a {1}{G} bear; P0 counters it with Mana Sculpt."""
    p0, p1 = game.players

    bear = Creature(
        name="Bear", base_power=2, base_toughness=2,
        mana_cost=ManaCost.parse("{1}{G}"),
    )
    set_board_state(
        game, 1, hand=[bear],
        mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
    )
    set_board_state(
        game, 0,
        battlefield=p0_extra_battlefield or [],
        hand=[ManaSculpt(owner=None)],
        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
    )

    # P1 is the active player casting at sorcery speed.
    game.active_player_index = 1
    game._normal_next_index = 0
    game.priority_player_index = 1
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    engine_cast_spell(game, p1, bear)
    bear_so = game.stack.peek()

    sculpt = next(c for c in p0.zones[Zone.HAND].get_all() if c.name == "Mana Sculpt")
    p0._script.appendleft(bear_so)
    engine_cast_spell(game, p0, sculpt)

    # Resolve: p1 pass, p0 pass -> Mana Sculpt resolves and counters.
    p1._script.append("pass")
    p0._script.append("pass")
    priority_loop(game)
    return bear


class TestManaSculptProperties:
    def test_static_data(self) -> None:
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        set_board_state(
            game, 0, hand=[ManaSculpt(owner=None)],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        with pytest.raises(SetupError):
            cast_spell(game, 0, "Mana Sculpt")


class TestCounter:
    def test_counters_target_spell(self) -> None:
        game = create_game()
        bear = _counter_bear(game)
        p0, p1 = game.players
        assert bear in p1.zones[Zone.GRAVEYARD].get_all()
        assert bear not in p1.zones[Zone.BATTLEFIELD].get_all()
        assert game.stack.is_empty()
        gy0_names = [c.name for c in p0.zones[Zone.GRAVEYARD].get_all()]
        assert "Mana Sculpt" in gy0_names


class TestDelayedMana:
    def test_wizard_grants_colorless_at_next_main(self) -> None:
        game = create_game()
        wizard = Creature(name="Wiz", base_power=1, base_toughness=1,
                          subtypes={"Wizard"})
        _counter_bear(game, p0_extra_battlefield=[wizard])
        p0 = game.players[0]

        # Advance to P0's precombat main (next turn).
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p0
        for p in game.players:
            p._script.append("pass")
        priority_loop(game)
        # Bear cost {1}{G} -> 2 mana were spent on it.
        assert p0.mana_pool.get(ManaType.COLORLESS) == 2

    def test_no_wizard_no_mana(self) -> None:
        game = create_game()
        _counter_bear(game)
        p0 = game.players[0]
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p0
        for p in game.players:
            p._script.append("pass")
        priority_loop(game)
        assert p0.mana_pool.total() == 0

    def test_one_shot_does_not_repeat_next_turn(self) -> None:
        game = create_game()
        wizard = Creature(name="Wiz", base_power=1, base_toughness=1,
                          subtypes={"Wizard"})
        _counter_bear(game, p0_extra_battlefield=[wizard])
        p0 = game.players[0]
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        for p in game.players:
            p._script.append("pass")
        priority_loop(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 2

        # Two turns later (P0 active again): nothing more is added.
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p0
        priority_loop(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0  # pools emptied each phase

    def test_wizard_checked_when_trigger_fires(self) -> None:
        # No Wizard when the spell is countered, but one arrives before
        # the next main phase: the mana IS added (fire-time check).
        game = create_game()
        _counter_bear(game)
        p0 = game.players[0]
        wizard = Creature(name="LateWiz", base_power=1, base_toughness=1,
                          subtypes={"Wizard"})
        set_board_state(game, 0, battlefield=[wizard])
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        for p in game.players:
            p._script.append("pass")
        priority_loop(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 2
