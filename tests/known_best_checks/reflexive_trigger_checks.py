"""A reflexive triggered ability ("when you do", CR 603.12) waits like any
other triggered ability: it goes on the stack when the game next settles,
after state-based actions, in APNAP order and its controller's chosen order,
choosing its targets as it goes (CR 603.3b, 603.3d).

Faebloom Trick is the Known-Best card with one. Run inside
``known_best/workspace`` by ``tests/test_known_best_gameplay_regressions.py``.
"""

from __future__ import annotations

from cards.fdn.fdn_38.card_impl import FaebloomTrick, FaebloomTrickAbility1
from engine.card import Creature
from engine.casting import cast_spell
from engine.decisions import Decision, DecisionKind, GameRef, InvalidPlayerChoiceError
from engine.events import EntersBattlefieldTriggeredEvent
from engine.stack import resolve_top_of_stack
from engine.triggers import TriggerRegistration
from engine.types import ManaType, Phase, Zone
from test_utils import Intent, branch, create_game, set_board_state


class WatcherAbility1:
    """When the first Faerie enters, nothing happens."""


class WatcherAbility2:
    """When the first Faerie enters, nothing else happens."""


def _watch_first_faerie(game, source, controller, printed, targeting=None):
    """A trigger of *controller*'s *source* on the first Faerie entering."""
    seen: list[object] = []

    def _first_faerie(game, event):
        if getattr(event.permanent, "name", None) != "Faerie" or seen:
            return False
        seen.append(event.permanent)
        return True

    game.trigger_manager.register(TriggerRegistration(
        event_type=EntersBattlefieldTriggeredEvent, condition=_first_faerie,
        effect=(lambda game, targets, context: None) if targeting else (lambda game: None),
        source=source, controller=controller, printed=printed, targeting=targeting,
    ))


def _faeries(game, player):
    return [o for o in game.get_battlefield(player).get_all() if getattr(o, "name", None) == "Faerie"]


def _table(*, their_creature=True):
    """Player 0 is active; player 1 holds Faebloom Trick with mana for it, and
    player 0 has *their_creature*, the only possible target."""
    game = create_game()
    p0, p1 = game.players
    game.active_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    trick = FaebloomTrick(owner=p1, controller=p1)
    bear = Creature(name="Bear", base_power=2, base_toughness=2)
    set_board_state(game, 0, battlefield=[bear] if their_creature else [])
    set_board_state(game, 1, hand=[trick], mana={ManaType.BLUE: 3})
    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef()))
    return game, trick, bear


def _cast_and_resolve(game, trick, preferences=(), branches=()):
    """Player 1 casts Faebloom Trick in player 0's turn; it resolves and the
    game settles."""
    p1 = game.players[1]
    game.priority_player_index = 1
    p1.set_baseline(Intent(pattern=GameRef(), preferences=tuple(preferences), branches=tuple(branches)))
    cast_spell(game, p1, trick)
    resolve_top_of_stack(game)


def _bear_ref(game, bear):
    return Decision.obj(instance=game.refs.instance_id(bear, Zone.BATTLEFIELD.value))


def test_the_reflexive_trigger_goes_on_the_stack_above_the_active_players_trigger():
    game, trick, bear = _table()
    p0, p1 = game.players
    _watch_first_faerie(game, bear, p0, WatcherAbility1)
    _cast_and_resolve(game, trick, [_bear_ref(game, bear)])
    top, bottom = game.stack.objects()
    assert (top.controller, top.printed, top.targets) == (p1, FaebloomTrickAbility1, [bear])
    assert (bottom.controller, bottom.printed) == (p0, WatcherAbility1)


def test_the_reflexive_trigger_is_ordered_with_its_controllers_other_triggers():
    game, trick, bear = _table()
    p1 = game.players[1]
    _watch_first_faerie(game, trick, p1, WatcherAbility2)
    reflexive_first = Decision.ability(printed=FaebloomTrickAbility1)
    _cast_and_resolve(game, trick, [reflexive_first, _bear_ref(game, bear)])
    orderings = [
        r for r in p1.transcript.all()
        if r.options and all(o.kind is DecisionKind.ABILITY for o in r.options) and r.min == r.max == 2
    ]
    assert len(orderings) == 1
    top, bottom = game.stack.objects()
    # The first chosen goes on the stack first, so it ends up at the bottom.
    assert (top.printed, bottom.printed) == (WatcherAbility2, FaebloomTrickAbility1)
    assert bottom.targets == [bear]


def test_a_target_that_dies_to_state_based_actions_first_is_never_chosen():
    game, trick, bear = _table()

    class DoomedTrick(FaebloomTrick):
        def on_resolve(self, game):
            bear.damage_marked = 2  # lethal, so it dies before the trigger is placed
            super().on_resolve(game)

    p1 = game.players[1]
    doomed = DoomedTrick(owner=p1, controller=p1)
    set_board_state(game, 1, hand=[doomed], mana={ManaType.BLUE: 3})
    _cast_and_resolve(game, doomed, [_bear_ref(game, bear)])
    assert game.stack.is_empty()
    assert game.players[0].zones[Zone.GRAVEYARD].contains(bear)
    assert len(_faeries(game, p1)) == 2


def test_with_no_legal_target_the_tokens_are_still_created():
    game, trick, _ = _table(their_creature=False)
    _cast_and_resolve(game, trick)
    assert game.stack.is_empty()
    assert len(_faeries(game, game.players[1])) == 2


def test_a_rejected_placement_is_asked_again_without_duplicate_tokens_or_triggers():
    from engine.queries import PlayerQuery, ask

    game, trick, bear = _table()
    p1 = game.players[1]
    asked: list[int] = []

    p0 = game.players[0]
    p0_ref = game.refs.player_decision(p0, seat=0)
    bear_ref = _bear_ref(game, bear)

    def _rejects_the_bear(game, event, controller):
        answer = ask(controller, PlayerQuery(source=(), prompt="watcher target", options=(bear_ref, p0_ref), min=1, max=1))
        asked.append(1)
        if answer.selected[0] == bear_ref:
            raise InvalidPlayerChoiceError("the watcher may not target the Bear")
        return [p0]

    _watch_first_faerie(game, trick, p1, WatcherAbility2, targeting=_rejects_the_bear)
    reflexive_first = Decision.ability(printed=FaebloomTrickAbility1)
    # The reflexive trigger can target only the Bear; the watcher is offered
    # the Bear and player 0, and rejects the Bear, so its controller's whole
    # placement is rolled back and asked again under the second branch.
    _cast_and_resolve(
        game, trick,
        branches=(branch(reflexive_first, bear_ref), branch(reflexive_first, p0_ref, bear_ref)),
    )
    assert asked == [1]  # the rollback restored the first try's record
    assert len(_faeries(game, p1)) == 2
    assert len(game.created_tokens) == 2
    top, bottom = game.stack.objects()
    assert (top.printed, top.targets) == (WatcherAbility2, [p0])
    assert (bottom.printed, bottom.targets) == (FaebloomTrickAbility1, [bear])
    assert not game.trigger_manager.has_pending()
