"""Audited tests for FDN 27 — Valkyrie's Call."""

from __future__ import annotations

from card_impl import ValkyrieSCall

from engine.card import Creature, Enchantment
from engine.triggers import EventType
from engine.types import CardType, Keyword, ManaCost, Zone
from tests.test_utils import create_game


class TestValkyrieSCallBasics:
    """Basic card properties."""

    def test_is_enchantment(self) -> None:
        card = ValkyrieSCall(owner=None)
        assert isinstance(card, Enchantment)

    def test_name(self) -> None:
        card = ValkyrieSCall(owner=None)
        assert card.name == "Valkyrie's Call"

    def test_mana_cost(self) -> None:
        card = ValkyrieSCall(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{W}{W}")


class TestValkyrieSCallDeathTrigger:
    """Nontoken non-Angel creature dies -> return with +1/+1 counter, flying, Angel."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        enchantment = ValkyrieSCall(owner=p1, controller=p1)
        game.get_battlefield(p1).add(enchantment)
        enchantment.register_triggers(game)
        return game, p1, enchantment

    def test_nontoken_creature_returns_to_battlefield(self) -> None:
        game, p1, enchantment = self._setup()
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(bear)
        game.trigger_manager.fire_event(
            game, EventType.CREATURE_DIES,
            {"creature": bear, "controller": p1},
        )
        self._resolve_stack(game)
        assert game.get_battlefield(p1).contains(bear)

    def test_returned_creature_gets_plus_one_counter(self) -> None:
        game, p1, enchantment = self._setup()
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(bear)
        game.trigger_manager.fire_event(
            game, EventType.CREATURE_DIES,
            {"creature": bear, "controller": p1},
        )
        self._resolve_stack(game)
        assert getattr(bear, "plus_one_counters", 0) >= 1

    def test_returned_creature_gains_flying(self) -> None:
        game, p1, enchantment = self._setup()
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(bear)
        game.trigger_manager.fire_event(
            game, EventType.CREATURE_DIES,
            {"creature": bear, "controller": p1},
        )
        self._resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert Keyword.FLYING in bear.keywords

    def test_returned_creature_becomes_angel(self) -> None:
        game, p1, enchantment = self._setup()
        bear = Creature(name="Bear", subtypes={"Bear"}, base_power=2, base_toughness=2,
                        owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(bear)
        game.trigger_manager.fire_event(
            game, EventType.CREATURE_DIES,
            {"creature": bear, "controller": p1},
        )
        self._resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert "Angel" in bear.subtypes
        assert "Bear" in bear.subtypes  # keeps original types

    def test_token_creature_does_not_trigger(self) -> None:
        game, p1, enchantment = self._setup()
        token = Creature(name="Token Bear", base_power=2, base_toughness=2,
                         owner=p1, controller=p1)
        token.is_token = True
        p1.zones[Zone.GRAVEYARD].add(token)
        initial_bf_count = len(game.get_battlefield(p1).get_all())
        game.trigger_manager.fire_event(
            game, EventType.CREATURE_DIES,
            {"creature": token, "controller": p1},
        )
        self._resolve_stack(game)
        # Token should not be returned
        assert len(game.get_battlefield(p1).get_all()) == initial_bf_count

    def test_angel_creature_does_not_trigger(self) -> None:
        game, p1, enchantment = self._setup()
        angel = Creature(name="Angel", subtypes={"Angel"}, base_power=4, base_toughness=4,
                         owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(angel)
        initial_bf_count = len(game.get_battlefield(p1).get_all())
        game.trigger_manager.fire_event(
            game, EventType.CREATURE_DIES,
            {"creature": angel, "controller": p1},
        )
        self._resolve_stack(game)
        assert len(game.get_battlefield(p1).get_all()) == initial_bf_count

    def test_opponent_creature_does_not_trigger(self) -> None:
        game, p1, enchantment = self._setup()
        p2 = game.players[1]
        opp = Creature(name="Opp Bear", base_power=2, base_toughness=2,
                        owner=p2, controller=p2)
        p2.zones[Zone.GRAVEYARD].add(opp)
        initial_bf_count = len(game.get_battlefield(p1).get_all())
        game.trigger_manager.fire_event(
            game, EventType.CREATURE_DIES,
            {"creature": opp, "controller": p2},
        )
        self._resolve_stack(game)
        assert len(game.get_battlefield(p1).get_all()) == initial_bf_count
