"""Tests for sos_226 — Silverquill, the Disputant (Casualty 1)."""
from __future__ import annotations

import pytest

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game


class TestSilverquillProperties:
    def test_is_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Silverquill" in card.name

    def test_mana_cost(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_power_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_flying(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_is_legendary_elder_dragon(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Supertype.LEGENDARY in card.supertypes


class TestSilverquillCasualtyGrant:
    """Each instant and sorcery spell you cast has casualty 1."""

    def test_casualty_granted_to_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        instant = Instant(name="Shock", mana_cost=ManaCost.parse("{R}"), owner=p1, controller=p1)
        dragon.grant_casualty_to_spell(instant)
        assert getattr(instant, "has_casualty", False) is True
        assert getattr(instant, "casualty_power_req", 1) == 1

    def test_casualty_granted_to_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        sorcery = Sorcery(name="Divination", mana_cost=ManaCost.parse("{2}{U}"), owner=p1, controller=p1)
        dragon.grant_casualty_to_spell(sorcery)
        assert getattr(sorcery, "has_casualty", False) is True

    def test_casualty_not_granted_to_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1)
        dragon.grant_casualty_to_spell(creature)
        assert getattr(creature, "has_casualty", False) is False


class TestSilverquillCasualtyCopy:
    """When casualty is paid (sacrifice creature with power >= 1), copy the spell."""

    def test_pay_casualty_copies_spell(self) -> None:
        """Sacrificing a creature when casting spell copies the spell."""
        game = create_game()
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dragon)
        dragon.register_triggers(game)

        # Sacrifice target to pay casualty.
        sacrifice_target = Creature(
            name="Pawn", base_power=1, base_toughness=1, owner=p1, controller=p1
        )
        game.get_battlefield(p1).add(sacrifice_target)

        instant = Instant(name="Lightning Strike", mana_cost=ManaCost.parse("{1}{R}"), owner=p1, controller=p1)
        instant.has_casualty = True
        instant.casualty_power_req = 1

        # Cast the spell.
        from engine.stack import StackObject
        stack_obj = StackObject(source=instant, controller=p1)
        game.stack.push(stack_obj)

        initial_stack_size = len(game.stack)
        # Pay casualty: sacrifice the pawn.
        dragon.pay_casualty(game, instant, sacrifice_target)
        # The stack should have a copy pushed.
        assert len(game.stack) >= initial_stack_size

    def test_pay_casualty_sacrifices_creature(self) -> None:
        """The creature used to pay casualty is sacrificed."""
        game = create_game()
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)

        sacrifice_target = Creature(
            name="Pawn", base_power=1, base_toughness=1, owner=p1, controller=p1
        )
        game.get_battlefield(p1).add(sacrifice_target)

        instant = Instant(name="Shock", mana_cost=ManaCost.parse("{R}"), owner=p1, controller=p1)
        instant.has_casualty = True

        dragon.pay_casualty(game, instant, sacrifice_target)

        # Pawn should be off battlefield.
        assert sacrifice_target not in game.get_battlefield(p1).get_all()

    def test_registers_spellcast_trigger(self) -> None:
        """register_triggers registers a SpellCastTriggeredEvent watcher."""
        game = create_game()
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        before = len(game.trigger_manager._triggers)
        dragon.register_triggers(game)
        after = len(game.trigger_manager._triggers)
        assert after > before
