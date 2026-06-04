"""Tests for Silverquill, the Disputant (SOS 226)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.events import SpellCastTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class _Pinger(Instant):
    """Trivial instant that records each resolution on the game object."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pinger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        game._resolved = getattr(game, "_resolved", 0) + 1


def _put_spell_on_stack(game: Any, caster: Any, card: Any) -> StackObject:
    card.owner = caster
    card.controller = caster
    caster.zones[Zone.STACK].add(card)
    obj = StackObject(
        source=card,
        controller=caster,
        on_resolve=lambda g, c=card: c.on_resolve(g),
    )
    game.stack.push(obj)
    return obj


def _resolve_stack(game: Any) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestSilverquillProperties:
    def test_is_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        assert SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_power_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.power == 4
        assert card.toughness == 4

    def test_keywords(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords

    def test_legendary_elder_dragon(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Dragon" in card.subtypes
        assert "Elder" in card.subtypes


class TestSilverquillCasualty:
    def _setup(self, scripts):
        game = create_game(scripts=scripts)
        p1, p2 = game.players
        silver = SilverquillTheDisputant()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[silver, bear])
        silver.register_triggers(game)
        return game, p1, p2, silver, bear

    def test_registers_trigger(self) -> None:
        game, p1, p2, silver, bear = self._setup(([], []))
        assert len(game.trigger_manager.get_triggers_for_source(silver)) == 1

    def test_pay_casualty_copies_spell(self) -> None:
        game, p1, p2, silver, bear = self._setup(([True, None], []))
        # script: choose_yes_no -> True, choose_card -> bear (patched below)
        game.players[0]._script.clear()
        game.players[0]._script.extend([True, bear])

        pinger = _Pinger()
        obj = _put_spell_on_stack(game, p1, pinger)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=obj, card=pinger, player=p1, controller=p1),
        )
        _resolve_stack(game)

        assert game._resolved == 2  # original + copy
        assert p1.zones[Zone.GRAVEYARD].contains(bear)
        assert not p1.zones[Zone.BATTLEFIELD].contains(bear)

    def test_decline_casualty(self) -> None:
        game, p1, p2, silver, bear = self._setup(([False], []))
        pinger = _Pinger()
        obj = _put_spell_on_stack(game, p1, pinger)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=obj, card=pinger, player=p1, controller=p1),
        )
        _resolve_stack(game)

        assert game._resolved == 1  # only the original
        assert p1.zones[Zone.BATTLEFIELD].contains(bear)

    def test_opponent_spell_does_not_trigger(self) -> None:
        game, p1, p2, silver, bear = self._setup(([], []))
        pinger = _Pinger()
        obj = _put_spell_on_stack(game, p2, pinger)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=obj, card=pinger, player=p2, controller=p2),
        )
        # Only the opponent's spell is on the stack — no casualty trigger.
        assert len(game.stack) == 1

    def test_noncreature_spell_does_not_trigger(self) -> None:
        from engine.card import Sorcery

        game, p1, p2, silver, bear = self._setup(([], []))
        # A spell that is neither instant nor sorcery should not get casualty.
        artifact_like = Creature(name="Beast", base_power=1, base_toughness=1)
        obj = _put_spell_on_stack(game, p1, artifact_like)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=obj, card=artifact_like, player=p1, controller=p1
            ),
        )
        assert len(game.stack) == 1

    def test_sorcery_also_gets_casualty(self) -> None:
        from engine.card import Sorcery

        game, p1, p2, silver, bear = self._setup(([], []))
        game.players[0]._script.extend([True, bear])

        class _Srcy(Sorcery):
            def __init__(self, **kw: Any) -> None:
                kw.setdefault("name", "Srcy")
                kw.setdefault("mana_cost", ManaCost.parse("{1}"))
                super().__init__(**kw)

            def on_resolve(self, game: Any) -> None:
                game._resolved = getattr(game, "_resolved", 0) + 1

        srcy = _Srcy()
        obj = _put_spell_on_stack(game, p1, srcy)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=obj, card=srcy, player=p1, controller=p1),
        )
        _resolve_stack(game)
        assert game._resolved == 2
        assert p1.zones[Zone.GRAVEYARD].contains(bear)
