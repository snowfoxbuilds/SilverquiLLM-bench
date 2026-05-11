"""Audited tests for Valorous Stance (FDN collector number 583)."""

from __future__ import annotations

import pytest

from card_impl import ValorousStance

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestValorousStanceProperties:
    def test_is_instant(self):
        card = ValorousStance()
        assert isinstance(card, Instant)

    def test_name(self):
        card = ValorousStance()
        assert card.name == "Valorous Stance"


@pytest.mark.ability
class TestValorousStanceResolution:
    def test_mode_0_grants_indestructible(self):
        """Mode 0: Target creature gains indestructible until end of turn."""
        from engine.types import Keyword
        game = create_game()
        p1 = game.players[0]
        creature = _make_creature(name="Bear", power=2, toughness=2, owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[creature])
        spell = ValorousStance(owner=p1, controller=p1)
        spell.chosen_mode = 0
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        assert Keyword.INDESTRUCTIBLE & creature.keywords

    def test_mode_1_destroys_creature_toughness_4_plus(self):
        game = create_game()
        p1, p2 = game.players
        big = _make_creature(name="Big", power=5, toughness=5, owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[big])
        spell = ValorousStance(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.chosen_targets = [big]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        assert big not in bf

    def test_mode_1_does_not_destroy_small_creature(self):
        """Mode 1 should not destroy a creature with toughness < 4."""
        game = create_game()
        p1, p2 = game.players
        small = _make_creature(name="Small", power=1, toughness=3, owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[small])
        spell = ValorousStance(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.chosen_targets = [small]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        assert small in bf


@pytest.mark.edge
class TestValorousStanceEdge:
    def test_no_mode_no_crash(self):
        game = create_game()
        spell = ValorousStance(owner=game.players[0], controller=game.players[0])
        spell.chosen_mode = None
        spell.on_resolve(game)
