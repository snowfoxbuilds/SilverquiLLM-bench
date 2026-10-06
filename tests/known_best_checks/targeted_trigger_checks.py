"""A triggered ability that chose its targets as it went on the stack checks
each of them again as it resolves — zone stint, its whole target requirement
for its controller, and protection from its source — and does nothing at all
when every target is illegal (rule 608.2b).

Run inside ``known_best/workspace`` by
``tests/test_known_best_gameplay_regressions.py``: the module imports the
workspace's own ``engine``, ``cards`` and ``test_utils``.
"""

from __future__ import annotations

from cards.fdn.fdn_39.card_impl import GrapplingKraken
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_280.card_impl import Forest
from engine.decisions import GameRef
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.protection import ProtectionAbility
from engine.stack import resolve_top_of_stack
from engine.triggers import TriggerRegistration, choose_trigger_targets
from engine.types import CardType, Color, TargetRequirement, Zone
from engine.zones import move_to_zone
from test_utils import Intent, create_game, set_board_state


def _kraken_targets_lions():
    """Player 0's Grappling Kraken triggers on a Forest and targets player 1's
    Savannah Lions; the trigger waits on the stack."""
    kraken, lions, forest = GrapplingKraken(), SavannahLions(), Forest()
    game = create_game()
    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef()))
    set_board_state(game, 0, battlefield=[kraken], hand=[forest])
    set_board_state(game, 1, battlefield=[lions])
    kraken.register_triggers(game)
    move_to_zone(game, forest, Zone.HAND, Zone.BATTLEFIELD)
    game.trigger_manager.put_pending_on_stack(game)
    (obj,) = game.stack.objects()
    assert obj.targets == [lions]
    return game, lions


def _stunned(creature) -> bool:
    return creature.counters.get("stun", 0) > 0


def test_a_legal_target_is_tapped_and_stunned():
    game, lions = _kraken_targets_lions()
    resolve_top_of_stack(game)
    assert lions.is_tapped and _stunned(lions)


def test_a_target_no_longer_a_creature_is_untouched():
    game, lions = _kraken_targets_lions()
    lions.card_types = {CardType.ARTIFACT}
    resolve_top_of_stack(game)
    assert not lions.is_tapped and not _stunned(lions)


def test_a_target_that_gained_protection_from_blue_is_untouched():
    game, lions = _kraken_targets_lions()
    lions.protections = [ProtectionAbility(quality=Color.BLUE)]
    resolve_top_of_stack(game)
    assert not lions.is_tapped and not _stunned(lions)


def test_a_target_its_controller_now_controls_is_untouched():
    game, lions = _kraken_targets_lions()
    lions.controller = game.players[0]
    resolve_top_of_stack(game)
    assert not lions.is_tapped and not _stunned(lions)


def test_a_target_that_left_and_returned_is_untouched():
    game, lions = _kraken_targets_lions()
    move_to_zone(game, lions, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, lions, Zone.EXILE, Zone.BATTLEFIELD)
    resolve_top_of_stack(game)
    assert not lions.is_tapped and not _stunned(lions)


def _two_target_trigger(game, source, seen):
    """An upkeep trigger targeting two creatures, recording what it resolves with."""

    def _creature(obj):
        return CardType.CREATURE in getattr(obj, "card_types", set())

    requirements = [
        TargetRequirement(filter_fn=_creature, description="target creature", zone=Zone.BATTLEFIELD),
        TargetRequirement(filter_fn=_creature, description="another target creature", zone=Zone.BATTLEFIELD),
    ]
    game.trigger_manager.register(TriggerRegistration(
        event_type=BeginningOfUpkeepTriggeredEvent, condition=None,
        effect=lambda game, targets, context: seen.append(list(targets)),
        source=source, controller=game.players[0],
        targeting=lambda game, event, controller: choose_trigger_targets(game, controller, source, requirements),
    ))


def test_a_partly_illegal_pair_resolves_for_the_legal_target_only():
    source, first, second = Forest(), SavannahLions(), SavannahLions()
    game = create_game()
    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef()))
    set_board_state(game, 0, battlefield=[source])
    set_board_state(game, 1, battlefield=[first, second])
    seen: list[list] = []
    _two_target_trigger(game, source, seen)
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    game.trigger_manager.put_pending_on_stack(game)
    (obj,) = game.stack.objects()
    chosen = list(obj.targets)
    chosen[1].card_types = {CardType.ARTIFACT}
    resolve_top_of_stack(game)
    assert seen == [[chosen[0], None]]


def test_an_ability_whose_targets_are_all_illegal_does_nothing():
    source, first, second = Forest(), SavannahLions(), SavannahLions()
    game = create_game()
    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef()))
    set_board_state(game, 0, battlefield=[source])
    set_board_state(game, 1, battlefield=[first, second])
    seen: list[list] = []
    _two_target_trigger(game, source, seen)
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    game.trigger_manager.put_pending_on_stack(game)
    for creature in (first, second):
        creature.card_types = {CardType.ARTIFACT}
    resolve_top_of_stack(game)
    assert seen == []
