"""A player orders their own triggered abilities that trigger together
through an ordering Player Query (CR 603.3b; DECISION-MODEL.md › Player Query).

Run inside ``known_best/workspace`` by ``tests/test_known_best_combat_queries.py``:
the module imports the workspace's ``engine`` and ``test_utils``, which the repo
suite cannot import in-process alongside other workspaces.
"""

from __future__ import annotations

from engine.card import Creature
from engine.decisions import Decision, DecisionKind, GameRef
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import ManaCost, Zone
from test_utils import Intent, create_game, set_board_state


class Bear(Creature):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Bear")
        super().__init__(mana_cost=ManaCost(), base_power=2, base_toughness=2, **kwargs)


class BearAbility1:
    """When an upkeep begins, nothing happens."""


class BearAbility2:
    """When an upkeep begins, nothing else happens."""


def _upkeep_trigger(source, controller, printed=None) -> TriggerRegistration:
    return TriggerRegistration(
        event_type=BeginningOfUpkeepTriggeredEvent, condition=None,
        effect=lambda game: None, source=source, controller=controller, printed=printed,
    )


def _game(*sources_by_seat):
    game = create_game()
    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef()))
    for seat, sources in enumerate(sources_by_seat):
        set_board_state(game, seat, battlefield=[s for s in sources if s is not None])
    return game


def _orderings(player):
    return [
        r for r in player.transcript.all()
        if r.options and all(o.kind is DecisionKind.ABILITY for o in r.options)
        and r.min == r.max == len(r.options)
    ]


def _fire(game):
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())


def test_the_controller_orders_two_triggers_and_the_first_chosen_goes_on_the_stack_first():
    bear, cub = Bear(), Bear(name="Cub")
    game = _game([bear, cub])
    p0 = game.players[0]
    for source in (bear, cub):
        game.trigger_manager.register(_upkeep_trigger(source, p0))
    cub_first = Decision.ability(source=game.refs.instance_id(cub, Zone.BATTLEFIELD.value))
    p0.set_baseline(Intent(pattern=GameRef(), preferences=(cub_first,)))
    _fire(game)
    assert len(_orderings(p0)) == 1
    # Top first: the Cub's ability went on first, so the Bear's is on top.
    assert [o.source for o in game.stack.objects()] == [bear, cub]


def test_by_default_the_offered_order_is_registration_order():
    bear, cub = Bear(), Bear(name="Cub")
    game = _game([bear, cub])
    p0 = game.players[0]
    for source in (bear, cub):
        game.trigger_manager.register(_upkeep_trigger(source, p0))
    _fire(game)
    assert [o.source for o in game.stack.objects()] == [cub, bear]


def test_a_single_trigger_raises_no_ordering_query():
    bear = Bear()
    game = _game([bear])
    game.trigger_manager.register(_upkeep_trigger(bear, game.players[0]))
    _fire(game)
    assert _orderings(game.players[0]) == [] and len(game.stack.objects()) == 1


def test_each_player_orders_only_their_own_after_apnap():
    bear, cub, hawk = Bear(), Bear(name="Cub"), Bear(name="Hawk")
    game = _game([bear, cub], [hawk])
    p0, p1 = game.players
    for source, controller in ((bear, p0), (cub, p0), (hawk, p1)):
        game.trigger_manager.register(_upkeep_trigger(source, controller))
    _fire(game)
    assert len(_orderings(p0)) == 1 and _orderings(p1) == []
    # The active player's go on the stack first, the other player's on top.
    assert game.stack.objects()[0].source is hawk


def test_two_triggers_of_one_source_are_told_apart_by_index():
    bear = Bear()
    game = _game([bear])
    p0 = game.players[0]
    game.trigger_manager.register(_upkeep_trigger(bear, p0))
    game.trigger_manager.register(_upkeep_trigger(bear, p0))
    _fire(game)
    (ordering,) = _orderings(p0)
    assert sorted(dict(o.attrs)["index"] for o in ordering.options) == [0, 1]
    assert len(game.stack.objects()) == 2


def test_a_trigger_is_offered_and_chosen_by_its_printed_ability_class():
    bear = Bear()
    game = _game([bear])
    p0 = game.players[0]
    game.trigger_manager.register(_upkeep_trigger(bear, p0, BearAbility1))
    game.trigger_manager.register(_upkeep_trigger(bear, p0, BearAbility2))
    p0.set_baseline(Intent(pattern=GameRef(), preferences=(Decision.ability(printed=BearAbility2),)))
    _fire(game)
    (ordering,) = _orderings(p0)
    assert [dict(o.attrs)["printed"] for o in ordering.options] == [BearAbility1, BearAbility2]
    # Top first: the second ability went on first, so the first is on top.
    assert [o.printed for o in game.stack.objects()] == [BearAbility1, BearAbility2]



def _attack_trigger(source, controller) -> TriggerRegistration:
    from engine.events import AttacksTriggeredEvent

    return TriggerRegistration(
        event_type=AttacksTriggeredEvent,
        condition=lambda game, event, _s=source: event.attacker is _s,
        effect=lambda game: None, source=source, controller=controller,
    )


def test_triggers_from_simultaneous_attacks_are_ordered_as_one_batch():
    from engine.combat import declare_attackers_step
    from engine.types import Phase, Step
    from test_utils import act, script

    bear, cub = Bear(), Bear(name="Cub")
    game = _game([bear, cub])
    p0 = game.players[0]
    for source in (bear, cub):
        source.summoning_sick = False
        game.trigger_manager.register(_attack_trigger(source, p0))
    game.active_player_index = game.priority_player_index = 0
    game.phase, game.step = Phase.COMBAT, Step.DECLARE_ATTACKERS
    cub_first = Decision.ability(source=game.refs.instance_id(cub, Zone.BATTLEFIELD.value))
    p0.set_baseline(Intent(pattern=GameRef(), preferences=(cub_first,)))
    script(game, 0, act(*(
        Decision.obj(instance=game.refs.instance_id(c, Zone.BATTLEFIELD.value)) for c in (bear, cub)
    )))
    declare_attackers_step(game)
    # Both attack at once (rule 508.1), so their triggers are one ordering
    # (rule 603.3b): the Cub's, chosen first, goes on first.
    assert len(_orderings(p0)) == 1
    assert [o.source for o in game.stack.objects()] == [bear, cub]
