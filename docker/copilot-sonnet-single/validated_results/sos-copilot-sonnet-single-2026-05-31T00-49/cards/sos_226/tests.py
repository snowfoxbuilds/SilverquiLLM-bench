"""Tests for sos_226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class TestSilverquillProperties:
    def test_name(self) -> None:
        assert SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_is_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_legendary(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

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


class TestSilverquillTriggerRegistration:
    def test_register_triggers_adds_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after - before == 1

    def test_trigger_watches_spell_cast_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert triggers[0].event_type is SpellCastTriggeredEvent


class TestSilverquillCasualtyCondition:
    """Trigger condition: fires for instant/sorcery spells cast by controller."""

    def _get_condition(self, game, card):
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        return triggers[0].condition

    def test_condition_true_for_instant_by_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        condition = self._get_condition(game, card)
        spell = Instant(name="Bolt", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=spell, controller=p1)
        assert condition(game, event) is True

    def test_condition_true_for_sorcery_by_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        condition = self._get_condition(game, card)
        spell = Sorcery(name="Ramp", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=spell, controller=p1)
        assert condition(game, event) is True

    def test_condition_false_for_opponent_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        condition = self._get_condition(game, card)
        spell = Instant(name="Bolt", owner=p2, controller=p2)
        event = SpellCastTriggeredEvent(spell=spell, controller=p2)
        assert condition(game, event) is False

    def test_condition_false_for_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        condition = self._get_condition(game, card)
        creature_spell = Creature(name="Bear", base_power=2, base_toughness=2,
                                  owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=creature_spell, controller=p1)
        assert condition(game, event) is False


class TestSilverquillCasualtyEffect:
    """Casualty 1 effect: sacrifice a creature with power ≥ 1 to copy the spell."""

    def test_no_sacrifice_when_no_legal_targets(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        # Push a dummy instant onto stack.
        spell = Instant(name="Bolt", owner=p1, controller=p1)
        p1.zones[Zone.STACK].add(spell)
        so = StackObject(source=spell, controller=p1, on_resolve=lambda g: None)
        game.stack.push(so)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        # No creatures with power ≥ 1 besides Silverquill (which we allow sacrificing).
        # But the effect will look for creatures (not Silverquill itself in legal list).
        # Silverquill has power 4 ≥ 1 but is excluded from default check.
        # Put a 0/1 creature — too weak.
        small = Creature(name="Wimp", base_power=0, base_toughness=1,
                         owner=p1, controller=p1)
        game.get_battlefield(p1).add(small)
        before_stack = len(game.stack)
        trigger.effect(game)
        assert len(game.stack) == before_stack  # no copy pushed

    def test_sacrifice_copies_spell(self) -> None:
        game = create_game(scripts=[[True, 0], []])  # yes, choose index 0
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        # Legal casualty target: creature with power ≥ 1.
        sacrificial = Creature(name="Token", base_power=1, base_toughness=1,
                               owner=p1, controller=p1)
        game.get_battlefield(p1).add(sacrificial)
        spell = Instant(name="Bolt", owner=p1, controller=p1)
        p1.zones[Zone.STACK].add(spell)
        so = StackObject(source=spell, controller=p1, on_resolve=lambda g: None)
        game.stack.push(so)
        before_stack = len(game.stack)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        trigger.effect(game)
        # Copy was pushed onto the stack.
        assert len(game.stack) == before_stack + 1
        # Sacrificial creature was removed from battlefield.
        assert not game.get_battlefield(p1).contains(sacrificial)
