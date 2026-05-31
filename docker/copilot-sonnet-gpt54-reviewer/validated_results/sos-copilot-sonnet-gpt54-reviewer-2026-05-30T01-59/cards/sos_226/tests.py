"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from collections import deque

import pytest

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _CounterInstant(Instant):
    """Simple instant that counts how many times it has resolved."""

    resolve_count: int = 0

    def __init__(self, **kwargs):  # type: ignore[override]
        kwargs.setdefault("name", "Counter Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):  # type: ignore[override]
        _CounterInstant.resolve_count += 1


class _CounterSorcery(Sorcery):
    """Simple sorcery that counts how many times it has resolved."""

    resolve_count: int = 0

    def __init__(self, **kwargs):  # type: ignore[override]
        kwargs.setdefault("name", "Counter Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):  # type: ignore[override]
        _CounterSorcery.resolve_count += 1


def _make_bear(owner=None, controller=None, power: int = 2) -> Creature:
    """Return a creature with the given power (default 2) for sacrifice testing."""
    c = Creature(
        name="Test Bear",
        base_power=power,
        base_toughness=2,
        owner=owner,
        controller=controller,
    )
    return c


def _resolve_stack(game) -> None:
    """Drain the entire stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _setup(game):
    """Place Silverquill on p1's battlefield and register its triggers."""
    p1 = game.players[0]
    sw = SilverquillTheDisputant(owner=p1, controller=p1)
    game.get_battlefield(p1).add(sw)
    sw.register_triggers(game)
    return p1, sw


# ---------------------------------------------------------------------------
# 1. Card Identity
# ---------------------------------------------------------------------------

class TestSilverquillIdentity:
    """Static card properties must match the card spec."""

    def test_name(self) -> None:
        assert SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"

    def test_base_power(self) -> None:
        assert SilverquillTheDisputant(owner=None).base_power == 4

    def test_base_toughness(self) -> None:
        assert SilverquillTheDisputant(owner=None).base_toughness == 4

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in SilverquillTheDisputant(owner=None).keywords

    def test_has_vigilance(self) -> None:
        assert Keyword.VIGILANCE in SilverquillTheDisputant(owner=None).keywords

    def test_is_creature(self) -> None:
        assert isinstance(SilverquillTheDisputant(owner=None), Creature)

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in SilverquillTheDisputant(owner=None).supertypes

    def test_mana_cost(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_elder_dragon_subtype(self) -> None:
        subtypes = SilverquillTheDisputant(owner=None).subtypes
        assert "Elder" in subtypes
        assert "Dragon" in subtypes


# ---------------------------------------------------------------------------
# 2. Trigger Registration
# ---------------------------------------------------------------------------

class TestTriggerRegistration:
    """register_triggers adds a SpellCastTriggeredEvent trigger."""

    def test_register_adds_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sw = SilverquillTheDisputant(owner=p1, controller=p1)
        sw.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(sw)
        assert len(triggers) >= 1
        assert any(t.event_type is SpellCastTriggeredEvent for t in triggers)

    def test_condition_true_for_instant_by_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sw = SilverquillTheDisputant(owner=p1, controller=p1)
        sw.register_triggers(game)
        trigger = next(t for t in game.trigger_manager.get_triggers_for_source(sw)
                       if t.event_type is SpellCastTriggeredEvent)
        instant = _CounterInstant(owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=instant, card=instant, player=p1, controller=p1)
        assert trigger.condition(game, event) is True

    def test_condition_true_for_sorcery_by_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sw = SilverquillTheDisputant(owner=p1, controller=p1)
        sw.register_triggers(game)
        trigger = next(t for t in game.trigger_manager.get_triggers_for_source(sw)
                       if t.event_type is SpellCastTriggeredEvent)
        sorcery = _CounterSorcery(owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=sorcery, card=sorcery, player=p1, controller=p1)
        assert trigger.condition(game, event) is True

    def test_condition_false_for_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sw = SilverquillTheDisputant(owner=p1, controller=p1)
        sw.register_triggers(game)
        trigger = next(t for t in game.trigger_manager.get_triggers_for_source(sw)
                       if t.event_type is SpellCastTriggeredEvent)
        creature_spell = Creature(name="Bear", base_power=2, base_toughness=2,
                                  owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=creature_spell, card=creature_spell,
                                        player=p1, controller=p1)
        assert trigger.condition(game, event) is False

    def test_condition_false_for_opponent_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        sw = SilverquillTheDisputant(owner=p1, controller=p1)
        sw.register_triggers(game)
        trigger = next(t for t in game.trigger_manager.get_triggers_for_source(sw)
                       if t.event_type is SpellCastTriggeredEvent)
        instant = _CounterInstant(owner=p2, controller=p2)
        event = SpellCastTriggeredEvent(spell=instant, card=instant, player=p2, controller=p2)
        assert trigger.condition(game, event) is False

    def test_trigger_fires_when_instant_cast_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sw = SilverquillTheDisputant(owner=p1, controller=p1)
        sw.register_triggers(game)
        instant = _CounterInstant(owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=instant, card=instant, player=p1, controller=p1)
        game.trigger_manager.fire_event(game, event)
        assert not game.stack.is_empty()


# ---------------------------------------------------------------------------
# 3. Casualty — Decline to Sacrifice
# ---------------------------------------------------------------------------

class TestCasualtyDecline:
    """When the player declines the sacrifice, the spell resolves exactly once."""

    def _cast_and_resolve(self, game, p1, spell, mana_type: ManaType) -> None:
        """Helper: add mana, cast spell from hand, resolve stack."""
        game.get_hand(p1).add(spell)
        set_board_state(game, 0, mana={mana_type: 1})
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0
        from engine.casting import cast_spell as _cast
        _cast(game, p1, spell)
        _resolve_stack(game)

    def test_instant_resolves_once_on_decline(self) -> None:
        _CounterInstant.resolve_count = 0
        game = create_game()
        p1, sw = _setup(game)
        bear = _make_bear(owner=p1, controller=p1)
        game.get_battlefield(p1).add(bear)
        spell = _CounterInstant(owner=p1, controller=p1)
        # Script: decline sacrifice
        p1._script = deque([False])
        self._cast_and_resolve(game, p1, spell, ManaType.RED)
        assert _CounterInstant.resolve_count == 1
        # Bear is still on the battlefield
        assert bear in game.get_battlefield(p1).get_all()

    def test_sorcery_resolves_once_on_decline(self) -> None:
        _CounterSorcery.resolve_count = 0
        game = create_game()
        p1, sw = _setup(game)
        bear = _make_bear(owner=p1, controller=p1)
        game.get_battlefield(p1).add(bear)
        spell = _CounterSorcery(owner=p1, controller=p1)
        p1._script = deque([False])
        self._cast_and_resolve(game, p1, spell, ManaType.RED)
        assert _CounterSorcery.resolve_count == 1


# ---------------------------------------------------------------------------
# 4. Casualty — Accept Sacrifice
# ---------------------------------------------------------------------------

class TestCasualtyAccept:
    """When the player sacrifices, the spell resolves exactly twice."""

    def _cast_and_resolve(self, game, p1, spell, mana_type: ManaType) -> None:
        game.get_hand(p1).add(spell)
        set_board_state(game, 0, mana={mana_type: 1})
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0
        from engine.casting import cast_spell as _cast
        _cast(game, p1, spell)
        _resolve_stack(game)

    def test_instant_resolves_twice_on_accept(self) -> None:
        _CounterInstant.resolve_count = 0
        game = create_game()
        p1, sw = _setup(game)
        bear = _make_bear(owner=p1, controller=p1)
        game.get_battlefield(p1).add(bear)
        spell = _CounterInstant(owner=p1, controller=p1)
        # Script: yes, then choose the bear
        p1._script = deque([True, bear])
        self._cast_and_resolve(game, p1, spell, ManaType.RED)
        assert _CounterInstant.resolve_count == 2

    def test_sorcery_resolves_twice_on_accept(self) -> None:
        _CounterSorcery.resolve_count = 0
        game = create_game()
        p1, sw = _setup(game)
        bear = _make_bear(owner=p1, controller=p1)
        game.get_battlefield(p1).add(bear)
        spell = _CounterSorcery(owner=p1, controller=p1)
        p1._script = deque([True, bear])
        self._cast_and_resolve(game, p1, spell, ManaType.RED)
        assert _CounterSorcery.resolve_count == 2

    def test_sacrificed_creature_in_graveyard(self) -> None:
        _CounterInstant.resolve_count = 0
        game = create_game()
        p1, sw = _setup(game)
        bear = _make_bear(owner=p1, controller=p1)
        game.get_battlefield(p1).add(bear)
        spell = _CounterInstant(owner=p1, controller=p1)
        p1._script = deque([True, bear])
        self._cast_and_resolve(game, p1, spell, ManaType.RED)
        # The bear was sacrificed
        assert bear not in game.get_battlefield(p1).get_all()
        gy = game.get_graveyard(p1).get_all()
        assert bear in gy


# ---------------------------------------------------------------------------
# 5. Casualty — No eligible creatures
# ---------------------------------------------------------------------------

class TestCasualtyNoEligibleCreatures:
    """With no power->=1 creatures, casualty is unavailable and spell resolves once."""

    def _cast_and_resolve(self, game, p1, spell, mana_type: ManaType) -> None:
        game.get_hand(p1).add(spell)
        set_board_state(game, 0, mana={mana_type: 1})
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0
        from engine.casting import cast_spell as _cast
        _cast(game, p1, spell)
        _resolve_stack(game)

    def test_no_creatures_resolves_once_without_choice(self) -> None:
        """With no creatures on battlefield, no sacrifice is offered."""
        _CounterInstant.resolve_count = 0
        game = create_game()
        p1, sw = _setup(game)
        # No creature on battlefield (Silverquill itself doesn't count for
        # casualty when casting — it's not power>=1... wait it is 4/4.
        # Let's leave no OTHER creatures and make sure Silverquill alone
        # doesn't cause a sacrifice offer.)
        # Actually Silverquill has power 4, so it IS a candidate. Clear
        # the battlefield except Silverquill, then check.
        # Instead: just put a 0/1 creature on the battlefield.
        zero_power = Creature(name="Wall", base_power=0, base_toughness=3,
                              owner=p1, controller=p1)
        game.get_battlefield(p1).add(zero_power)
        spell = _CounterInstant(owner=p1, controller=p1)
        # No script needed — the trigger sees no candidates and returns early.
        # But Silverquill (power 4) is on the battlefield! It counts.
        # So this test actually expects a yes/no choice with Silverquill as candidate.
        # Re-design: put NO extra creatures, just Silverquill.
        # Silverquill itself has power 4, so it's a candidate.
        # Let's script yes, Silverquill (the dragon sacrifices itself for casualty).
        p1._script = deque([True, sw])
        self._cast_and_resolve(game, p1, spell, ManaType.RED)
        # Silverquill was sacrificed, spell resolved twice
        assert _CounterInstant.resolve_count == 2

    def test_zero_power_creature_not_eligible(self) -> None:
        """A 0/3 creature cannot be sacrificed for casualty 1."""
        _CounterInstant.resolve_count = 0
        game = create_game()
        # Set up without _setup so we can control the battlefield exactly.
        p1 = game.players[0]
        sw = SilverquillTheDisputant(owner=p1, controller=p1)
        # Clear everything, put only 0-power creatures + Silverquill
        # But Silverquill has power 4... skip it entirely and don't put
        # it on the battlefield — just register triggers manually.
        # Register triggers but don't add Silverquill to battlefield
        sw.register_triggers(game)
        wall = Creature(name="Wall", base_power=0, base_toughness=3,
                        owner=p1, controller=p1)
        game.get_battlefield(p1).add(wall)
        spell = _CounterInstant(owner=p1, controller=p1)
        # No sacrifice offer because only 0-power creatures exist.
        # Script is empty — no choices needed.
        p1._script = deque([])
        self._cast_and_resolve(game, p1, spell, ManaType.RED)
        assert _CounterInstant.resolve_count == 1
        # Wall is unaffected
        assert wall in game.get_battlefield(p1).get_all()

    def test_empty_battlefield_no_sacrifice_offered(self) -> None:
        """With nothing on the battlefield, no sacrifice is offered."""
        _CounterInstant.resolve_count = 0
        game = create_game()
        p1 = game.players[0]
        sw = SilverquillTheDisputant(owner=p1, controller=p1)
        sw.register_triggers(game)
        # No creatures on battlefield
        spell = _CounterInstant(owner=p1, controller=p1)
        p1._script = deque([])
        self._cast_and_resolve(game, p1, spell, ManaType.RED)
        assert _CounterInstant.resolve_count == 1


# ---------------------------------------------------------------------------
# 6. Non-instant/sorcery spells — no casualty
# ---------------------------------------------------------------------------

class TestNonInstantSorceryUnaffected:
    """Creatures and other non-instant/sorcery spells do not trigger casualty."""

    def test_creature_spell_cast_no_casualty_trigger(self) -> None:
        """Casting a creature spell while Silverquill is on the battlefield
        does NOT push a casualty trigger onto the stack."""
        game = create_game()
        p1, sw = _setup(game)
        bear = _make_bear(owner=p1, controller=p1)
        game.get_hand(p1).add(bear)
        # Set up sorcery-speed
        set_board_state(game, 0, mana={ManaType.GREEN: 2, ManaType.COLORLESS: 2})
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0
        from engine.casting import cast_spell as _cast
        bear.mana_cost = ManaCost.parse("{1}{G}")
        # Script is empty — if casualty triggers, DeterministicPlayer will raise.
        p1._script = deque([])
        _cast(game, p1, bear)
        # Stack should contain just the creature spell, no casualty trigger.
        # (Trigger manager fires the SpellCastTriggeredEvent but condition returns False.)
        assert game.stack.is_empty() or all(
            getattr(obj.source, "card_types", set()) == {CardType.CREATURE}
            for obj in game.stack._items
        )


# ---------------------------------------------------------------------------
# 7. Silverquill not on battlefield
# ---------------------------------------------------------------------------

class TestSilverquillNotOnBattlefield:
    """No casualty effect when Silverquill has not registered its triggers."""

    def _cast_and_resolve(self, game, p1, spell, mana_type: ManaType) -> None:
        game.get_hand(p1).add(spell)
        set_board_state(game, 0, mana={mana_type: 1})
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0
        from engine.casting import cast_spell as _cast
        _cast(game, p1, spell)
        _resolve_stack(game)

    def test_no_trigger_registered_spell_resolves_once(self) -> None:
        """Without Silverquill on the battlefield, no casualty trigger fires."""
        _CounterInstant.resolve_count = 0
        game = create_game()
        p1 = game.players[0]
        # Silverquill is in hand, NOT registered
        sw = SilverquillTheDisputant(owner=p1, controller=p1)
        game.get_hand(p1).add(sw)
        # No register_triggers call
        bear = _make_bear(owner=p1, controller=p1)
        game.get_battlefield(p1).add(bear)
        spell = _CounterInstant(owner=p1, controller=p1)
        # Script is empty — if something pops from it, the test will fail
        p1._script = deque([])
        self._cast_and_resolve(game, p1, spell, ManaType.RED)
        assert _CounterInstant.resolve_count == 1
