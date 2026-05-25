"""Audited tests for FDN 48 — Refute."""

from __future__ import annotations

from card_impl import Refute
from engine.card import Creature, Instant
from engine.stack import StackObject
from engine.types import ManaCost, Zone
from test_utils import create_game


class TestRefuteBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = Refute(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = Refute(owner=None)
        assert card.name == "Refute"

    def test_mana_cost(self) -> None:
        card = Refute(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")


class TestRefuteResolve:
    """Counter target spell, then loot (draw a card, discard a card)."""

    def test_counters_target_spell(self) -> None:
        """Refute removes the targeted spell from the stack."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = Refute(owner=p1, controller=p1)
        # Put a target spell on the stack
        target_spell = Instant(name="TargetSpell", owner=p2, controller=p2)
        stack_obj = StackObject(source=target_spell, controller=p2)
        game.stack.push(stack_obj)
        p2.zones[Zone.STACK].add(target_spell)
        card.chosen_targets = [stack_obj]
        # Add library cards for loot
        for i in range(3):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        card.on_resolve(game)
        # Targeted spell should be removed from stack (countered → graveyard)
        assert not game.stack.contains(stack_obj) if hasattr(game.stack, 'contains') else len(game.stack) == 0

    def test_loots_after_countering(self) -> None:
        """After countering, draws one card then discards one (net 0 hand change)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = Refute(owner=p1, controller=p1)
        target_spell = Instant(name="TargetSpell", owner=p2, controller=p2)
        stack_obj = StackObject(source=target_spell, controller=p2)
        game.stack.push(stack_obj)
        p2.zones[Zone.STACK].add(target_spell)
        card.chosen_targets = [stack_obj]
        for i in range(3):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        card.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        # Draws 1, discards 1 → net 0
        assert hand_after - hand_before == 0

    def test_discards_a_card_on_resolve(self) -> None:
        """Loot effect sends a card to the graveyard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = Refute(owner=p1, controller=p1)
        target_spell = Instant(name="TargetSpell", owner=p2, controller=p2)
        stack_obj = StackObject(source=target_spell, controller=p2)
        game.stack.push(stack_obj)
        p2.zones[Zone.STACK].add(target_spell)
        card.chosen_targets = [stack_obj]
        for i in range(3):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        card.on_resolve(game)
        gy_cards = list(p1.zones[Zone.GRAVEYARD].get_all())
        assert len(gy_cards) == 1

    def test_fizzles_when_target_is_none(self) -> None:
        """Single-target spell fizzles entirely when target is illegal (None)."""
        game = create_game()
        p1 = game.players[0]
        card = Refute(owner=p1, controller=p1)
        card.chosen_targets = [None]
        for i in range(3):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        card.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        # Spell fizzled — no draw, no discard
        assert hand_after == hand_before

    def test_fizzles_no_graveyard_change(self) -> None:
        """Fizzled Refute should not put anything in the graveyard (no loot)."""
        game = create_game()
        p1 = game.players[0]
        card = Refute(owner=p1, controller=p1)
        card.chosen_targets = [None]
        for i in range(3):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        card.on_resolve(game)
        gy_cards = list(p1.zones[Zone.GRAVEYARD].get_all())
        assert len(gy_cards) == 0


class TestRefuteCanCast:
    """Can only cast when there's a spell on the stack."""

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = Refute(owner=p1, controller=p1)
        assert card.can_cast(game) is False
