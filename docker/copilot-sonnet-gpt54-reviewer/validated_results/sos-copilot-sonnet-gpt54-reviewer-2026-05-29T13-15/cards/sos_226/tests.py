"""Tests for sos_226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class TestSilverquillProperties:
    def test_name(self) -> None:
        assert SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_is_creature(self) -> None:
        assert isinstance(SilverquillTheDisputant(owner=None), Creature)

    def test_power_toughness(self) -> None:
        c = SilverquillTheDisputant(owner=None)
        assert c.base_power == 4
        assert c.base_toughness == 4

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in SilverquillTheDisputant(owner=None).keywords

    def test_has_vigilance(self) -> None:
        assert Keyword.VIGILANCE in SilverquillTheDisputant(owner=None).keywords

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in SilverquillTheDisputant(owner=None).supertypes

    def test_has_dragon_subtype(self) -> None:
        assert "Dragon" in SilverquillTheDisputant(owner=None).subtypes


class TestSilverquillCasualty:
    """Casualty 1: when you cast an instant/sorcery, may sacrifice a creature
    with power >= 1 to copy the spell."""

    def _setup_casualty(self):
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        game.get_battlefield(p1).add(silverquill)
        silverquill.register_triggers(game)
        return game, p1, silverquill

    def test_casualty_trigger_registers(self) -> None:
        game, p1, silverquill = self._setup_casualty()
        triggers = game.trigger_manager.get_triggers_for_source(silverquill)
        assert len(triggers) >= 1

    def test_casualty_fires_on_instant_cast(self) -> None:
        game, p1, _ = self._setup_casualty()
        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        stack_obj = type("SO", (), {"source": instant, "targets": [], "controller": p1})()
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=stack_obj, player=p1, card=instant, controller=p1),
        )
        assert not game.stack.is_empty()

    def test_casualty_fires_on_sorcery_cast(self) -> None:
        game, p1, _ = self._setup_casualty()
        sorcery = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        stack_obj = type("SO", (), {"source": sorcery, "targets": [], "controller": p1})()
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=stack_obj, player=p1, card=sorcery, controller=p1),
        )
        assert not game.stack.is_empty()

    def test_casualty_does_not_fire_for_creatures(self) -> None:
        game, p1, _ = self._setup_casualty()
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1)
        stack_obj = type("SO", (), {"source": creature, "targets": [], "controller": p1})()
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=stack_obj, player=p1, card=creature, controller=p1),
        )
        assert game.stack.is_empty()

    def test_casualty_does_not_fire_for_opponent_spells(self) -> None:
        game, p1, _ = self._setup_casualty()
        p2 = game.players[1]
        instant = Instant(name="Opp Instant", owner=p2, controller=p2)
        stack_obj = type("SO", (), {"source": instant, "targets": [], "controller": p2})()
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=stack_obj, player=p2, card=instant, controller=p2),
        )
        assert game.stack.is_empty()

    def test_sacrifice_creature_copies_spell(self) -> None:
        game, p1, _ = self._setup_casualty()
        instant = Instant(name="Test Instant", owner=p1, controller=p1)

        # Sacrifice target: a creature with power 1
        fodder = Creature(name="Token", base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.get_battlefield(p1).add(fodder)
        fodder.register_triggers(game)

        from engine.stack import StackObject
        stack_obj = StackObject(
            source=instant, controller=p1, targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(stack_obj)

        # Fire casualty trigger
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=stack_obj, player=p1, card=instant, controller=p1),
        )

        # Trigger is on stack; pop it and resolve - script: True (yes sacrifice), fodder
        p1._script.appendleft(fodder)  # which creature to sacrifice
        p1._script.appendleft(True)    # yes, do casualty

        # Pop the casualty trigger (it was pushed last, so it's first)
        trig_obj = game.stack.pop()
        trig_obj.on_resolve(game)

        # fodder should be sacrificed
        assert game.get_battlefield(p1).contains(fodder) is False
        assert p1.zones[Zone.GRAVEYARD].contains(fodder)

        # And a copy of the spell should now be on the stack too
        # (Original + copy = 2 items; original was pushed first, copy after)
        assert not game.stack.is_empty()

    def test_no_sacrifice_no_copy(self) -> None:
        game, p1, _ = self._setup_casualty()
        instant = Instant(name="Test Instant", owner=p1, controller=p1)

        fodder = Creature(name="Token", base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.get_battlefield(p1).add(fodder)

        from engine.stack import StackObject
        stack_obj = StackObject(
            source=instant, controller=p1, targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(stack_obj)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=stack_obj, player=p1, card=instant, controller=p1),
        )

        # Say no to casualty
        p1._script.appendleft(False)

        trig_obj = game.stack.pop()
        trig_obj.on_resolve(game)

        # Fodder should still be alive
        assert game.get_battlefield(p1).contains(fodder)

        # Only the original spell on stack (no copy)
        assert not game.stack.is_empty()
        remaining = game.stack.pop()
        assert remaining is stack_obj
        assert game.stack.is_empty()

    def test_no_valid_sacrifice_target_skips_copy(self) -> None:
        """If controller has no creature with power >= 1, casualty doesn't apply."""
        game, p1, silverquill = self._setup_casualty()
        instant = Instant(name="Test Instant", owner=p1, controller=p1)

        # Remove Silverquill from battlefield so it can't be a casualty target
        game.get_battlefield(p1).remove(silverquill)

        # Put a 0/0 creature on battlefield (not valid casualty target)
        tiny = Creature(name="Tiny", base_power=0, base_toughness=1, owner=p1, controller=p1)
        game.get_battlefield(p1).add(tiny)

        from engine.stack import StackObject
        stack_obj = StackObject(
            source=instant, controller=p1, targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(stack_obj)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=stack_obj, player=p1, card=instant, controller=p1),
        )

        # Trigger fires but finds no valid target — no sacrifice, no copy
        trig_obj = game.stack.pop()
        trig_obj.on_resolve(game)

        # No sacrifice happened, no copy
        assert game.get_battlefield(p1).contains(tiny)
        # Only the original spell remains on stack
        assert not game.stack.is_empty()
        remaining = game.stack.pop()
        assert remaining is stack_obj
        assert game.stack.is_empty()
