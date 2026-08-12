"""Regression test for FDN 236 — Wildwood Scourge.

The crash surface is **trigger registration on a permanent entering play**:
``register_triggers`` gated its subscription behind ``hasattr(EventType, ...)``
on an undefined ``EventType`` name, so registration raised ``NameError``
(`register_triggers Wildwood Scourge` in the replay layer). This test drives
``register_triggers`` and asserts it completes and subscribes to the declared
``CounterAddedTriggeredEvent``. The X entry counters are now supplied by the
enters-with-counters primitive (``enters_battlefield_with``) rather than
``on_resolve``, so they are on the creature as it enters.
"""

from __future__ import annotations

from cards.fdn.fdn_236.card_impl import WildwoodScourge
from engine.card import Creature
from engine.events import CounterAddedTriggeredEvent
from engine.game import add_counter
from engine.types import ManaCost, Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state


class TestWildwoodScourgeProperties:
    def test_name_and_cost(self) -> None:
        card = WildwoodScourge(owner=None)
        assert card.name == "Wildwood Scourge"
        assert card.mana_cost == ManaCost.parse("{X}{G}")

    def test_enters_with_x_counters(self) -> None:
        # Enters-with-counters primitive: X +1/+1 counters land AS the creature
        # enters, so a 0/0 with X=3 is a 3/3 the moment it is on the battlefield.
        game = create_game()
        p1 = game.players[0]
        card = WildwoodScourge(owner=p1, controller=p1)
        card.x_value = 3
        set_board_state(game, 0, hand=[card])
        move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
        assert card.plus_one_counters == 3
        assert card.power == 3
        assert card.toughness == 3

    def test_x_zero_enters_at_zero_zero_no_fabrication(self) -> None:
        # No X evidence → x_value stays 0 → the creature honestly enters at 0/0
        # (and would die to the 0-toughness SBA). No counter is invented.
        game = create_game()
        p1 = game.players[0]
        card = WildwoodScourge(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card])
        move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
        assert card.plus_one_counters == 0
        assert card.toughness == 0


class TestWildwoodScourgeTriggerRegistration:
    """The previously-crashing register_triggers path."""

    def test_register_triggers_does_not_raise_and_subscribes(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WildwoodScourge(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.register_triggers(game)  # must not raise NameError

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert any(t.event_type is CounterAddedTriggeredEvent for t in triggers)

    def test_condition_matches_other_nonhydra_creature_you_control(self) -> None:
        game = create_game()
        p1 = game.players[0]
        scourge = WildwoodScourge(owner=p1, controller=p1)
        other = Creature(name="Beast", subtypes={"Beast"}, base_power=1,
                         base_toughness=1, owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[scourge, other])
        scourge.register_triggers(game)

        trig = next(
            t for t in game.trigger_manager.get_triggers_for_source(scourge)
            if t.event_type is CounterAddedTriggeredEvent
        )
        event = CounterAddedTriggeredEvent(permanent=other, counter_type="+1/+1", amount=1)
        assert trig.condition(game, event) is True

        # Self and Hydra creatures are excluded.
        self_event = CounterAddedTriggeredEvent(permanent=scourge, counter_type="+1/+1")
        assert trig.condition(game, self_event) is False


class TestWildwoodScourgeThroughBattlefieldEntry:
    """Integration coverage: trigger registration for a permanent normally
    happens through the battlefield-entry path, not a hand-call to
    ``register_triggers``. Entering via the real zone-transition must not
    raise and must leave the ``CounterAddedTriggeredEvent`` subscription live.
    """

    def test_battlefield_entry_registers_counter_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        scourge = WildwoodScourge(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[scourge])

        # Normal zone-entry path: move_to_zone runs register_triggers on
        # battlefield entry (must not raise — the NameError used to crash it).
        move_to_zone(game, scourge, Zone.HAND, Zone.BATTLEFIELD)

        assert game.get_battlefield(p1).contains(scourge)
        triggers = game.trigger_manager.get_triggers_for_source(scourge)
        assert any(
            t.event_type is CounterAddedTriggeredEvent for t in triggers
        )
