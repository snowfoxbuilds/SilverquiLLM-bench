"""Audited tests for Antiquities on the Loose (FDN collector number 7).

Collector number 7 is shared with Crystal Barricade (artifacts_batch2).
A conftest override maps directory '7' to AntiquitiesOnTheLoose for this batch.
"""

from __future__ import annotations

import pytest

from card_impl import AntiquitiesOnTheLoose

from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestAntiquitiesOnTheLooseProperties:
    def test_is_sorcery(self):
        card = AntiquitiesOnTheLoose()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = AntiquitiesOnTheLoose()
        assert card.name == "Antiquities on the Loose"

    def test_mana_cost(self):
        card = AntiquitiesOnTheLoose()
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")


@pytest.mark.ability
class TestAntiquitiesOnTheLooseResolution:
    def test_creates_two_spirit_tokens(self):
        """Resolution creates two 2/2 Spirit creature tokens."""
        game = create_game()
        p1 = game.players[0]
        spell = AntiquitiesOnTheLoose(owner=p1, controller=p1)
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        spirits = [c for c in bf if getattr(c, "name", "") == "Spirit"]
        assert len(spirits) == 2

    def test_spirit_tokens_are_2_2(self):
        """Each Spirit token should be a 2/2."""
        game = create_game()
        p1 = game.players[0]
        spell = AntiquitiesOnTheLoose(owner=p1, controller=p1)
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        spirits = [c for c in bf if getattr(c, "name", "") == "Spirit"]
        for spirit in spirits:
            assert spirit.base_power == 2
            assert spirit.base_toughness == 2

    def test_spirit_tokens_are_creatures(self):
        """Spirit tokens should be creature type."""
        game = create_game()
        p1 = game.players[0]
        spell = AntiquitiesOnTheLoose(owner=p1, controller=p1)
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        spirits = [c for c in bf if getattr(c, "name", "") == "Spirit"]
        assert len(spirits) > 0
        for spirit in spirits:
            assert CardType.CREATURE in spirit.card_types


@pytest.mark.edge
class TestAntiquitiesOnTheLooseEdge:
    def test_no_controller_does_nothing(self):
        """If controller is None, resolution does not crash or change state."""
        game = create_game()
        p1 = game.players[0]
        initial_bf_count = len(list(game.get_battlefield(p1).get_all()))
        spell = AntiquitiesOnTheLoose(owner=p1)
        spell.controller = None
        spell.on_resolve(game)
        final_bf_count = len(list(game.get_battlefield(p1).get_all()))
        assert final_bf_count == initial_bf_count
