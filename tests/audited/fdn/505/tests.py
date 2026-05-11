"""Audited tests for Cancel (FDN collector number 505)."""

from __future__ import annotations

import pytest

from card_impl import Cancel

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment, CardImpl
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestCancelProperties:
    def test_is_instant(self):
        card = Cancel()
        assert isinstance(card, Instant)

    def test_name(self):
        card = Cancel()
        assert card.name == "Cancel"

    def test_mana_cost(self):
        card = Cancel()
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")


@pytest.mark.ability
class TestCancelResolution:
    def test_cannot_cast_with_empty_stack(self):
        game = create_game()
        p1 = game.players[0]
        spell = Cancel(owner=p1, controller=p1)
        assert not spell.can_cast(game)

    def test_can_cast_with_spell_on_stack(self):
        """Cancel can target any spell on the stack."""
        game = create_game()
        p1, p2 = game.players
        target_spell = Instant(name="Lightning Bolt", owner=p2, controller=p2)
        stack_obj = StackObject(source=target_spell, controller=p2)
        game.stack.push(stack_obj)
        spell = Cancel(owner=p1, controller=p1)
        assert spell.can_cast(game)

    def test_can_cast_with_creature_spell_on_stack(self):
        """Cancel can also target creature spells (it counters any spell)."""
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(name="Bear", owner=p2, controller=p2)
        stack_obj = StackObject(source=creature, controller=p2)
        game.stack.push(stack_obj)
        spell = Cancel(owner=p1, controller=p1)
        assert spell.can_cast(game)

    def test_counters_target_spell(self):
        """Resolving Cancel removes the target spell from the stack."""
        game = create_game()
        p1, p2 = game.players
        target_spell = Instant(name="Lightning Bolt", owner=p2, controller=p2)
        stack_obj = StackObject(source=target_spell, controller=p2)
        game.stack.push(stack_obj)
        spell = Cancel(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)
        remaining = [o for o in game.stack.objects() if o.source is target_spell]
        assert len(remaining) == 0

    def test_countered_spell_goes_to_graveyard(self):
        """The countered spell's card should be placed in its owner's graveyard."""
        game = create_game()
        p1, p2 = game.players
        target_spell = Instant(name="Lightning Bolt", owner=p2, controller=p2)
        stack_obj = StackObject(source=target_spell, controller=p2)
        game.stack.push(stack_obj)
        spell = Cancel(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)
        gy = list(p2.zones[Zone.GRAVEYARD].get_all())
        assert target_spell in gy

    def test_fizzle_when_target_gone(self):
        """If the target spell is no longer on the stack, Cancel fizzles harmlessly."""
        game = create_game()
        p1, p2 = game.players
        target_spell = Instant(name="Lightning Bolt", owner=p2, controller=p2)
        stack_obj = StackObject(source=target_spell, controller=p2)
        # Don't push to stack — target has left
        spell = Cancel(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        initial_stack_len = len(game.stack)
        p2_gy_before = list(p2.zones[Zone.GRAVEYARD].get_all())
        p1_gy_before = list(p1.zones[Zone.GRAVEYARD].get_all())
        spell.on_resolve(game)
        # Stack unchanged
        assert len(game.stack) == initial_stack_len
        # Target spell card must NOT be moved to any graveyard
        p2_gy_after = list(p2.zones[Zone.GRAVEYARD].get_all())
        p1_gy_after = list(p1.zones[Zone.GRAVEYARD].get_all())
        assert target_spell not in p2_gy_after, "Fizzled counterspell must not move target to graveyard"
        assert target_spell not in p1_gy_after
        # Graveyards unchanged
        assert len(p2_gy_after) == len(p2_gy_before)
        assert len(p1_gy_after) == len(p1_gy_before)
