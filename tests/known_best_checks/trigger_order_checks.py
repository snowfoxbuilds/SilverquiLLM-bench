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
    """Fire an upkeep and settle, as the game does before priority (CR 117.5)."""
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    game.trigger_manager.put_pending_on_stack(game)


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


class _Entrant(Creature):
    """A 2/2 with "When this creature enters, nothing happens."."""

    def __init__(self, **kwargs) -> None:
        super().__init__(mana_cost=ManaCost(), base_power=2, base_toughness=2, **kwargs)

    def register_triggers(self, game) -> None:
        from engine.events import EntersBattlefieldTriggeredEvent

        game.trigger_manager.register(TriggerRegistration(
            event_type=EntersBattlefieldTriggeredEvent,
            condition=lambda game, event, _s=self: event.permanent is _s,
            effect=lambda game: None, source=self, controller=self.controller,
        ))


def test_abilities_triggered_during_one_resolution_are_ordered_together():
    from engine.stack import StackObject, resolve_top_of_stack
    from engine.zones import move_to_zone

    game = _game([])
    p0 = game.players[0]
    first, second = _Entrant(name="First", owner=p0, controller=p0), _Entrant(name="Second", owner=p0, controller=p0)
    for card in (first, second):
        p0.zones[Zone.HAND].add(card)

    def _put_both_onto_the_battlefield(game) -> None:
        for card in (first, second):
            move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)

    game.stack.push(StackObject(source=Bear(owner=p0, controller=p0), controller=p0,
                                on_resolve=_put_both_onto_the_battlefield))
    resolve_top_of_stack(game)
    (ordering,) = _orderings(p0)
    assert len(ordering.options) == 2
    assert {o.source for o in game.stack.objects()} == {first, second}


def test_the_active_player_places_all_of_theirs_before_the_other_player_orders():
    bear, cub, hawk, owl = Bear(), Bear(name="Cub"), Bear(name="Hawk"), Bear(name="Owl")
    game = _game([bear, cub], [hawk, owl])
    p0, p1 = game.players
    for source, controller in ((bear, p0), (cub, p0), (hawk, p1), (owl, p1)):
        game.trigger_manager.register(_upkeep_trigger(source, controller))
    seen: list[set] = []
    answer = p1.answer

    def _answer(query):
        if query.options and all(o.kind is DecisionKind.ABILITY for o in query.options):
            seen.append({o.source for o in game.stack.objects()})
        return answer(query)

    p1.answer = _answer
    _fire(game)
    assert seen == [{bear, cub}]
    assert [o.source for o in game.stack.objects()][:2] == [owl, hawk]


def test_an_occurrence_waits_for_the_game_to_settle_and_keeps_its_fire_time_facts():
    from engine.stack import battlefield_stint_id
    from engine.zones import move_to_zone

    bear = Bear()
    game = _game([bear])
    p0 = game.players[0]
    game.trigger_manager.register(TriggerRegistration(
        event_type=BeginningOfUpkeepTriggeredEvent, condition=None,
        effect=lambda game, controller, stint: None, source=bear, controller=p0,
        capture=lambda game, event, controller: battlefield_stint_id(game, bear),
    ))
    stint = battlefield_stint_id(game, bear)
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    assert game.stack.is_empty() and game.trigger_manager.has_pending()
    move_to_zone(game, bear, Zone.BATTLEFIELD, Zone.HAND)
    move_to_zone(game, bear, Zone.HAND, Zone.BATTLEFIELD)
    game.trigger_manager.put_pending_on_stack(game)
    (obj,) = game.stack.objects()
    assert obj.event_state == stint and not game.trigger_manager.has_pending()


def test_a_rejected_trigger_target_rolls_back_only_that_players_placement():
    from engine.decisions import InvalidPlayerChoiceError
    from engine.queries import PlayerQuery, ask
    from test_utils import branch

    bear, cub = Bear(), Bear(name="Cub")
    game = _game([bear], [cub])
    p0, p1 = game.players
    tries: list[int] = []

    def _targeting(game, event, controller):
        tries.append(len(game.stack.objects()))
        options = tuple(game.refs.object_decision(c, zone=Zone.BATTLEFIELD.value) for c in (bear, cub))
        answer = ask(controller, PlayerQuery(source=(), prompt="target", options=options, min=1, max=1))
        chosen = game.refs.object_for(answer.selected[0])
        if chosen is bear:
            raise InvalidPlayerChoiceError("the Bear is not a legal target")
        return [chosen]

    game.trigger_manager.register(_upkeep_trigger(bear, p0))
    game.trigger_manager.register(TriggerRegistration(
        event_type=BeginningOfUpkeepTriggeredEvent, condition=None,
        effect=lambda game, targets, context: None, source=cub, controller=p1,
        targeting=_targeting,
    ))
    bear_ref = Decision.obj(instance=game.refs.instance_id(bear, Zone.BATTLEFIELD.value))
    cub_ref = Decision.obj(instance=game.refs.instance_id(cub, Zone.BATTLEFIELD.value))
    p1.set_baseline(Intent(pattern=GameRef(), branches=(branch(bear_ref), branch(cub_ref))))
    _fire(game)
    # The target was asked again over the active player's one ability, as
    # the rollback left it; nothing was duplicated or lost.
    assert tries == [1]  # the rollback restored the first try's record
    assert [r.query.prompt for r in p1.transcript.all()].count("target") == 2
    (top, bottom) = game.stack.objects()
    assert (top.source, top.targets, bottom.source) == (cub, [cub], bear)
    assert not game.trigger_manager.has_pending()


# ---------------------------------------------------------------------------
# A game a state-based action ends places nothing more (CR 104.2a, 104.4a)
# ---------------------------------------------------------------------------


def _damage_trigger(source, controller, *, targeting=None) -> TriggerRegistration:
    from engine.events import DealsDamageTriggeredEvent

    return TriggerRegistration(
        event_type=DealsDamageTriggeredEvent,
        condition=lambda game, event, _s=source: getattr(event, "source", None) is _s,
        effect=(lambda game, targets, context: None) if targeting else (lambda game: None),
        source=source, controller=controller, targeting=targeting,
    )


def _unblocked_attack(game, attacker, defender_life):
    from engine.combat import combat_damage_step, declare_attackers_step
    from engine.types import Phase, Step
    from test_utils import act, script

    game.players[1].life = defender_life
    attacker.summoning_sick = False
    game.active_player_index = game.priority_player_index = 0
    game.phase, game.step = Phase.COMBAT, Step.DECLARE_ATTACKERS
    script(game, 0, act(Decision.obj(instance=game.refs.instance_id(attacker, Zone.BATTLEFIELD.value))))
    declare_attackers_step(game)
    asked = len(game.players[0].transcript.all())
    combat_damage_step(game)
    return game.players[0].transcript.all()[asked:]


def test_lethal_combat_damage_ends_the_game_before_its_triggers_are_ordered():
    bear = Bear()
    game = _game([bear])
    p0 = game.players[0]
    for _ in range(2):
        game.trigger_manager.register(_damage_trigger(bear, p0))
    questions = _unblocked_attack(game, bear, 2)
    assert game.is_game_over and game.winner is p0
    assert _orderings(p0) == [] and questions == []
    assert game.stack.is_empty() and not game.trigger_manager.has_pending()


def test_lethal_combat_damage_chooses_no_target_for_a_waiting_targeted_trigger():
    bear = Bear()
    game = _game([bear])
    p0 = game.players[0]
    chosen: list[int] = []

    def _targeting(game, event, controller):
        chosen.append(1)
        return [game.players[1]]

    game.trigger_manager.register(_damage_trigger(bear, p0, targeting=_targeting))
    _unblocked_attack(game, bear, 2)
    assert game.is_game_over and chosen == [] and game.stack.is_empty()


def test_a_lethal_spell_ends_the_game_before_a_trigger_it_caused_goes_on_the_stack():
    from engine.stack import StackObject, resolve_top_of_stack

    bear = Bear()
    game = _game([bear])
    p0, p1 = game.players
    game.trigger_manager.register(_upkeep_trigger(bear, p0))
    game.trigger_manager.register(_upkeep_trigger(bear, p0))

    def _bolt(game) -> None:
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        p1.life -= 3

    p1.life = 3
    game.stack.push(StackObject(source=Bear(owner=p0, controller=p0), controller=p0, on_resolve=_bolt))
    resolve_top_of_stack(game)
    assert game.is_game_over and game.winner is p0
    assert _orderings(p0) == [] and game.stack.is_empty()


def test_simultaneous_losses_are_a_draw_and_place_nothing():
    from engine.state_based_actions import resolve_state_based_actions

    bear = Bear()
    game = _game([bear])
    p0, p1 = game.players
    for _ in range(2):
        game.trigger_manager.register(_upkeep_trigger(bear, p0))
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    p0.life = p1.life = 0
    resolve_state_based_actions(game)
    assert game.is_game_over and game.winner is None
    assert _orderings(p0) == [] and game.stack.is_empty()


def test_lethal_first_strike_damage_leaves_no_regular_damage_pass():
    from engine.combat import combat_damage_step, declare_attackers_step
    from engine.events import DealsDamageTriggeredEvent
    from engine.types import Keyword, Phase, Step
    from test_utils import act, script

    striker, bear = Bear(name="Striker"), Bear()
    striker.keywords = striker.keywords | Keyword.FIRST_STRIKE
    game = _game([striker, bear])
    p0, p1 = game.players
    dealt: list[object] = []
    game.trigger_manager.register(TriggerRegistration(
        event_type=DealsDamageTriggeredEvent,
        condition=lambda game, event: dealt.append(event.source) or False,
        effect=lambda game: None, source=bear, controller=p0,
    ))

    p1.life = 2
    for c in (striker, bear):
        c.summoning_sick = False
    game.active_player_index = game.priority_player_index = 0
    game.phase, game.step = Phase.COMBAT, Step.DECLARE_ATTACKERS
    script(game, 0, act(*(Decision.obj(instance=game.refs.instance_id(c, Zone.BATTLEFIELD.value)) for c in (striker, bear))))
    declare_attackers_step(game)
    combat_damage_step(game)
    assert game.is_game_over and game.winner is p0
    assert bear not in dealt and p1.life == 0


def test_nonlethal_settling_still_orders_the_waiting_triggers():
    from engine.state_based_actions import resolve_state_based_actions

    bear, cub = Bear(), Bear(name="Cub")
    game = _game([bear, cub])
    p0 = game.players[0]
    for source in (bear, cub):
        game.trigger_manager.register(_upkeep_trigger(source, p0))
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    game.players[1].life = 1
    resolve_state_based_actions(game)
    assert not game.is_game_over and len(_orderings(p0)) == 1 and len(game.stack.objects()) == 2


# ---------------------------------------------------------------------------
# An occurrence keeps its source's identity from when it triggered (CR 400.7)
# ---------------------------------------------------------------------------


def _counter_on_own_source(source, controller, hits) -> TriggerRegistration:
    """A targeted upkeep trigger whose effect touches its own source — here,
    records a hit — only if the source is still the object that triggered."""
    from engine.stack import same_stint

    def _effect(game, targets, context, _s=source):
        if same_stint(game, _s, context.source_instance_id):
            hits.append(_s)

    return TriggerRegistration(
        event_type=BeginningOfUpkeepTriggeredEvent, condition=None, effect=_effect,
        source=source, controller=controller, targeting=lambda game, event, controller: [game.players[1]],
    )


def _blink(game, card):
    from engine.zones import move_to_zone

    move_to_zone(game, card, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, card, Zone.EXILE, Zone.BATTLEFIELD)


def _resolve_all(game):
    from engine.stack import resolve_top_of_stack

    while not game.stack.is_empty():
        resolve_top_of_stack(game)


def test_a_source_that_leaves_and_returns_before_placement_is_a_new_object():
    bear = Bear()
    game = _game([bear])
    p0 = game.players[0]
    hits: list[object] = []
    game.trigger_manager.register(_counter_on_own_source(bear, p0, hits))
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    _blink(game, bear)
    game.trigger_manager.put_pending_on_stack(game)
    _resolve_all(game)
    assert hits == []


def test_a_source_that_stays_gets_its_counter():
    bear = Bear()
    game = _game([bear])
    hits: list[object] = []
    game.trigger_manager.register(_counter_on_own_source(bear, game.players[0], hits))
    _fire(game)
    _resolve_all(game)
    assert hits == [bear]


def test_a_source_that_left_for_good_is_no_longer_the_triggering_object():
    from engine.stack import battlefield_stint_id, same_stint
    from engine.zones import move_to_zone

    bear = Bear()
    game = _game([bear])
    hits: list[object] = []
    game.trigger_manager.register(_counter_on_own_source(bear, game.players[0], hits))
    fired_as = battlefield_stint_id(game, bear)
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    move_to_zone(game, bear, Zone.BATTLEFIELD, Zone.EXILE)
    game.trigger_manager.put_pending_on_stack(game)
    (obj,) = game.stack.objects()
    assert obj.activation_context.source_instance_id == fired_as
    assert not same_stint(game, bear, fired_as)
    _resolve_all(game)
    assert hits == []


def test_occurrences_from_two_stints_of_one_card_keep_their_own_stints():
    from engine.stack import battlefield_stint_id

    bear = Bear()
    game = _game([bear])
    hits: list[object] = []
    game.trigger_manager.register(_counter_on_own_source(bear, game.players[0], hits))
    first = battlefield_stint_id(game, bear)
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    _blink(game, bear)
    # The returned card is a new object with its abilities registered anew.
    game.trigger_manager.register(_counter_on_own_source(bear, game.players[0], hits))
    second = battlefield_stint_id(game, bear)
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    game.trigger_manager.put_pending_on_stack(game)
    stints = sorted(o.activation_context.source_instance_id for o in game.stack.objects())
    assert stints == sorted([first, second]) and first != second
    _resolve_all(game)
    assert hits == [bear]


def test_an_occurrence_offered_for_ordering_names_its_source_as_it_triggered():
    bear, cub = Bear(), Bear(name="Cub")
    game = _game([bear, cub])
    p0 = game.players[0]
    for source in (bear, cub):
        game.trigger_manager.register(_upkeep_trigger(source, p0))
    fired_as = game.refs.instance_id(bear, Zone.BATTLEFIELD.value)
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    _blink(game, bear)
    game.trigger_manager.put_pending_on_stack(game)
    (ordering,) = _orderings(p0)
    assert fired_as in {dict(o.attrs)["source"] for o in ordering.options}
