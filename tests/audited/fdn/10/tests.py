"""Audited tests for Divine Resilience (FDN collector number 10)."""

from __future__ import annotations

import pytest

from card_impl import DivineResilience

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestDivineResilienceProperties:
    def test_is_instant(self):
        card = DivineResilience()
        assert isinstance(card, Instant)

    def test_name(self):
        card = DivineResilience()
        assert card.name == "Divine Resilience"

    def test_mana_cost(self):
        card = DivineResilience()
        assert card.mana_cost == ManaCost.parse("{W}")


@pytest.mark.ability
class TestDivineResilienceResolution:
    def test_grants_indestructible(self):
        """Target creature gains indestructible until end of turn."""
        from engine.types import Keyword
        game = create_game()
        p1 = game.players[0]
        creature = _make_creature(name="Bear", power=2, toughness=2, owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[creature])
        spell = DivineResilience(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.INDESTRUCTIBLE & creature.keywords


@pytest.mark.edge
class TestDivineResilienceEdge:
    def test_no_target_state_unchanged(self):
        """Empty targets list: state should remain unchanged."""
        game = create_game()
        p1 = game.players[0]
        initial_life = p1.life
        initial_bf = len(list(game.get_battlefield(p1).get_all()))
        spell = DivineResilience(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)
        assert p1.life == initial_life
        assert len(list(game.get_battlefield(p1).get_all())) == initial_bf

    def test_target_left_battlefield_fizzles(self):
        """If target is no longer on battlefield, spell does nothing and state unchanged."""
        game = create_game()
        p1 = game.players[0]
        creature = _make_creature(name="Bear", power=2, toughness=2, owner=p1, controller=p1)
        # Don't put creature on battlefield — simulates it leaving
        initial_life = p1.life
        initial_bf = len(list(game.get_battlefield(p1).get_all()))
        spell = DivineResilience(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        assert p1.life == initial_life
        assert len(list(game.get_battlefield(p1).get_all())) == initial_bf
