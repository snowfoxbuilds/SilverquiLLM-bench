"""Tests for SOS 153 — Lumaret's Favor.

Instant for {1}{G}. Target creature gets +2/+4 until end of turn.
Infusion — When you cast this spell, copy it if you gained life this turn.
You may choose new targets for the copy.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_153.card_impl import LumaretsFavor
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestLumaretsFavorProperties:
    """Static card data should match the SOS 153 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(LumaretsFavor(owner=None), Instant)

    def test_name(self) -> None:
        assert LumaretsFavor(owner=None).name == "Lumaret's Favor"

    def test_mana_cost(self) -> None:
        assert LumaretsFavor(owner=None).mana_cost == ManaCost.parse("{1}{G}")


class TestLumaretsFavorTargeting:
    """The spell targets a creature."""

    def test_returns_target_requirement(self) -> None:
        game = create_game()
        reqs = LumaretsFavor(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = LumaretsFavor(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD


class TestLumaretsFavorResolution:
    """On resolve, target creature gets +2/+4 until end of turn."""

    def test_grants_plus_2_plus_4(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)

        spell = LumaretsFavor(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert bear.power == 4  # 2 + 2
        assert bear.toughness == 6  # 2 + 4

    def test_no_target_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = LumaretsFavor(owner=p1, controller=p1)
        spell.on_resolve(game)  # should not raise


class TestLumaretsFavorInfusion:
    """Infusion copies the spell if life was gained this turn."""

    def test_copies_when_life_gained(self) -> None:
        """If controller gained life this turn, the spell should be copied."""
        game = create_game()
        p1 = game.players[0]
        p1.life_gained_this_turn = 3

        spell = LumaretsFavor(owner=p1, controller=p1)
        result = spell.on_cast_trigger(game)
        # Should produce a copy
        assert result is not None
        assert result.copy_spell is True

    def test_no_copy_when_no_life_gained(self) -> None:
        """If controller has not gained life this turn, no copy."""
        game = create_game()
        p1 = game.players[0]
        p1.life_gained_this_turn = 0

        spell = LumaretsFavor(owner=p1, controller=p1)
        result = spell.on_cast_trigger(game)
        assert result is None or result.copy_spell is False
