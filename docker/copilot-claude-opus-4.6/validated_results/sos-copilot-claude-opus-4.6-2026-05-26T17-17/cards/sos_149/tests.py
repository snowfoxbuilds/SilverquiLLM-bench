"""Tests for SOS 149 — Germination Practicum."""

from __future__ import annotations

import pytest

from cards.sos.sos_149.card_impl import GerminationPracticum
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestGerminationPracticumProperties:
    """Static card data should match the SOS 149 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(GerminationPracticum(owner=None), Sorcery)

    def test_name(self) -> None:
        assert GerminationPracticum(owner=None).name == "Germination Practicum"

    def test_mana_cost(self) -> None:
        assert GerminationPracticum(owner=None).mana_cost == ManaCost.parse("{3}{G}{G}")


class TestGerminationPracticumResolution:
    """Put two +1/+1 counters on each creature you control."""

    def test_adds_two_counters_to_each_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear1 = Creature(name="Bear1", owner=p1, controller=p1,
                         base_power=2, base_toughness=2)
        bear1.card_types = {CardType.CREATURE}
        bear1.plus_one_counters = 0
        bear2 = Creature(name="Bear2", owner=p1, controller=p1,
                         base_power=3, base_toughness=3)
        bear2.card_types = {CardType.CREATURE}
        bear2.plus_one_counters = 0
        game.get_battlefield(p1).add(bear1)
        game.get_battlefield(p1).add(bear2)
        spell = GerminationPracticum(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert bear1.plus_one_counters == 2
        assert bear2.plus_one_counters == 2

    def test_does_not_affect_opponent_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        my_bear = Creature(name="MyBear", owner=p1, controller=p1,
                           base_power=2, base_toughness=2)
        my_bear.card_types = {CardType.CREATURE}
        my_bear.plus_one_counters = 0
        opp_bear = Creature(name="OppBear", owner=p2, controller=p2,
                            base_power=2, base_toughness=2)
        opp_bear.card_types = {CardType.CREATURE}
        opp_bear.plus_one_counters = 0
        game.get_battlefield(p1).add(my_bear)
        game.get_battlefield(p2).add(opp_bear)
        spell = GerminationPracticum(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert my_bear.plus_one_counters == 2
        assert opp_bear.plus_one_counters == 0

    def test_no_creatures_is_noop(self) -> None:
        """With no creatures on battlefield, resolution does not error."""
        game = create_game()
        p1 = game.players[0]
        spell = GerminationPracticum(owner=p1, controller=p1)
        spell.on_resolve(game)  # Should not raise


class TestGerminationPracticumParadigm:
    """Paradigm: exile after resolve, cast copy from exile on subsequent turns."""

    def test_spell_exiled_after_resolution(self) -> None:
        """After resolving, the spell should be exiled (not graveyard)."""
        game = create_game()
        p1 = game.players[0]
        spell = GerminationPracticum(owner=p1, controller=p1)
        spell.on_resolve(game)
        exile = game.get_exile(p1)
        assert any(c.name == "Germination Practicum" for c in exile)

    def test_paradigm_triggers_on_second_cast(self) -> None:
        """After first resolve, paradigm allows free copy at main phase."""
        game = create_game()
        p1 = game.players[0]
        # First resolution
        spell = GerminationPracticum(owner=p1, controller=p1)
        spell.on_resolve(game)
        # The paradigm should be registered for future main phases
        assert p1.paradigm_active("Germination Practicum") is True
