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


# ---------------------------------------------------------------------------
# Each target is checked against the requirement it was chosen for
# ---------------------------------------------------------------------------


def _felidar_targets(*allies):
    """Player 0's Felidar Savior enters with *allies* — creatures they
    control — and its enters trigger goes on the stack choosing them, in
    order, for its two "up to one" slots."""
    from cards.fdn.fdn_12.card_impl import FelidarSavior
    from engine.decisions import Decision

    felidar, lions = FelidarSavior(), [SavannahLions(), SavannahLions()]
    game = create_game()
    p0, p1 = game.players
    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef()))
    set_board_state(game, 0, hand=[felidar], battlefield=lions)
    chosen = [lions[i] for i in allies]
    p0.set_baseline(Intent(pattern=GameRef(), preferences=tuple(
        Decision.obj(instance=game.refs.instance_id(c, Zone.BATTLEFIELD.value)) for c in chosen
    )))
    move_to_zone(game, felidar, Zone.HAND, Zone.BATTLEFIELD)
    game.trigger_manager.put_pending_on_stack(game)
    (obj,) = game.stack.objects()
    assert obj.targets == chosen
    return game, lions


def _counters(creature) -> int:
    return creature.counters.get("+1/+1", 0)


def test_both_felidar_targets_legal_get_a_counter_each():
    game, (first, second) = _felidar_targets(0, 1)
    resolve_top_of_stack(game)
    assert (_counters(first), _counters(second)) == (1, 1)


def test_felidar_first_target_now_controlled_by_the_opponent_leaves_the_second_its_counter():
    game, (first, second) = _felidar_targets(0, 1)
    first.controller = game.players[1]
    resolve_top_of_stack(game)
    assert (_counters(first), _counters(second)) == (0, 1)


def test_felidar_first_target_no_longer_a_creature_leaves_the_second_its_counter():
    game, (first, second) = _felidar_targets(0, 1)
    first.card_types = {CardType.ARTIFACT}
    resolve_top_of_stack(game)
    assert (_counters(first), _counters(second)) == (0, 1)


def test_felidar_first_target_with_protection_from_white_leaves_the_second_its_counter():
    game, (first, second) = _felidar_targets(0, 1)
    first.protections = [ProtectionAbility(quality=Color.WHITE)]
    resolve_top_of_stack(game)
    assert (_counters(first), _counters(second)) == (0, 1)


def test_felidar_first_target_that_left_and_returned_leaves_the_second_its_counter():
    game, (first, second) = _felidar_targets(0, 1)
    move_to_zone(game, first, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, first, Zone.EXILE, Zone.BATTLEFIELD)
    resolve_top_of_stack(game)
    assert (_counters(first), _counters(second)) == (0, 1)


def test_felidar_with_its_second_slot_declined_counts_its_one_target():
    game, (first, second) = _felidar_targets(1)
    resolve_top_of_stack(game)
    assert (_counters(first), _counters(second)) == (0, 1)


def test_felidar_with_its_one_target_illegal_does_nothing():
    game, (first, second) = _felidar_targets(1)
    second.controller = game.players[1]
    resolve_top_of_stack(game)
    assert (_counters(first), _counters(second)) == (0, 0)


def test_felidar_with_both_targets_illegal_does_nothing():
    game, (first, second) = _felidar_targets(0, 1)
    for lions in (first, second):
        lions.controller = game.players[1]
    resolve_top_of_stack(game)
    assert (_counters(first), _counters(second)) == (0, 0)


def _artifact_then_creature_trigger(game, source, seen):
    """An upkeep trigger with "up to one target artifact" then "target
    creature", recording what it resolves with."""

    def _is(card_type):
        return lambda obj: card_type in getattr(obj, "card_types", set())

    requirements = [
        TargetRequirement(filter_fn=_is(CardType.ARTIFACT), description="up to one target artifact",
                          zone=Zone.BATTLEFIELD, optional=True),
        TargetRequirement(filter_fn=_is(CardType.CREATURE), description="target creature", zone=Zone.BATTLEFIELD),
    ]
    game.trigger_manager.register(TriggerRegistration(
        event_type=BeginningOfUpkeepTriggeredEvent, condition=None,
        effect=lambda game, targets, context: seen.append(list(targets)),
        source=source, controller=game.players[0],
        targeting=lambda game, event, controller: choose_trigger_targets(game, controller, source, requirements),
    ))


def _heterogeneous(*chosen_names):
    from engine.card import Artifact
    from engine.decisions import Decision

    source, relic, lions = Forest(), Artifact(name="Relic"), SavannahLions()
    game = create_game()
    p0 = game.players[0]
    set_board_state(game, 0, battlefield=[source])
    set_board_state(game, 1, battlefield=[relic, lions])
    by_name = {"relic": relic, "lions": lions}
    p0.set_baseline(Intent(pattern=GameRef(), preferences=tuple(
        Decision.obj(instance=game.refs.instance_id(by_name[n], Zone.BATTLEFIELD.value)) for n in chosen_names
    )))
    game.players[1].set_baseline(Intent(pattern=GameRef()))
    seen: list[list] = []
    _artifact_then_creature_trigger(game, source, seen)
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    game.trigger_manager.put_pending_on_stack(game)
    return game, relic, lions, seen


def test_an_artifact_target_that_became_a_creature_is_not_checked_against_the_creature_requirement():
    game, relic, lions, seen = _heterogeneous("relic", "lions")
    assert game.stack.objects()[0].targets == [relic, lions]
    relic.card_types = {CardType.CREATURE}
    resolve_top_of_stack(game)
    assert seen == [[None, lions]]


def test_a_declined_artifact_slot_leaves_the_creature_checked_as_a_creature():
    game, relic, lions, seen = _heterogeneous("lions")
    assert game.stack.objects()[0].targets == [lions]
    resolve_top_of_stack(game)
    assert seen == [[lions]]


# ---------------------------------------------------------------------------
# Stromkirk Bloodthief's intervening "if" is checked for the ability's
# controller as it resolves, not for whoever controls its source then
# ---------------------------------------------------------------------------


def _bloodthief_at_end_step(*, source_controller_seat: int = 0):
    """Player 0's end step begins after player 1 lost life; Stromkirk
    Bloodthief (controlled by *source_controller_seat*) may trigger, targeting
    player 0's other Vampire."""
    from cards.fdn.fdn_185.card_impl import StromkirkBloodthief
    from engine.card import Creature
    from engine.decisions import Decision
    from engine.events import EndStepTriggeredEvent

    bloodthief = StromkirkBloodthief()
    vampire = Creature(name="Vampire", base_power=1, base_toughness=1, subtypes={"Vampire"})
    game = create_game()
    p0, p1 = game.players
    set_board_state(game, source_controller_seat, battlefield=[bloodthief])
    set_board_state(game, 0, battlefield=[vampire])
    p1.life_lost_this_turn = 1
    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef(), preferences=(
            Decision.obj(instance=game.refs.instance_id(vampire, Zone.BATTLEFIELD.value)),
        )))
    bloodthief.register_triggers(game)
    game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p0))
    game.trigger_manager.put_pending_on_stack(game)
    return game, bloodthief, vampire


def _placed(game, vampire):
    (obj,) = game.stack.objects()
    assert obj.controller is game.players[0] and obj.targets == [vampire]


def test_bloodthief_counts_its_target_when_nothing_changed():
    game, bloodthief, vampire = _bloodthief_at_end_step()
    _placed(game, vampire)
    resolve_top_of_stack(game)
    assert _counters(vampire) == 1


def test_bloodthief_resolves_for_its_controller_after_its_source_is_stolen():
    game, bloodthief, vampire = _bloodthief_at_end_step()
    _placed(game, vampire)
    bloodthief.controller = game.players[1]
    resolve_top_of_stack(game)
    assert _counters(vampire) == 1


def test_bloodthief_resolves_after_its_stolen_source_dies_and_returns_to_its_owner():
    game, bloodthief, vampire = _bloodthief_at_end_step()
    _placed(game, vampire)
    bloodthief.controller = game.players[1]
    move_to_zone(game, bloodthief, Zone.BATTLEFIELD, Zone.GRAVEYARD)
    resolve_top_of_stack(game)
    assert _counters(vampire) == 1


def test_bloodthief_resolves_after_its_source_leaves_and_returns():
    game, bloodthief, vampire = _bloodthief_at_end_step()
    _placed(game, vampire)
    move_to_zone(game, bloodthief, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, bloodthief, Zone.EXILE, Zone.BATTLEFIELD)
    resolve_top_of_stack(game)
    assert _counters(vampire) == 1


def test_bloodthief_does_nothing_once_its_vampire_is_no_longer_its_controllers():
    game, bloodthief, vampire = _bloodthief_at_end_step()
    _placed(game, vampire)
    vampire.controller = game.players[1]
    resolve_top_of_stack(game)
    assert _counters(vampire) == 0


def test_bloodthief_does_not_trigger_in_the_end_step_of_a_player_who_does_not_control_it():
    game, bloodthief, vampire = _bloodthief_at_end_step(source_controller_seat=1)
    assert game.stack.is_empty()
