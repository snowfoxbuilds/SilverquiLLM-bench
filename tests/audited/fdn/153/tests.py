"""Audited tests for Essence Scatter (FDN collector number 153)."""

from __future__ import annotations

import pytest

from card_impl import EssenceScatter

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment, CardImpl
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestEssenceScatterProperties:
    def test_is_instant(self):
        card = EssenceScatter()
        assert isinstance(card, Instant)

    def test_name(self):
        card = EssenceScatter()
        assert card.name == "Essence Scatter"

    def test_mana_cost(self):
        card = EssenceScatter()
        assert card.mana_cost == ManaCost.parse("{1}{U}")


@pytest.mark.ability
class TestEssenceScatterResolution:
    def test_can_cast_with_creature_spell_on_stack(self):
        """Can cast when a creature spell is on the stack."""
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(name="Bear", owner=p2, controller=p2)
        stack_obj = StackObject(source=creature, controller=p2)
        game.stack.push(stack_obj)
        spell = EssenceScatter(owner=p1, controller=p1)
        assert spell.can_cast(game)

    def test_cannot_cast_with_empty_stack(self):
        """Cannot cast when no spells are on the stack."""
        game = create_game()
        p1 = game.players[0]
        spell = EssenceScatter(owner=p1, controller=p1)
        assert not spell.can_cast(game)

    def test_cannot_cast_with_only_noncreature_on_stack(self):
        """Cannot cast when only noncreature spells are on the stack."""
        game = create_game()
        p1, p2 = game.players
        noncreature = Instant(name="Lightning Bolt", owner=p2, controller=p2)
        stack_obj = StackObject(source=noncreature, controller=p2)
        game.stack.push(stack_obj)
        spell = EssenceScatter(owner=p1, controller=p1)
        assert not spell.can_cast(game)

    def test_counters_creature_spell(self):
        """Resolving Essence Scatter should counter (remove from stack) the target creature spell."""
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(name="Bear", owner=p2, controller=p2)
        stack_obj = StackObject(source=creature, controller=p2)
        game.stack.push(stack_obj)
        spell = EssenceScatter(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)
        # Stack should no longer contain the creature spell
        remaining = [o for o in game.stack.objects() if o.source is creature]
        assert len(remaining) == 0

    def test_countered_spell_goes_to_graveyard(self):
        """The countered creature spell's card should move to its owner's graveyard."""
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(name="Bear", owner=p2, controller=p2)
        stack_obj = StackObject(source=creature, controller=p2)
        game.stack.push(stack_obj)
        spell = EssenceScatter(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)
        gy = list(p2.zones[Zone.GRAVEYARD].get_all())
        assert creature in gy

    def test_fizzle_when_target_gone(self):
        """If the target creature spell is no longer on the stack, Essence Scatter fizzles."""
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(name="Bear", owner=p2, controller=p2)
        stack_obj = StackObject(source=creature, controller=p2)
        # Don't push to stack — simulates target leaving
        spell = EssenceScatter(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        initial_stack_len = len(game.stack)
        p2_gy_before = list(p2.zones[Zone.GRAVEYARD].get_all())
        p1_gy_before = list(p1.zones[Zone.GRAVEYARD].get_all())
        spell.on_resolve(game)
        # Stack should be unchanged
        assert len(game.stack) == initial_stack_len
        # Target creature card must NOT be moved to any graveyard
        p2_gy_after = list(p2.zones[Zone.GRAVEYARD].get_all())
        p1_gy_after = list(p1.zones[Zone.GRAVEYARD].get_all())
        assert creature not in p2_gy_after, "Fizzled counterspell must not move target to graveyard"
        assert creature not in p1_gy_after
        # Graveyards unchanged
        assert len(p2_gy_after) == len(p2_gy_before)
        assert len(p1_gy_after) == len(p1_gy_before)
