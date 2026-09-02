"""Engine tests for the enters-with-counters replacement primitive (rule 614.1c).

A permanent that "enters with N counters" has them on it *as* it enters — it is
never a transient 0/0 that dies to the 0-toughness state-based action, and the
counters are present when the ETB event fires and before the first SBA pass. The
primitive has two contribution channels (the entering card's own
``enters_battlefield_with`` self-hook and third-party replacement effects on
``EntersBattlefieldReplacementEvent``), lands the counters through the shared
``AddCounterReplacementEvent`` path (so doublers apply), and fires exactly one
``CounterAddedTriggeredEvent`` per counter type after the ETB event.
"""

from __future__ import annotations

from typing import Any

from engine.card import Creature
from engine.events import (
    CounterAddedTriggeredEvent,
    EntersBattlefieldReplacementEvent,
    EntersBattlefieldTriggeredEvent,
)
from engine.game import create_token
from engine.replacement_effects import ReplacementEffect
from engine.state_based_actions import resolve_state_based_actions
from engine.triggers import TriggerRegistration
from engine.types import Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state


class _EntersWith(Creature):
    """A test creature that enters with a fixed bag of counters."""

    def __init__(self, counters: dict[str, int], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._entry_counters = counters

    def enters_battlefield_with(self, game: Any, event: Any) -> None:
        for ctype, amount in self._entry_counters.items():
            event.counters[ctype] = event.counters.get(ctype, 0) + amount


def _enter_from_hand(game, player, card):
    set_board_state(game, game.players.index(player), hand=[card])
    move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)


class TestZeroZeroSurvival:
    def test_zero_zero_with_counters_survives_sba(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _EntersWith({"+1/+1": 2}, name="Hydra", base_power=0,
                           base_toughness=0, owner=p1, controller=p1)
        _enter_from_hand(game, p1, card)
        # Counters landed as it entered — a 2/2, present before any SBA.
        assert card.plus_one_counters == 2
        assert (card.power, card.toughness) == (2, 2)
        resolve_state_based_actions(game)
        assert game.get_battlefield(p1).contains(card)

    def test_zero_zero_without_counters_dies_to_sba(self) -> None:
        # The honest-refusal pin: no evidence => no counters => a real 0/0 that
        # dies to the 0-toughness SBA. Nothing is fabricated to keep it alive.
        game = create_game()
        p1 = game.players[0]
        card = _EntersWith({}, name="Hydra", base_power=0, base_toughness=0,
                           owner=p1, controller=p1)
        _enter_from_hand(game, p1, card)
        assert card.toughness == 0
        resolve_state_based_actions(game)
        assert not game.get_battlefield(p1).contains(card)
        assert game.players[0].zones[Zone.GRAVEYARD].contains(card)


class TestCountersVisibleAtEtb:
    def test_counters_present_when_etb_event_fires(self) -> None:
        game = create_game()
        p1 = game.players[0]
        seen: list[int] = []

        class _RecordsAtEtb(_EntersWith):
            def register_triggers(self, g: Any) -> None:
                src = self

                def _cond(g: Any, event: Any) -> bool:
                    if event.permanent is src:
                        # Condition runs at ETB fire time — counters must be on.
                        seen.append(src.plus_one_counters)
                    return False

                g.trigger_manager.register(TriggerRegistration(
                    event_type=EntersBattlefieldTriggeredEvent,
                    condition=_cond, effect=lambda g: None,
                    source=self, controller=self.controller,
                ))

        card = _RecordsAtEtb({"+1/+1": 3}, name="Watcher", base_power=0,
                             base_toughness=0, owner=p1, controller=p1)
        _enter_from_hand(game, p1, card)
        assert seen == [3]


class TestCounterAddedFiring:
    def _count_counter_events(self, game):
        events: list[tuple[str, int]] = []
        # A bystander that records every CounterAddedTriggeredEvent it sees.
        recorder = Creature(name="Recorder", base_power=1, base_toughness=1,
                            owner=game.players[0], controller=game.players[0])

        def _cond(g: Any, event: Any) -> bool:
            events.append((event.counter_type, event.amount))
            return False

        game.trigger_manager.register(TriggerRegistration(
            event_type=CounterAddedTriggeredEvent, condition=_cond,
            effect=lambda g: None, source=recorder, controller=game.players[0],
        ))
        return events

    def test_exactly_one_event_per_type(self) -> None:
        game = create_game()
        p1 = game.players[0]
        events = self._count_counter_events(game)
        card = _EntersWith({"+1/+1": 3}, name="Hydra", base_power=0,
                           base_toughness=0, owner=p1, controller=p1)
        _enter_from_hand(game, p1, card)
        # One event for the whole +1/+1 batch, carrying the full amount.
        assert events == [("+1/+1", 3)]

    def test_one_event_per_distinct_type(self) -> None:
        game = create_game()
        p1 = game.players[0]
        events = self._count_counter_events(game)
        card = _EntersWith({"+1/+1": 1, "revival": 8}, name="Multi",
                           base_power=1, base_toughness=1, owner=p1, controller=p1)
        _enter_from_hand(game, p1, card)
        assert sorted(events) == [("+1/+1", 1), ("revival", 8)]

    def test_etb_fires_before_counter_added(self) -> None:
        game = create_game()
        p1 = game.players[0]
        order: list[str] = []
        recorder = Creature(name="Recorder", base_power=1, base_toughness=1,
                            owner=p1, controller=p1)
        game.trigger_manager.register(TriggerRegistration(
            event_type=EntersBattlefieldTriggeredEvent,
            condition=lambda g, e: order.append("etb") or False,
            effect=lambda g: None, source=recorder, controller=p1,
        ))
        game.trigger_manager.register(TriggerRegistration(
            event_type=CounterAddedTriggeredEvent,
            condition=lambda g, e: order.append("counter") or False,
            effect=lambda g: None, source=recorder, controller=p1,
        ))
        card = _EntersWith({"+1/+1": 1}, name="Hydra", base_power=0,
                           base_toughness=0, owner=p1, controller=p1)
        _enter_from_hand(game, p1, card)
        assert order == ["etb", "counter"]


class TestThirdPartyContribution:
    """Giada-shape: a registered replacement adds counters to entering others."""

    def test_third_party_replacement_adds_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        granter = Creature(name="Granter", base_power=1, base_toughness=1,
                           owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[granter])

        def _cond(g: Any, event: Any) -> bool:
            return event.permanent is not granter

        def _repl(g: Any, event: Any) -> Any:
            event.counters["+1/+1"] = event.counters.get("+1/+1", 0) + 2
            return event

        game.replacement_manager.register(ReplacementEffect(
            event_type=EntersBattlefieldReplacementEvent, source=granter,
            condition=_cond, replacement=_repl, controller=p1,
        ))

        newcomer = Creature(name="Newcomer", base_power=1, base_toughness=1,
                            owner=p1, controller=p1)
        _enter_from_hand(game, p1, newcomer)
        assert newcomer.plus_one_counters == 2

    def test_self_hook_and_third_party_stack(self) -> None:
        # A card's own entry counters and a third-party grant sum on entry.
        game = create_game()
        p1 = game.players[0]
        granter = Creature(name="Granter", base_power=1, base_toughness=1,
                           owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[granter])
        game.replacement_manager.register(ReplacementEffect(
            event_type=EntersBattlefieldReplacementEvent, source=granter,
            condition=lambda g, e: e.permanent is not granter,
            replacement=lambda g, e: (
                e.counters.__setitem__("+1/+1", e.counters.get("+1/+1", 0) + 1)
                or e
            ),
            controller=p1,
        ))
        card = _EntersWith({"+1/+1": 2}, name="Hydra", base_power=0,
                           base_toughness=0, owner=p1, controller=p1)
        _enter_from_hand(game, p1, card)
        assert card.plus_one_counters == 3


class TestDoublingInteraction:
    """Entry counters go through AddCounterReplacementEvent, so doublers apply."""

    def test_doubling_season_doubles_entry_counters(self) -> None:
        from engine.events import AddCounterReplacementEvent

        game = create_game()
        p1 = game.players[0]
        doubler = Creature(name="Doubler", base_power=1, base_toughness=1,
                          owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[doubler])

        def _repl(g: Any, event: Any) -> Any:
            event.amount *= 2
            return event

        game.replacement_manager.register(ReplacementEffect(
            event_type=AddCounterReplacementEvent, source=doubler,
            condition=lambda g, e: e.counter_type == "+1/+1",
            replacement=_repl, controller=p1,
        ))
        card = _EntersWith({"+1/+1": 2}, name="Hydra", base_power=0,
                           base_toughness=0, owner=p1, controller=p1)
        _enter_from_hand(game, p1, card)
        assert card.plus_one_counters == 4


class TestPlaceTokenPath:
    def test_token_enters_with_third_party_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        granter = Creature(name="Granter", base_power=1, base_toughness=1,
                           owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[granter])
        game.replacement_manager.register(ReplacementEffect(
            event_type=EntersBattlefieldReplacementEvent, source=granter,
            condition=lambda g, e: e.permanent is not granter,
            replacement=lambda g, e: (
                e.counters.__setitem__("+1/+1", e.counters.get("+1/+1", 0) + 2)
                or e
            ),
            controller=p1,
        ))
        token = Creature(name="Elf Token", base_power=1, base_toughness=1)
        placed = create_token(game, p1, token)
        assert placed[0].plus_one_counters == 2

    def test_token_self_hook_entry_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        token = _EntersWith({"+1/+1": 1}, name="Token", base_power=0,
                            base_toughness=0)
        placed = create_token(game, p1, token)
        assert placed[0].plus_one_counters == 1
        resolve_state_based_actions(game)
        assert game.get_battlefield(p1).contains(placed[0])
