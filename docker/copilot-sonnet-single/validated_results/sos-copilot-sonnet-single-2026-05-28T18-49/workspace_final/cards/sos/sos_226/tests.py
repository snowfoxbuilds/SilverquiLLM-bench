"""Tests for Silverquill, the Disputant (sos_226)."""

from __future__ import annotations

import pytest
from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class TestSilverquillProperties:
    """Static card properties."""

    def test_name(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"

    def test_is_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert isinstance(card, Creature)

    def test_power_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_mana_cost(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_has_flying(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING & card.keywords

    def test_has_vigilance(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.VIGILANCE & card.keywords

    def test_is_legendary(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


class TestSilverquillCasualtyTrigger:
    """Casualty 1: may sacrifice a creature with power >= 1 to copy spell."""

    def _get_casualty_trigger(self, game, card):
        from engine.events import SpellCastTriggeredEvent
        for t in game.trigger_manager.get_triggers_for_source(card):
            if t.event_type is SpellCastTriggeredEvent:
                return t
        return None

    def test_casualty_trigger_registered(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_casualty_trigger(game, card)
        assert trigger is not None

    def test_casualty_condition_fires_for_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        silverquill.register_triggers(game)

        from engine.events import SpellCastTriggeredEvent
        spell = Instant(name="Shock", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=spell, player=p1, controller=p1)

        trigger = self._get_casualty_trigger(game, silverquill)
        assert trigger.condition(game, event) is True

    def test_casualty_condition_fires_for_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        silverquill.register_triggers(game)

        from engine.events import SpellCastTriggeredEvent
        spell = Sorcery(name="Divination", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=spell, player=p1, controller=p1)

        trigger = self._get_casualty_trigger(game, silverquill)
        assert trigger.condition(game, event) is True

    def test_casualty_condition_does_not_fire_for_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        silverquill.register_triggers(game)

        from engine.events import SpellCastTriggeredEvent
        creature_card = Creature(name="Bear", base_power=2, base_toughness=2)
        event = SpellCastTriggeredEvent(spell=creature_card, player=p1, controller=p1)

        trigger = self._get_casualty_trigger(game, silverquill)
        assert trigger.condition(game, event) is False

    def test_casualty_condition_does_not_fire_for_opponent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        silverquill.register_triggers(game)

        from engine.events import SpellCastTriggeredEvent
        spell = Instant(name="Shock", owner=p2, controller=p2)
        event = SpellCastTriggeredEvent(spell=spell, player=p2, controller=p2)

        trigger = self._get_casualty_trigger(game, silverquill)
        assert trigger.condition(game, event) is False

    def test_casualty_copies_spell_when_sacrificed(self) -> None:
        """If player sacrifices a creature, the spell gets a copy on the stack."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(name="Token", base_power=1, base_toughness=1,
                          owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill, fodder])
        silverquill.register_triggers(game)

        # Push a spell onto the stack
        from engine.stack import StackObject
        from engine.card import Instant
        spell = Instant(name="Shock", owner=p1, controller=p1)
        p1.zones[Zone.STACK].add(spell)
        sobj = StackObject(source=spell, controller=p1)
        game.stack.push(sobj)

        # Script: yes to casualty, choose fodder
        p1._script.append(True)    # yes, use casualty
        p1._script.append(fodder)  # sacrifice this

        trigger = self._get_casualty_trigger(game, silverquill)
        trigger.effect(game)

        # Fodder was sacrificed
        assert not game.get_battlefield(p1).contains(fodder)
        # A copy is on the stack
        assert len(game.stack) >= 2

    def test_casualty_not_used_when_declined(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(name="Token", base_power=1, base_toughness=1,
                          owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill, fodder])
        silverquill.register_triggers(game)

        from engine.stack import StackObject
        spell = Instant(name="Shock", owner=p1, controller=p1)
        p1.zones[Zone.STACK].add(spell)
        sobj = StackObject(source=spell, controller=p1)
        game.stack.push(sobj)

        # Script: no to casualty
        p1._script.append(False)

        trigger = self._get_casualty_trigger(game, silverquill)
        trigger.effect(game)

        # Fodder not sacrificed
        assert game.get_battlefield(p1).contains(fodder)
        # Only original spell on stack
        assert len(game.stack) == 1
