"""Combat declarations as Player Queries in the Known-Best Workspace
(DECISION-MODEL.md › Priority actions › Options › Combat declarations).

Run inside ``known_best/workspace`` by ``tests/test_known_best_combat_queries.py``:
the module imports the workspace's ``engine`` and ``test_utils``, which the repo
suite cannot import in-process alongside other workspaces.
"""

from __future__ import annotations

import pytest
from engine.card import Creature, Planeswalker
from engine.combat import combat_damage_step, declare_attackers_step, declare_blockers_step
from engine.decisions import Decision, GameRef, InvalidPlayerChoiceError, PostconditionError
from engine.queries import (
    DECLARE_ATTACKERS_WINDOW,
    DECLARE_BLOCKERS_WINDOW,
    declaration_pattern,
    is_declaration_query,
)
from engine.types import Keyword, ManaCost, Phase, Step, Zone
from test_utils import (
    Intent,
    ScriptEntryError,
    act,
    act_illegal,
    branch,
    create_game,
    declare_attackers,
    declare_blockers,
    pass_priority,
    run_scripts,
    script,
    set_board_state,
    TestSetupError,
)


class Bear(Creature):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Bear")
        super().__init__(mana_cost=ManaCost(), base_power=2, base_toughness=2, **kwargs)


class Hawk(Creature):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Hawk", mana_cost=ManaCost(), base_power=1, base_toughness=1,
            keywords=Keyword.FLYING, **kwargs,
        )


class Brute(Creature):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Brute", mana_cost=ManaCost(), base_power=3, base_toughness=3,
            keywords=Keyword.MENACE, **kwargs,
        )


class Trampler(Creature):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Trampler", mana_cost=ManaCost(), base_power=6, base_toughness=6,
            keywords=Keyword.TRAMPLE, **kwargs,
        )


class Walker(Planeswalker):
    def __init__(self, **kwargs) -> None:
        super().__init__(starting_loyalty=5, name="Walker", mana_cost=ManaCost(), **kwargs)


def _game():
    game = create_game()
    for player in game.players:
        player.drawn_from_empty_library = False
    game.active_player_index = game.priority_player_index = 0
    game.phase, game.step = Phase.COMBAT, Step.DECLARE_ATTACKERS
    return game


def _ready(*creatures):
    for creature in creatures:
        creature.summoning_sick = False
    return creatures


def _declarations(player, window):
    return [
        r for r in player.transcript.all()
        if is_declaration_query(r.query)
        and any(window in s.ref.ability for s in r.query.source if s.ref is not None)
    ]


def _attack(game, *attackers):
    """Register *attackers* through a scripted declaration."""
    script(game, 0, act(*attackers))
    declare_attackers_step(game)


# ---------------------------------------------------------------------------
# Declaring attackers
# ---------------------------------------------------------------------------


def test_offered_attackers_carry_their_printed_class():
    game = _game()
    bear, hawk = _ready(Bear(), Hawk())
    set_board_state(game, 0, battlefield=[bear, hawk])
    declare_attackers_step(game)
    (record,) = _declarations(game.players[0], DECLARE_ATTACKERS_WINDOW)
    assert {dict(o.attrs)["printed"] for o in record.options} == {Bear, Hawk}
    assert record.min == 0 and record.max == 2


def test_a_dry_script_declares_no_attackers():
    game = _game()
    (bear,) = _ready(Bear())
    set_board_state(game, 0, battlefield=[bear])
    declare_attackers_step(game)
    assert game.combat_state.attackers == {}
    assert len(_declarations(game.players[0], DECLARE_ATTACKERS_WINDOW)) == 1


def test_act_declares_the_attackers_by_printed_class():
    game = _game()
    bear, hawk = _ready(Bear(), Hawk())
    set_board_state(game, 0, battlefield=[bear, hawk])
    script(game, 0, act(Hawk, goal=lambda g: hawk.is_attacking))
    declare_attackers_step(game)
    assert list(game.combat_state.attackers) == [hawk]
    assert hawk.is_tapped and not bear.is_attacking


def test_an_illegal_attacker_is_rejected_never_trimmed():
    game = _game()
    (bear,) = _ready(Bear())
    sick = Hawk()
    sick.summoning_sick = True
    set_board_state(game, 0, battlefield=[bear, sick])
    script(game, 0, act(Bear, Hawk))
    with pytest.raises(ScriptEntryError) as excinfo:
        declare_attackers_step(game)
    assert excinfo.value.reason == "rejected"
    assert isinstance(excinfo.value.error, InvalidPlayerChoiceError)
    assert game.combat_state.attackers == {}
    assert not bear.is_tapped and not bear.is_attacking


def test_a_rejected_declaration_is_asked_again():
    game = _game()
    (bear,) = _ready(Bear())
    sick = Hawk()
    sick.summoning_sick = True
    set_board_state(game, 0, battlefield=[bear, sick])
    script(game, 0, act_illegal(Bear, Hawk), act(Bear))
    declare_attackers_step(game)
    assert list(game.combat_state.attackers) == [bear]
    assert len(_declarations(game.players[0], DECLARE_ATTACKERS_WINDOW)) == 2


def test_a_rejected_declaration_retries_the_entrys_next_branch():
    game = _game()
    (bear,) = _ready(Bear())
    sick = Hawk()
    sick.summoning_sick = True
    set_board_state(game, 0, battlefield=[bear, sick])
    script(game, 0, act(branches=[[Bear, Hawk], [Bear]]))
    declare_attackers_step(game)
    assert list(game.combat_state.attackers) == [bear]
    assert len(_declarations(game.players[0], DECLARE_ATTACKERS_WINDOW)) == 2


def test_per_query_answers_a_declaration():
    game = _game()
    bear, hawk = _ready(Bear(), Hawk())
    set_board_state(game, 0, battlefield=[bear, hawk])
    script(game, 0, act(branches=[branch(Hawk, per_query={is_declaration_query: [Bear]})]))
    declare_attackers_step(game)
    assert list(game.combat_state.attackers) == [bear]


def test_a_declaration_retry_starts_from_the_restored_boundary():
    from engine.game import gain_life

    game = _game()
    (bear,) = _ready(Bear())
    sick = Hawk()
    sick.summoning_sick = True
    set_board_state(game, 0, battlefield=[bear, sick])
    p0 = game.players[0]
    original = p0.on_attempt_rejected

    def mutate_then_hear(context, answer, error):
        verdict = original(context, answer, error)
        gain_life(game, p0, 7)
        return verdict

    p0.on_attempt_rejected = mutate_then_hear
    script(game, 0, act(branches=[[Bear, Hawk], [Bear]]))
    declare_attackers_step(game)
    assert list(game.combat_state.attackers) == [bear] and p0.life == 20


def test_a_branch_with_a_creature_not_offered_is_skipped():
    game = _game()
    (bear,) = _ready(Bear())
    set_board_state(game, 0, battlefield=[bear])
    script(game, 0, act(branches=[[Hawk], [Bear]]))
    declare_attackers_step(game)
    assert list(game.combat_state.attackers) == [bear]


def test_act_illegal_passes_when_the_attacker_is_not_offered():
    game = _game()
    tapped = Bear()
    tapped.is_tapped = True
    set_board_state(game, 0, battlefield=[tapped, *_ready(Hawk())])
    script(game, 0, act_illegal(Bear))
    declare_attackers_step(game)
    assert game.combat_state.attackers == {}


def test_act_illegal_fails_when_the_declaration_takes_effect():
    game = _game()
    set_board_state(game, 0, battlefield=list(_ready(Bear())))
    script(game, 0, act_illegal(Bear))
    with pytest.raises(ScriptEntryError) as excinfo:
        declare_attackers_step(game)
    assert excinfo.value.reason == "took effect"


def test_an_attacker_may_attack_a_planeswalker():
    game = _game()
    bear, hawk = _ready(Bear(), Hawk())
    walker = Walker()
    set_board_state(game, 0, battlefield=[bear, hawk])
    set_board_state(game, 1, battlefield=[walker])
    script(game, 0, act(Bear, Hawk, scoped={Bear: Walker, Hawk: Decision.player(seat=1)}))
    declare_attackers_step(game)
    assert game.combat_state.attackers == {bear: walker, hawk: game.players[1]}
    defender_queries = [
        r for r in game.players[0].transcript.all()
        if r.query.prompt.startswith("choose what")
    ]
    assert len(defender_queries) == 2
    assert {o.kind.name for o in defender_queries[0].options} == {"PLAYER", "OBJECT"}

    combat_damage_step(game)
    assert walker.loyalty == 3
    assert game.players[1].life == 19


def test_declare_attackers_helper_attacks_the_player_past_a_planeswalker():
    game = _game()
    (bear,) = _ready(Bear())
    set_board_state(game, 0, battlefield=[bear])
    set_board_state(game, 1, battlefield=[Walker()])
    declare_attackers(game, ["Bear"])
    assert game.combat_state.attackers == {bear: game.players[1]}


def test_declare_attackers_helper_surfaces_a_rejection():
    game = _game()
    sick = Bear()
    sick.summoning_sick = True
    set_board_state(game, 0, battlefield=[sick])
    with pytest.raises(ScriptEntryError):
        declare_attackers(game, ["Bear"])
    declare_attackers(game, ["Bear"], illegal=True)
    assert game.combat_state.attackers == {}


# ---------------------------------------------------------------------------
# Declaring blockers
# ---------------------------------------------------------------------------


def _blocking_game(attacker, *blockers):
    game = _game()
    _ready(attacker, *blockers)
    set_board_state(game, 0, battlefield=[attacker])
    set_board_state(game, 1, battlefield=list(blockers))
    _attack(game, type(attacker))
    game.step = Step.DECLARE_BLOCKERS
    return game


def test_offered_blockers_carry_their_printed_class():
    game = _blocking_game(Bear(), Hawk(), Bear(name="Cub"))
    declare_blockers_step(game)
    (record,) = _declarations(game.players[1], DECLARE_BLOCKERS_WINDOW)
    assert [dict(o.attrs)["printed"] for o in record.options] == [Hawk, Bear]
    assert game.combat_state.blockers == {}


def test_act_declares_blocks_scoped_by_blocker():
    attacker, blocker = Bear(), Hawk()
    game = _blocking_game(attacker, blocker)
    script(game, 1, act(Hawk, scoped={Hawk: Bear}))
    declare_blockers_step(game)
    assert game.combat_state.blockers == {blocker: [attacker]}
    assert game.combat_state.attacker_blockers[attacker] == [blocker]
    assert attacker in game.combat_state.was_blocked


def test_a_flyer_cannot_be_blocked_by_a_ground_creature():
    attacker, ground = Hawk(), Bear()
    game = _blocking_game(attacker, ground)
    script(game, 1, act_illegal(Bear, scoped={Bear: Hawk}))
    declare_blockers_step(game)
    assert game.combat_state.blockers == {}
    assert not ground.is_blocking
    assert len(_declarations(game.players[1], DECLARE_BLOCKERS_WINDOW)) == 2

    script(game, 1, act(Bear, scoped={Bear: Hawk}))
    with pytest.raises(ScriptEntryError) as excinfo:
        declare_blockers_step(game)
    assert excinfo.value.reason == "rejected"


def test_a_single_block_of_a_menace_attacker_is_rejected():
    attacker, b1, b2 = Brute(), Bear(), Bear(name="Cub")
    game = _blocking_game(attacker, b1, b2)
    lone = Decision.obj(instance=game.refs.instance_id(b1, Zone.BATTLEFIELD.value))
    script(game, 1, act_illegal(lone, scoped={lone: Brute}))
    declare_blockers_step(game)
    assert game.combat_state.blockers == {}
    assert game.combat_state.attacker_blockers[attacker] == []


def test_two_blockers_satisfy_menace_and_the_attacker_divides_its_damage():
    attacker, b1, b2 = Brute(), Bear(), Bear(name="Cub")
    game = _blocking_game(attacker, b1, b2)
    declare_blockers(game, {"Brute": ["Bear", "Cub"]})
    assert game.combat_state.attacker_blockers[attacker] == [b1, b2]
    bear = Decision.obj(instance=game.refs.instance_id(b1, Zone.BATTLEFIELD.value))
    game.players[0].set_baseline(Intent(pattern=GameRef(), per_query={bear: [Decision.number(1)]}))
    combat_damage_step(game)
    # The first blocker is asked its share; the last takes the rest unasked.
    (division,) = [r for r in game.players[0].transcript.all() if r.query.question]
    assert division.query.question == (division.query.question[0],)
    assert dict(division.query.question[0].attrs)["printed"] is Bear
    # The Brute dies to the blockers' 4 damage; the Bear survives its 1, the Cub dies to its 2.
    assert b1.damage_marked == 1
    assert game.players[1].zones[Zone.GRAVEYARD].contains(b2)


def test_a_trampler_assigns_past_its_blockers_only_once_each_has_lethal_damage():
    trampler, b1, b2 = Trampler(), Bear(), Bear(name="Cub")
    game = _blocking_game(trampler, b1, b2)
    declare_blockers(game, {"Trampler": ["Bear", "Cub"]})
    first, second = (
        Decision.obj(instance=game.refs.instance_id(b, Zone.BATTLEFIELD.value)) for b in (b1, b2)
    )
    # 1 to the first blocker leaves it short of lethal, so trampling over is
    # rejected; the baseline's next branch gives each blocker lethal damage.
    game.players[0].set_baseline(Intent(pattern=GameRef(), branches=[
        branch(per_query={first: [Decision.number(1)], second: [Decision.number(2)]}),
        branch(per_query={first: [Decision.number(2)], second: [Decision.number(2)]}),
    ]))
    combat_damage_step(game)
    assert game.combat_state.damage_assignments[trampler] == [(b1, 2), (b2, 2), (game.players[1], 2)]
    assert game.players[1].life == 18


@pytest.mark.parametrize("power", [0, -2])
def test_an_attacker_with_no_power_divides_nothing(power):
    attacker, b1, b2 = Brute(), Bear(), Bear(name="Cub")
    attacker.base_power = attacker.modified_power = power
    game = _blocking_game(attacker, b1, b2)
    declare_blockers(game, {"Brute": ["Bear", "Cub"]})
    combat_damage_step(game)
    # It assigns no combat damage (rule 510.1a), so nothing is asked.
    assert not [r for r in game.players[0].transcript.all() if r.query.question]
    assert b1.damage_marked == b2.damage_marked == 0


def test_declare_blockers_helper_with_an_illegal_block():
    attacker, ground = Hawk(), Bear()
    game = _blocking_game(attacker, ground)
    with pytest.raises(ScriptEntryError):
        declare_blockers(game, {"Hawk": ["Bear"]})
    declare_blockers(game, {"Hawk": ["Bear"]}, illegal=True)
    assert game.combat_state.blockers == {}


def test_a_card_intent_can_answer_a_declaration():
    attacker, blocker = Bear(), Hawk()
    game = _blocking_game(attacker, blocker)
    # The baseline answers what the blocker blocks: the only attacker.
    game.players[1].set_baseline(Intent(pattern=GameRef()))
    game.players[1].start_intent(
        "block",
        Intent(
            pattern=declaration_pattern(DECLARE_BLOCKERS_WINDOW, seat=1),
            preferences=(Decision.obj(printed=Hawk),),
        ),
    )
    declare_blockers_step(game)
    assert game.combat_state.blockers == {blocker: [attacker]}


# ---------------------------------------------------------------------------
# Scripts across combat
# ---------------------------------------------------------------------------


def test_declarations_consume_script_entries_in_run_scripts():
    game = _game()
    game.phase, game.step = Phase.PRECOMBAT_MAIN, None
    attacker, blocker = _ready(Bear(), Hawk())
    set_board_state(game, 0, battlefield=[attacker])
    set_board_state(game, 1, battlefield=[blocker])
    # Main phase and beginning of combat priority, then the attack declaration.
    script(game, 0, pass_priority(), pass_priority(), act(Bear))
    # Main phase, beginning of combat and declare attackers priority, then the
    # block declaration.
    script(
        game, 1, pass_priority(), pass_priority(), pass_priority(), act(Hawk, scoped={Hawk: Bear})
    )
    run_scripts(game)
    assert (game.phase, game.step) == (Phase.COMBAT, Step.DECLARE_BLOCKERS)
    assert game.combat_state.blockers == {blocker: [attacker]}


# ---------------------------------------------------------------------------
# Scoped answers are exact
# ---------------------------------------------------------------------------


def _ref(game, creature):
    return Decision.obj(instance=game.refs.instance_id(creature, Zone.BATTLEFIELD.value))


def _two_attackers_one_blocker(blocker):
    """Bear and Cub attack; *blocker* defends; Hawk stays home."""
    game = _game()
    bear, cub, hawk = _ready(Bear(), Bear(name="Cub"), Hawk())
    _ready(blocker)
    set_board_state(game, 0, battlefield=[bear, cub, hawk])
    set_board_state(game, 1, battlefield=[blocker])
    script(game, 0, act(_ref(game, bear), _ref(game, cub)))
    declare_attackers_step(game)
    game.step = Step.DECLARE_BLOCKERS
    return game, bear, cub, hawk


def _unchanged(game, *blockers):
    assert game.combat_state.blockers == {}
    assert all(not b.is_blocking for b in blockers)
    assert all(blockers_of == [] for blockers_of in game.combat_state.attacker_blockers.values())


def test_a_block_of_a_creature_that_is_not_attacking_is_not_substituted():
    brute = Brute()
    game, bear, _cub, hawk = _two_attackers_one_blocker(brute)
    script(game, 1, act(Brute, scoped={Brute: _ref(game, hawk)}))
    with pytest.raises(ScriptEntryError) as excinfo:
        declare_blockers_step(game)
    assert excinfo.value.reason == "not offered"
    _unchanged(game, brute)


def test_an_unavailable_illegal_block_is_consumed_and_the_next_entry_declares():
    brute = Brute()
    game, bear, _cub, hawk = _two_attackers_one_blocker(brute)
    script(
        game, 1,
        act_illegal(Brute, scoped={Brute: _ref(game, hawk)}),
        act(Brute, scoped={Brute: _ref(game, bear)}),
    )
    declare_blockers_step(game)
    assert game.combat_state.blockers == {brute: [bear]}
    assert game.players[1].pending_entries == ()


def test_a_branch_whose_scoped_block_is_unavailable_gives_way_to_the_next():
    brute = Brute()
    game, bear, _cub, hawk = _two_attackers_one_blocker(brute)
    script(game, 1, act(branches=[
        branch(Brute, scoped={Brute: _ref(game, hawk)}),
        branch(Brute, scoped={Brute: _ref(game, bear)}),
    ]))
    declare_blockers_step(game)
    assert game.combat_state.blockers == {brute: [bear]}
    assert game.players[1].pending_entries == ()


def test_too_many_scoped_attackers_are_never_trimmed():
    brute = Brute()
    game, bear, cub, _hawk = _two_attackers_one_blocker(brute)
    both = [_ref(game, bear), _ref(game, cub)]
    script(game, 1, act(Brute, scoped={Brute: both}))
    with pytest.raises(ScriptEntryError) as excinfo:
        declare_blockers_step(game)
    assert excinfo.value.reason == "not offered"
    _unchanged(game, brute)

    script(game, 1, act_illegal(Brute, scoped={Brute: both}))
    declare_blockers_step(game)
    _unchanged(game, brute)


def test_a_blocker_that_may_block_two_attackers_blocks_both():
    brute = Brute()
    brute._max_attackers_blocked = 2
    game, bear, cub, _hawk = _two_attackers_one_blocker(brute)
    script(game, 1, act(Brute, scoped={Brute: [_ref(game, bear), _ref(game, cub)]}))
    declare_blockers_step(game)
    assert game.combat_state.blockers == {brute: [bear, cub]}


def test_a_later_unavailable_scoped_block_commits_none_of_the_declaration():
    game = _game()
    bear, hawk, brute, cub = _ready(Bear(), Hawk(), Brute(), Bear(name="Cub"))
    set_board_state(game, 0, battlefield=[bear, hawk])
    set_board_state(game, 1, battlefield=[brute, cub])
    _attack(game, Bear)
    game.step = Step.DECLARE_BLOCKERS
    entry = {_ref(game, brute): _ref(game, bear), _ref(game, cub): _ref(game, hawk)}
    script(game, 1, act(_ref(game, brute), _ref(game, cub), scoped=entry))
    with pytest.raises(ScriptEntryError):
        declare_blockers_step(game)
    _unchanged(game, brute, cub)


def test_a_scoped_planeswalker_that_is_not_there_is_not_offered():
    game = _game()
    (bear,) = _ready(Bear())
    set_board_state(game, 0, battlefield=[bear])
    script(game, 0, act(Bear, scoped={Bear: Walker}))
    with pytest.raises(ScriptEntryError) as excinfo:
        declare_attackers_step(game)
    assert excinfo.value.reason == "not offered"
    assert game.combat_state.attackers == {} and not bear.is_tapped

    script(game, 0, act_illegal(Bear, scoped={Bear: Walker}), act(Bear))
    declare_attackers_step(game)
    assert game.combat_state.attackers == {bear: game.players[1]}


def test_the_blockers_helper_never_substitutes_an_attacker():
    brute = Brute()
    game, bear, _cub, hawk = _two_attackers_one_blocker(brute)
    with pytest.raises(ScriptEntryError):
        declare_blockers(game, {hawk: [brute]})
    declare_blockers(game, {hawk: [brute]}, illegal=True)
    _unchanged(game, brute)


# ---------------------------------------------------------------------------
# A declaration with nothing to declare still happens
# ---------------------------------------------------------------------------


def test_an_empty_battlefield_still_raises_the_attack_declaration():
    game = _game()
    script(game, 0, act(goal=lambda g: g.combat_state.attackers == {}))
    declare_attackers_step(game)
    assert game.players[0].pending_entries == ()
    (record,) = _declarations(game.players[0], DECLARE_ATTACKERS_WINDOW)
    assert record.options == () and record.max == 0


def test_a_missing_attacker_is_not_offered_when_all_creatures_are_tapped():
    game = _game()
    tapped = Bear()
    tapped.is_tapped = True
    set_board_state(game, 0, battlefield=[tapped])
    script(game, 0, act(Bear))
    with pytest.raises(ScriptEntryError) as excinfo:
        declare_attackers_step(game)
    assert excinfo.value.reason == "not offered"

    script(game, 0, act_illegal(Bear))
    declare_attackers_step(game)
    assert game.players[0].pending_entries == ()
    assert game.combat_state.attackers == {}


def test_an_empty_block_declaration_consumes_its_entry():
    attacker = Bear()
    game = _blocking_game(attacker)
    script(game, 1, act_illegal(Hawk), act())
    declare_blockers_step(game)
    assert game.players[1].pending_entries == ()
    assert game.combat_state.blockers == {}


def test_no_block_declaration_without_attackers():
    game = _game()
    game.step = Step.DECLARE_BLOCKERS
    script(game, 1, act())
    declare_blockers_step(game)
    assert game.players[1].pending_entries == (act(),)


def test_run_scripts_consumes_an_empty_declaration_before_the_next_priority():
    game = _game()
    game.step = Step.BEGIN_COMBAT
    script(game, 0, pass_priority(), act(), pass_priority())
    run_scripts(game)
    assert (game.phase, game.step) == (Phase.COMBAT, Step.DECLARE_ATTACKERS)
    assert game.players[0].pending_entries == ()


# ---------------------------------------------------------------------------
# An attacked planeswalker that leaves combat takes no damage
# ---------------------------------------------------------------------------


def _attacking_walker(attacker):
    game = _game()
    _ready(attacker)
    walker = Walker()
    set_board_state(game, 0, battlefield=[attacker])
    set_board_state(game, 1, battlefield=[walker])
    script(game, 0, act(type(attacker), scoped={type(attacker): Walker}))
    declare_attackers_step(game)
    return game, walker


def test_a_departed_planeswalker_receives_no_damage_or_lifelink():
    from engine.zones import move_to_zone

    bear = Bear(keywords=Keyword.LIFELINK)
    game, walker = _attacking_walker(bear)
    move_to_zone(game, walker, Zone.BATTLEFIELD, Zone.GRAVEYARD)
    combat_damage_step(game)
    assert game.players[0].life == 20 and game.players[1].life == 20
    assert bear in game.combat_state.attackers


def test_a_flickered_planeswalker_is_a_new_object_and_is_not_attacked():
    from engine.zones import move_to_zone

    game, walker = _attacking_walker(Bear())
    move_to_zone(game, walker, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, walker, Zone.EXILE, Zone.BATTLEFIELD)
    loyalty = walker.loyalty
    combat_damage_step(game)
    assert walker.loyalty == loyalty and game.players[1].life == 20


def test_a_planeswalker_that_changes_control_or_type_leaves_combat():
    from engine.types import CardType

    game, walker = _attacking_walker(Bear())
    walker.controller = game.players[0]
    combat_damage_step(game)
    assert walker.loyalty == 5

    game, walker = _attacking_walker(Bear())
    walker.card_types = walker.card_types - {CardType.PLANESWALKER}
    combat_damage_step(game)
    assert walker.loyalty == 5 and game.players[1].life == 20


def test_a_blocked_trampler_assigns_nothing_to_a_departed_planeswalker():
    from engine.zones import move_to_zone

    trampler = Bear(keywords=Keyword.TRAMPLE)
    game, walker = _attacking_walker(trampler)
    chump = Bear(name="Chump")
    _ready(chump)
    chump.base_toughness = 1
    set_board_state(game, 1, battlefield=[walker, chump])
    game.step = Step.DECLARE_BLOCKERS
    script(game, 1, act(_ref(game, chump), scoped={_ref(game, chump): _ref(game, trampler)}))
    declare_blockers_step(game)
    move_to_zone(game, walker, Zone.BATTLEFIELD, Zone.GRAVEYARD)
    combat_damage_step(game)
    assert game.players[1].life == 20
    assert chump.damage_marked >= 1 or chump not in game.get_battlefield(game.players[1]).get_all()


def test_a_planeswalker_removed_after_first_strike_takes_no_normal_damage():
    from engine.zones import move_to_zone

    striker = Bear(keywords=Keyword.DOUBLE_STRIKE)
    game, walker = _attacking_walker(striker)
    combat_damage_step(game, sub_step="first_strike")
    assert walker.loyalty == 3
    move_to_zone(game, walker, Zone.BATTLEFIELD, Zone.GRAVEYARD)
    combat_damage_step(game, sub_step="normal")
    assert game.players[1].life == 20


# ---------------------------------------------------------------------------
# Review round 2: helper multi-blocks, singleton defender questions,
# permanent planeswalker departures, creature-planeswalker damage
# ---------------------------------------------------------------------------


def _helper_and_script_agree(build, assignments, scoped, *, illegal=False):
    """Run the same block through the helper and through a direct script on
    two identical boards; return both resulting block maps, by blocker name."""
    results = []
    for via_helper in (True, False):
        brute = build()
        game, bear, cub, _hawk = _two_attackers_one_blocker(brute)
        mapping = assignments(bear, cub, brute)
        error = None
        try:
            if via_helper:
                declare_blockers(game, mapping, illegal=illegal)
            else:
                entry = (act_illegal if illegal else act)(
                    _ref(game, brute),
                    scoped={_ref(game, brute): [_ref(game, a) for a in scoped(bear, cub)]},
                )
                script(game, 1, entry)
                declare_blockers_step(game)
        except ScriptEntryError as exc:
            error = exc.reason
        blocks = {b.name: [a.name for a in attackers]
                  for b, attackers in game.combat_state.blockers.items()}
        results.append((error, blocks, brute.is_blocking))
    return results


def _ordinary():
    return Brute()


def _double():
    brute = Brute()
    brute._max_attackers_blocked = 2
    return brute


@pytest.mark.parametrize("assignments", [
    lambda bear, cub, brute: {bear: [brute], cub: [brute]},
    lambda bear, cub, brute: {bear: ["Brute"], cub: [brute]},
    lambda bear, cub, brute: {"Bear": [brute], "Cub": ["Brute"]},
], ids=["objects", "mixed", "names"])
def test_the_blockers_helper_keeps_every_attacker_a_blocker_is_given(assignments):
    both = lambda bear, cub: [bear, cub]  # noqa: E731
    helper, direct = _helper_and_script_agree(_ordinary, assignments, both)
    assert helper == direct == ("not offered", {}, False)
    helper, direct = _helper_and_script_agree(_ordinary, assignments, both, illegal=True)
    assert helper == direct == (None, {}, False)
    helper, direct = _helper_and_script_agree(_double, assignments, both)
    assert helper == direct == (None, {"Brute": ["Bear", "Cub"]}, True)


def test_a_duplicate_assignment_is_one_block():
    brute = Brute()
    game, bear, _cub, _hawk = _two_attackers_one_blocker(brute)
    declare_blockers(game, {bear: [brute, brute]})
    assert game.combat_state.blockers == {brute: [bear]}


def _defender_questions(game):
    return [r for r in game.players[0].transcript.all() if r.query.prompt.startswith("choose what")]


def test_with_no_planeswalker_the_defending_player_is_still_asked():
    game = _game()
    (bear,) = _ready(Bear())
    set_board_state(game, 0, battlefield=[bear])
    _attack(game, Bear)
    (question,) = _defender_questions(game)
    assert [o.kind.value for o in question.options] == ["player"]
    assert game.combat_state.attackers == {bear: game.players[1]}


@pytest.mark.parametrize("walker", [False, True], ids=["alone", "with-walker"])
def test_a_scoped_attack_on_the_defending_player_takes_effect(walker):
    game = _game()
    (bear,) = _ready(Bear())
    set_board_state(game, 0, battlefield=[bear])
    if walker:
        set_board_state(game, 1, battlefield=[Walker()])
    script(game, 0, act(Bear, scoped={Bear: Decision.player(seat=1)}))
    declare_attackers_step(game)
    assert game.combat_state.attackers == {bear: game.players[1]}


@pytest.mark.parametrize("walker", [False, True], ids=["alone", "with-walker"])
def test_act_illegal_fails_when_a_legal_player_attack_takes_effect(walker):
    game = _game()
    (bear,) = _ready(Bear())
    set_board_state(game, 0, battlefield=[bear])
    if walker:
        set_board_state(game, 1, battlefield=[Walker()])
    script(game, 0, act_illegal(Bear, scoped={Bear: Decision.player(seat=1)}))
    with pytest.raises(ScriptEntryError) as excinfo:
        declare_attackers_step(game)
    assert excinfo.value.reason == "took effect"


def test_the_attackers_helper_attacks_the_player_without_a_planeswalker():
    game = _game()
    (bear,) = _ready(Bear())
    set_board_state(game, 0, battlefield=[bear])
    declare_attackers(game, ["Bear"])
    assert game.combat_state.attackers == {bear: game.players[1]}


def _double_striking_lifelinker():
    return Bear(keywords=Keyword.DOUBLE_STRIKE | Keyword.LIFELINK)


def _leave_and_return(game, walker, how):
    """Take *walker* out of combat by control or by type; return the undo."""
    from engine.continuous_effects import ContinuousEffect, Layer
    from engine.types import CardType

    if how == "controller":
        walker.controller = game.players[0]
        return lambda: setattr(walker, "controller", game.players[1])

    def not_a_planeswalker(_game):
        walker.card_types = walker.card_types - {CardType.PLANESWALKER}

    effect = ContinuousEffect(source=walker, layer=Layer.TYPE, apply=not_a_planeswalker)
    game.effect_manager.add(effect)
    game.effect_manager.apply_all(game)

    def come_back():
        game.effect_manager.remove(effect)
        game.effect_manager.apply_all(game)

    return come_back


@pytest.mark.parametrize("how", ["controller", "type"])
def test_a_planeswalker_that_left_combat_never_rejoins_it(how):
    game, walker = _attacking_walker(_double_striking_lifelinker())
    come_back = _leave_and_return(game, walker, how)
    combat_damage_step(game, sub_step="first_strike")
    assert walker.loyalty == 5 and game.players[0].life == 20
    come_back()
    combat_damage_step(game, sub_step="normal")
    assert walker.loyalty == 5 and game.players[0].life == 20 and game.players[1].life == 20


@pytest.mark.parametrize("how", ["controller", "type"])
def test_a_departure_seen_when_the_game_settles_lasts_through_a_return(how):
    from engine.stack import settle_after_resolution

    game, walker = _attacking_walker(Bear(keywords=Keyword.LIFELINK))
    come_back = _leave_and_return(game, walker, how)
    settle_after_resolution(game)
    come_back()
    settle_after_resolution(game)
    combat_damage_step(game)
    assert walker.loyalty == 5 and game.players[0].life == 20 and game.players[1].life == 20


def test_a_blocked_trampler_assigns_nothing_to_a_planeswalker_that_left_and_returned():
    from engine.stack import settle_after_resolution

    trampler = Bear(keywords=Keyword.TRAMPLE)
    trampler.base_power = 4
    game, walker = _attacking_walker(trampler)
    chump = Bear(name="Chump")
    _ready(chump)
    set_board_state(game, 1, battlefield=[walker, chump])
    game.step = Step.DECLARE_BLOCKERS
    script(game, 1, act(_ref(game, chump), scoped={_ref(game, chump): _ref(game, trampler)}))
    declare_blockers_step(game)
    come_back = _leave_and_return(game, walker, "controller")
    settle_after_resolution(game)
    come_back()
    combat_damage_step(game)
    assert walker.loyalty == 5 and game.players[1].life == 20


def test_a_departure_is_forgotten_with_the_combat_it_happened_in():
    from engine.combat import end_combat_step
    from engine.stack import settle_after_resolution

    game, walker = _attacking_walker(Bear())
    come_back = _leave_and_return(game, walker, "controller")
    settle_after_resolution(game)
    come_back()
    end_combat_step(game)
    assert game.combat_state.departed_planeswalkers == []
    game.step = Step.DECLARE_ATTACKERS
    bear = next(iter(game.get_battlefield(game.players[0]).get_all()))
    bear.is_tapped = False
    script(game, 0, act(Bear, scoped={Bear: Walker}))
    declare_attackers_step(game)
    combat_damage_step(game)
    assert walker.loyalty == 3


def _creature_walker():
    from engine.types import CardType

    walker = Walker()
    walker.card_types = walker.card_types | {CardType.CREATURE}
    walker.damage_marked = 0
    return walker


def test_an_attacked_creature_planeswalker_loses_loyalty_and_is_marked_with_damage():
    game = _game()
    bear = Bear(keywords=Keyword.LIFELINK)
    _ready(bear)
    walker = _creature_walker()
    set_board_state(game, 0, battlefield=[bear])
    set_board_state(game, 1, battlefield=[walker])
    script(game, 0, act(Bear, scoped={Bear: Walker}))
    declare_attackers_step(game)
    combat_damage_step(game)
    assert (walker.loyalty, walker.damage_marked) == (3, 2)
    assert game.players[0].life == 22  # lifelink once, for the one assignment
    assert game.combat_state.damage_assignments[bear] == [(walker, 2)]


def test_a_blocking_creature_planeswalker_loses_loyalty_and_is_marked_with_damage():
    game = _game()
    (bear,) = _ready(Bear())
    walker = _creature_walker()
    walker.base_power, walker.base_toughness = 0, 4
    set_board_state(game, 0, battlefield=[bear])
    set_board_state(game, 1, battlefield=[walker])
    script(game, 0, act(Bear, scoped={Bear: Decision.player(seat=1)}))
    declare_attackers_step(game)
    game.step = Step.DECLARE_BLOCKERS
    script(game, 1, act(_ref(game, walker), scoped={_ref(game, walker): _ref(game, bear)}))
    declare_blockers_step(game)
    combat_damage_step(game)
    assert (walker.loyalty, walker.damage_marked) == (3, 2)


def test_prevented_damage_to_a_creature_planeswalker_has_no_result():
    game = _game()
    (bear,) = _ready(Bear())
    walker = _creature_walker()
    walker.combat_damage_prevented = True
    set_board_state(game, 0, battlefield=[bear])
    set_board_state(game, 1, battlefield=[walker])
    script(game, 0, act(Bear, scoped={Bear: Walker}))
    declare_attackers_step(game)
    combat_damage_step(game)
    assert (walker.loyalty, walker.damage_marked) == (5, 0)


# ---------------------------------------------------------------------------
# Scripted declarations are judged by their outcome, not by which questions
# the engine asked
# ---------------------------------------------------------------------------


@pytest.fixture
def skips_forced_defender_questions(monkeypatch):
    """An engine variant that never asks what an attacker attacks when the
    defending player is the only choice."""
    import engine.combat as combat
    from engine.types import CardType

    asks = combat._choose_defender

    def choose_defender(game, active, defending, attacker):
        walkers = [p for p in defending.zones[Zone.BATTLEFIELD].get_all()
                   if CardType.PLANESWALKER in getattr(p, "card_types", ())]
        return asks(game, active, defending, attacker) if walkers else defending

    monkeypatch.setattr(combat, "_choose_defender", choose_defender)


@pytest.fixture
def attacks_the_player_unasked(monkeypatch):
    """A faulty engine variant that never asks what an attacker attacks and
    always sends it at the defending player."""
    import engine.combat as combat

    monkeypatch.setattr(
        combat, "_choose_defender", lambda game, active, defending, attacker: defending
    )


def _lone_bear(*extra_defenders):
    game = _game()
    (bear,) = _ready(Bear())
    set_board_state(game, 0, battlefield=[bear])
    if extra_defenders:
        set_board_state(game, 1, battlefield=list(extra_defenders))
    return game, bear


@pytest.mark.usefixtures("skips_forced_defender_questions")
def test_a_skipped_forced_defender_question_still_takes_a_scoped_player_attack():
    game, bear = _lone_bear()
    script(game, 0, act(Bear, scoped={Bear: Decision.player(seat=1)}))
    declare_attackers_step(game)
    assert game.combat_state.attackers == {bear: game.players[1]}
    assert not _defender_questions(game)


@pytest.mark.usefixtures("skips_forced_defender_questions")
def test_a_skipped_forced_defender_question_still_fails_act_illegal_for_a_legal_attack():
    game, _bear = _lone_bear()
    script(game, 0, act_illegal(Bear, scoped={Bear: Decision.player(seat=1)}))
    with pytest.raises(ScriptEntryError) as excinfo:
        declare_attackers_step(game)
    assert excinfo.value.reason == "took effect"


@pytest.mark.usefixtures("skips_forced_defender_questions")
def test_a_skipped_forced_defender_question_still_rejects_a_planeswalker_that_is_not_there():
    game, bear = _lone_bear()
    script(game, 0, act(Bear, scoped={Bear: Walker}))
    with pytest.raises(ScriptEntryError) as excinfo:
        declare_attackers_step(game)
    assert excinfo.value.reason == "not offered"
    assert game.combat_state.attackers == {} and not bear.is_tapped


@pytest.mark.usefixtures("attacks_the_player_unasked")
def test_a_declaration_that_would_attack_a_different_defender_is_withdrawn():
    walker = Walker()
    game, bear = _lone_bear(walker)
    script(game, 0, act(Bear, scoped={Bear: Walker}))
    with pytest.raises(ScriptEntryError) as excinfo:
        declare_attackers_step(game)
    assert excinfo.value.reason == "not offered"
    assert game.combat_state.attackers == {} and not bear.is_tapped

    script(game, 0, act_illegal(Bear, scoped={Bear: Walker}), act(Bear))
    declare_attackers_step(game)
    assert game.combat_state.attackers == {bear: game.players[1]}


# ---------------------------------------------------------------------------
# A declaration's entry ends with the declaration, however it ends
# ---------------------------------------------------------------------------


def _an_independent_choice(player) -> int:
    """A later mandatory choice between 1 and 7, which nothing scripts."""
    from engine.queries import PlayerQuery, ask

    player.set_baseline(Intent(pattern=GameRef()))
    query = PlayerQuery(
        source=(), prompt="pick a number",
        options=(Decision.number(1), Decision.number(7)), min=1, max=1,
    )
    return dict(ask(player, query).selected[0].attrs)["value"]


def test_an_attack_that_ends_in_an_error_ends_its_entry():
    game = _game()
    bear = Bear()  # summoning sick: it can't attack
    set_board_state(game, 0, battlefield=[bear])
    p0 = game.players[0]
    script(game, 0, act(Bear, choices=[Decision.number(7)]))
    with pytest.raises(PostconditionError):
        declare_attackers_step(game)
    assert not p0.acting and _an_independent_choice(p0) == 1


def test_a_block_that_ends_in_an_error_ends_its_entry():
    attacker, wall = Hawk(), Bear(name="Wall")
    game = _blocking_game(attacker, wall)
    p1 = game.players[1]
    script(game, 1, act(_ref(game, wall), choices=[Decision.number(7)]))
    with pytest.raises(PostconditionError):
        declare_blockers_step(game)
    assert not p1.acting and _an_independent_choice(p1) == 1


@pytest.mark.parametrize("through_helper", [False, True], ids=["step", "helper"])
def test_a_block_whose_completion_raises_ends_its_entry(monkeypatch, through_helper):
    attacker, wall = Bear(), Bear(name="Wall")
    game = _blocking_game(attacker, wall)
    p1 = game.players[1]

    def fail(*args):
        raise RuntimeError("completion failed")

    monkeypatch.setattr(p1, "confirm_declaration", fail)
    with pytest.raises((RuntimeError, TestSetupError)):
        if through_helper:
            declare_blockers(game, {"Bear": ["Wall"]})
        else:
            script(game, 1, act(_ref(game, wall), choices=[Decision.number(7)]))
            declare_blockers_step(game)
    assert not p1.acting and _an_independent_choice(p1) == 1


# ---- a declaration wrapper performs its step's action once -------------------


@pytest.mark.parametrize("entered", ["pending", "by setup"])
def test_a_declaration_wrapper_declares_once_whichever_driver_continues(entered):
    from engine.game_state import StepState
    from engine.turn import advance

    game = _game()
    (bear,) = _ready(Bear())
    set_board_state(game, 0, battlefield=[bear])
    if entered == "pending":
        game.step_state = StepState.PENDING
    else:
        game.open_window()
    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef()))
    declare_attackers(game, [bear])
    assert bear.is_attacking and game.step_state is StepState.WINDOW
    while game.step_state is StepState.WINDOW:
        advance(game)  # plays out the window, declaring nothing again
    assert bear.is_attacking and game.step_state is StepState.DONE
    assert len(_declarations(game.players[0], DECLARE_ATTACKERS_WINDOW)) == 1


# ---- a declaration step that raises no declaration ----------------------------


def _nothing_attacking():
    game = _game()
    bear, hawk = _ready(Bear(), Hawk())
    set_board_state(game, 0, battlefield=[bear])
    set_board_state(game, 1, battlefield=[hawk])
    game.step = Step.DECLARE_BLOCKERS
    return game, bear, hawk


def test_blocks_named_with_nothing_attacking_are_not_offered():
    game, bear, hawk = _nothing_attacking()
    with pytest.raises(ScriptEntryError) as excinfo:
        declare_blockers(game, {bear: [hawk]})
    assert excinfo.value.reason == "not offered"


def test_declaring_no_blocks_with_nothing_attacking_is_fulfilled():
    game, bear, hawk = _nothing_attacking()
    declare_blockers(game, {})
    assert game.combat_state.blockers == {}


def test_an_illegal_block_with_nothing_attacking_is_not_taking_effect():
    game, bear, hawk = _nothing_attacking()
    declare_blockers(game, {bear: [hawk]}, illegal=True)
    assert game.combat_state.blockers == {}


def test_a_branch_declaring_only_through_per_query_is_not_offered_either():
    import test_utils
    from engine.combat import declare_blockers_step

    game, bear, hawk = _nothing_attacking()
    entry = act(branches=[branch(per_query={(lambda query: True): [_ref(game, hawk)]})])
    with pytest.raises(ScriptEntryError) as excinfo:
        test_utils._declare(game, game.players[1], entry, declare_blockers_step)
    assert excinfo.value.reason == "not offered"
