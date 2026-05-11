"""Audited tests for Negate (FDN collector number 710)."""

from __future__ import annotations

import pytest

from card_impl import Negate

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestNegateProperties:
    def test_is_instant(self):
        card = Negate()
        assert isinstance(card, Instant)

    def test_name(self):
        card = Negate()
        assert card.name == "Negate"

    def test_mana_cost(self):
        card = Negate()
        assert card.mana_cost == ManaCost.parse("{1}{U}")


@pytest.mark.ability
class TestNegateResolution:
    def test_cannot_cast_with_empty_stack(self):
        game = create_game()
        p1 = game.players[0]
        spell = Negate(owner=p1, controller=p1)
        assert not spell.can_cast(game)

    def test_can_cast_with_noncreature_spell_on_stack(self):
        """Negate can be cast when a noncreature spell is on the stack."""
        from engine.stack import StackObject
        game = create_game()
        p1, p2 = game.players
        target_spell = Sorcery(name="Divination", owner=p2, controller=p2)
        stack_obj = StackObject(source=target_spell, controller=p2)
        game.stack.push(stack_obj)
        negate = Negate(owner=p1, controller=p1)
        assert negate.can_cast(game)

    def test_cannot_cast_with_only_creature_spell_on_stack(self):
        """Negate cannot target creature spells."""
        from engine.stack import StackObject
        game = create_game()
        p1, p2 = game.players
        creature_spell = _make_creature(owner=p2, controller=p2)
        stack_obj = StackObject(source=creature_spell, controller=p2)
        game.stack.push(stack_obj)
        negate = Negate(owner=p1, controller=p1)
        assert not negate.can_cast(game)
