"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.events import SpellCastTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


def _spell(player, name="Bolt", cls=Instant):
    card = cls(name=name)
    card.owner = player
    card.controller = player
    return card


class TestProperties:
    def test_is_creature(self) -> None:
        assert isinstance(SilverquillTheDisputant(owner=None), Creature)

    def test_name(self) -> None:
        assert (
            SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"
        )

    def test_mana_cost(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse(
            "{2}{W}{B}"
        )

    def test_power_toughness(self) -> None:
        c = SilverquillTheDisputant(owner=None)
        assert (c.base_power, c.base_toughness) == (4, 4)

    def test_flying_vigilance_legendary(self) -> None:
        c = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in c.keywords
        assert Keyword.VIGILANCE in c.keywords
        assert Supertype.LEGENDARY in c.supertypes

    def test_registers_one_trigger(self) -> None:
        game = create_game()
        s = SilverquillTheDisputant(owner=game.players[0], controller=game.players[0])
        s.register_triggers(game)
        assert len(game.trigger_manager.get_triggers_for_source(s)) == 1


class TestCasualty:
    def _setup(self, scripts):
        game = create_game(scripts=scripts)
        p1, p2 = game.players
        silver = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(name="Fodder", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[silver, fodder])
        silver.register_triggers(game)
        spell_card = _spell(p1)
        spell_obj = StackObject(source=spell_card, controller=p1)
        game.stack.push(spell_obj)
        return game, p1, silver, fodder, spell_card, spell_obj

    def test_accept_sacrifices_and_copies(self) -> None:
        game, p1, silver, fodder, spell_card, spell_obj = self._setup(
            ([True, None], [])
        )
        # Replace the None placeholder: scripted answers are choose_yes_no then
        # choose_card. Put fodder as the card choice.
        p1._script.clear()
        p1._script.extend([True, fodder])

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell_obj, player=p1, card=spell_card, controller=p1
            ),
        )
        # Resolve the casualty trigger (top of stack).
        trig = game.stack.pop()
        trig.on_resolve(game)

        assert p1.zones[Zone.GRAVEYARD].contains(fodder)
        assert not game.get_battlefield(p1).contains(fodder)
        # Original spell + the copy remain on the stack.
        assert len(game.stack) == 2

    def test_decline_keeps_creature_and_no_copy(self) -> None:
        game, p1, silver, fodder, spell_card, spell_obj = self._setup(([False], []))
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell_obj, player=p1, card=spell_card, controller=p1
            ),
        )
        trig = game.stack.pop()
        trig.on_resolve(game)
        assert game.get_battlefield(p1).contains(fodder)
        # Only the original spell remains.
        assert len(game.stack) == 1


class TestConditionFiltering:
    def test_opponent_spell_does_not_trigger(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        silver = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silver])
        silver.register_triggers(game)
        spell_card = _spell(p2)
        spell_obj = StackObject(source=spell_card, controller=p2)
        game.stack.push(spell_obj)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell_obj, player=p2, card=spell_card, controller=p2
            ),
        )
        assert len(game.stack) == 1  # no casualty trigger added

    def test_creature_spell_does_not_trigger(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        silver = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silver])
        silver.register_triggers(game)
        creature_spell = Creature(name="Beast", base_power=3, base_toughness=3)
        creature_spell.owner = p1
        creature_spell.controller = p1
        spell_obj = StackObject(source=creature_spell, controller=p1)
        game.stack.push(spell_obj)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell_obj, player=p1, card=creature_spell, controller=p1
            ),
        )
        assert len(game.stack) == 1
