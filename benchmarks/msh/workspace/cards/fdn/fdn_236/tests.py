"""Regression test for FDN 236 — Wildwood Scourge.

The crash surface is **trigger registration on a permanent entering play**:
``register_triggers`` gated its subscription behind ``hasattr(EventType, ...)``
on an undefined ``EventType`` name, so registration raised ``NameError``
(`register_triggers Wildwood Scourge` in the replay layer). This test drives
``register_triggers`` and asserts it completes and subscribes to the declared
``CounterAddedTriggeredEvent``.

Note the documented dependency: ``engine.game.add_counter`` does not yet emit
``CounterAddedTriggeredEvent``, so the trigger is registered correctly but
dormant until the engine-primitives phase.
"""

from __future__ import annotations

from cards.fdn.fdn_236.card_impl import WildwoodScourge
from engine.card import Creature
from engine.events import CounterAddedTriggeredEvent
from engine.game import add_counter
from engine.types import ManaCost
from test_utils import create_game, set_board_state


class TestWildwoodScourgeProperties:
    def test_name_and_cost(self) -> None:
        card = WildwoodScourge(owner=None)
        assert card.name == "Wildwood Scourge"
        assert card.mana_cost == ManaCost.parse("{X}{G}")

    def test_enters_with_x_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WildwoodScourge(owner=p1, controller=p1)
        card.x_value = 3
        set_board_state(game, 0, battlefield=[card])
        card.on_resolve(game)
        assert card.plus_one_counters == 3


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
