"""The Known-Best Engine's Priority Query (DECISION-MODEL.md › Priority actions).

Run inside ``known_best/workspace`` by ``tests/test_known_best_priority_query.py``:
the module imports the workspace's ``engine`` and ``cards`` packages, which the
repo suite cannot import in-process alongside other workspaces.
"""

from __future__ import annotations

from typing import Any

import pytest
from cards.fdn.fdn_134.card_impl import AjaniCallerOfThePride
from cards.fdn.fdn_163.card_impl import SelfReflection
from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_223.card_impl import GiantGrowth
from cards.fdn.fdn_227.card_impl import LlanowarElves, LlanowarElvesAbility1
from cards.fdn.fdn_280.card_impl import Forest, ForestAbility1
from engine.card import Creature, Sorcery
from engine.casting import CastingError, cast_spell
from engine.decisions import (
    Decision,
    DecisionKind,
    GameRef,
    InvalidPlayerChoiceError,
    PlayerDecision,
)
from engine.game import create_game as engine_create_game
from engine.intent_player import DeterministicPlayer, Intent
from engine.priority import priority_query, take_priority
from engine.queries import Answer, PlayerQuery, ask, is_priority_query, priority_pattern
from engine.rollback import take_snapshot
from engine.stack import StackObject, priority_loop
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType, Phase, Step, Zone
from test_utils import create_game, resolve_stack, set_board_state


class ScriptedPlayer(DeterministicPlayer):
    """Answers Priority Queries from a script of preferences and keeps going
    after a rejected choice, recording each rejection."""

    rollback_exempt = DeterministicPlayer.rollback_exempt | {"script", "rejections"}

    def __init__(self, name: str, script: list[PlayerDecision | None]) -> None:
        super().__init__(name)
        self.script = list(script)
        self.rejections: list[InvalidPlayerChoiceError] = []

    def answer(self, query: PlayerQuery) -> Answer:
        if not is_priority_query(query):
            return super().answer(query)
        self.transcript._record(query)
        preference = self.script.pop(0) if self.script else None
        for option in query.options:
            if preference is not None and preference.attrs <= option.attrs:
                return Answer(selected=(option,))
        return Answer()

    def on_choice_rejected(self, query, answer, error) -> None:
        self.rejections.append(error)


def _game(p0: DeterministicPlayer | None = None):
    if p0 is None:
        game = create_game()
    else:
        game = engine_create_game(p0, DeterministicPlayer("Player2"), [], [])
    for player in game.players:
        player.game = game
        player.drawn_from_empty_library = False
        player.set_baseline(Intent(pattern=GameRef()))
    return _main_phase(game)


def _main_phase(game):
    game.phase, game.step = Phase.PRECOMBAT_MAIN, None
    game.active_player_index = game.priority_player_index = 0
    return game


def _printed(query: PlayerQuery, kind: DecisionKind) -> list[type]:
    return [dict(o.attrs).get("printed") for o in query.options if o.kind is kind]


def _fingerprint(game) -> tuple:
    zones = tuple(
        (id(obj), zone.value)
        for player in game.players
        for zone in (Zone.HAND, Zone.BATTLEFIELD, Zone.GRAVEYARD, Zone.EXILE, Zone.STACK, Zone.LIBRARY)
        for obj in player.zones[zone].get_all()
    )
    pools = tuple(
        tuple(sorted((m.value, player.mana_pool.get(m)) for m in ManaType)) for player in game.players
    )
    lives = tuple(player.life for player in game.players)
    tapped = tuple(
        getattr(obj, "is_tapped", None)
        for player in game.players
        for obj in player.zones[Zone.BATTLEFIELD].get_all()
    )
    return zones, pools, lives, tapped, len(game.stack), len(game.trigger_manager._triggers)


# ---------------------------------------------------------------------------
# What is offered
# ---------------------------------------------------------------------------


def _offer_board(game):
    set_board_state(
        game, 0,
        hand=[Forest(), LlanowarElves(), GiantGrowth(), SelfReflection()],
        battlefield=[Forest(), AjaniCallerOfThePride()],
    )


def test_main_phase_offers_spells_lands_and_abilities_with_printed_classes():
    game = _game()
    _offer_board(game)
    query, _ = priority_query(game, game.players[0])

    assert query.min == 0 and query.max == 1
    assert is_priority_query(query)
    assert sorted(c.__name__ for c in _printed(query, DecisionKind.OBJECT)) == sorted(
        ["Forest", "LlanowarElves", "GiantGrowth", "SelfReflection"]
    )
    ajani = game.get_battlefield(game.players[0]).get_all()[1]
    loyalty = [ability.printed for ability in ajani.get_loyalty_abilities()]
    assert sorted(c.__name__ for c in _printed(query, DecisionKind.ABILITY)) == sorted(
        [ForestAbility1.__name__, *(c.__name__ for c in loyalty)]
    )
    assert all(dict(o.attrs).get("printed") is not None for o in query.options)


def test_instant_speed_offers_only_instants_and_non_loyalty_abilities():
    game = _game()
    _offer_board(game)
    game.stack.push(StackObject(source=None, controller=game.players[1], on_resolve=lambda g: None))
    query, _ = priority_query(game, game.players[0])

    assert _printed(query, DecisionKind.OBJECT) == [GiantGrowth]
    assert _printed(query, DecisionKind.ABILITY) == [ForestAbility1]


def test_non_active_player_is_offered_instants_but_no_lands_or_sorceries():
    game = _game()
    set_board_state(game, 1, hand=[Forest(), GiantGrowth(), SelfReflection()])
    query, _ = priority_query(game, game.players[1])

    assert _printed(query, DecisionKind.OBJECT) == [GiantGrowth]


def test_no_land_is_offered_once_the_land_play_is_used():
    game = _game()
    set_board_state(game, 0, hand=[Forest()])
    game.players[0].land_plays_remaining = 0
    query, _ = priority_query(game, game.players[0])

    assert query.options == ()


def test_flashback_card_in_graveyard_is_offered_and_cast_for_its_flashback_cost():
    game = _game()
    think = ThinkTwice()
    set_board_state(
        game, 0, graveyard=[think], mana={ManaType.BLUE: 1, ManaType.COLORLESS: 2}
    )
    game.get_library(game.players[0]).add(Creature(name="Library", owner=game.players[0]))
    p0 = game.players[0]
    p0.start_intent("flashback", Intent(pattern=priority_pattern(0), preferences=(Decision.obj(printed=ThinkTwice),)))

    assert take_priority(game, p0) is False
    assert game.stack.peek().departure_zone is Zone.EXILE
    assert p0.mana_pool.total() == 0
    p0.end_intent("flashback")
    resolve_stack(game)
    assert game.get_exile(p0).contains(think)


def test_mana_ability_of_a_creature_and_loyalty_abilities_are_ability_options():
    game = _game()
    set_board_state(game, 0, battlefield=[LlanowarElves(), AjaniCallerOfThePride()])
    query, _ = priority_query(game, game.players[0])

    assert LlanowarElvesAbility1 in _printed(query, DecisionKind.ABILITY)


def test_loyalty_ability_is_not_offered_again_this_turn_once_activated():
    game = _game()
    set_board_state(game, 0, battlefield=[AjaniCallerOfThePride()])
    p0 = game.players[0]
    plus_one = game.get_battlefield(p0).get_all()[0].get_loyalty_abilities()[0].printed
    p0.start_intent("plus", Intent(pattern=priority_pattern(0), preferences=(Decision.ability(printed=plus_one),)))

    assert take_priority(game, p0) is False
    query, _ = priority_query(game, p0)
    assert query.options == ()


# ---------------------------------------------------------------------------
# Choosing, passing and the priority loop
# ---------------------------------------------------------------------------


def test_baseline_passes_priority_even_when_its_preferences_match_an_action():
    game = _game()
    set_board_state(game, 0, hand=[LlanowarElves()], mana={ManaType.GREEN: 1})
    p0 = game.players[0]
    p0.set_baseline(Intent(pattern=GameRef(), preferences=(Decision.obj(printed=LlanowarElves),)))

    priority_loop(game)

    assert len(game.get_hand(p0)) == 1
    record = p0.transcript.all()[-1]
    assert is_priority_query(record.query) and record.answer == Answer()


def test_player_without_a_baseline_passes_priority():
    game = _game()
    set_board_state(game, 0, hand=[LlanowarElves()])
    for player in game.players:
        player.clear_baseline()

    priority_loop(game)

    assert len(game.get_hand(game.players[0])) == 1


def test_priority_intent_casts_and_the_spell_resolves_after_both_pass():
    game = _game()
    elves = LlanowarElves()
    set_board_state(game, 0, hand=[elves], mana={ManaType.GREEN: 1})
    p0 = game.players[0]
    p0.start_intent("cast", Intent(pattern=priority_pattern(0), preferences=(Decision.obj(printed=LlanowarElves),)))

    priority_loop(game)

    p0.end_intent("cast")
    assert game.get_battlefield(p0).contains(elves)


def test_mana_ability_then_cast_in_one_priority_window():
    elves = LlanowarElves()
    p0 = ScriptedPlayer("Player1", [Decision.ability(printed=ForestAbility1), Decision.obj(printed=LlanowarElves)])
    game = _game(p0)
    set_board_state(game, 0, hand=[elves], battlefield=[Forest()])

    priority_loop(game)

    assert game.get_battlefield(p0).contains(elves)
    assert p0.rejections == []


def test_land_play_is_an_object_option():
    game = _game()
    forest = Forest()
    set_board_state(game, 0, hand=[forest])
    p0 = game.players[0]
    p0.start_intent("land", Intent(pattern=priority_pattern(0), preferences=(Decision.obj(printed=Forest),)))

    assert take_priority(game, p0) is False
    assert game.get_battlefield(p0).contains(forest)
    assert p0.land_plays_remaining == 0


# ---------------------------------------------------------------------------
# Rejection, rollback and re-asking
# ---------------------------------------------------------------------------


def test_rejected_cast_is_rolled_back_and_the_query_asked_again():
    p0 = ScriptedPlayer("Player1", [Decision.obj(printed=SelfReflection), None])
    game = _game(p0)
    reflection = SelfReflection()
    set_board_state(game, 0, hand=[reflection], battlefield=[Forest()])
    before = _fingerprint(game)
    instance = game.refs.instance_id(reflection, Zone.HAND.value)

    assert take_priority(game, p0) is True

    assert len(p0.rejections) == 1
    assert isinstance(p0.rejections[0].__cause__, CastingError)
    assert _fingerprint(game) == before
    assert game.refs.instance_id(reflection, Zone.HAND.value) == instance
    priority_records = [r for r in p0.transcript.all() if is_priority_query(r.query)]
    assert len(priority_records) == 2
    assert priority_records[0].query.options == priority_records[1].query.options


def test_rejected_mana_ability_on_a_tapped_land_is_rolled_back():
    p0 = ScriptedPlayer("Player1", [Decision.ability(printed=ForestAbility1), None])
    game = _game(p0)
    forest = Forest()
    set_board_state(game, 0, battlefield=[forest])
    forest.is_tapped = True
    before = _fingerprint(game)

    assert take_priority(game, p0) is True

    assert len(p0.rejections) == 1
    assert _fingerprint(game) == before


def test_deterministic_player_surfaces_a_rejection_instead_of_being_asked_forever():
    game = _game()
    reflection = SelfReflection()
    set_board_state(game, 0, hand=[reflection])
    p0 = game.players[0]
    p0.start_intent("illegal", Intent(pattern=priority_pattern(0), preferences=(Decision.obj(printed=SelfReflection),)))
    before = _fingerprint(game)

    with pytest.raises(InvalidPlayerChoiceError) as raised:
        priority_loop(game)

    assert isinstance(raised.value.__cause__, CastingError)
    assert _fingerprint(game) == before


class _Leaky(Sorcery):
    """Changes the game in many ways, then finds its cast illegal."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Leaky")
        kwargs.setdefault("mana_cost", ManaCost.parse("{0}"))
        super().__init__(**kwargs)
        self.history: list[str] = []
        self.counter = [0]

    def cast_offers(self, game, player, from_zone, mode):
        counter = self.counter

        def action():
            counter[0] += 1
            self.history.append("attempt")
            player.life -= 5
            player.mana_pool.add(ManaType.RED, 3)
            game.get_hand(player).remove(self)
            game.get_graveyard(player).add(self)
            game.trigger_manager.register(
                TriggerRegistration(event_type=object, condition=lambda g, e: True,
                                    effect=lambda g: None, source=self, controller=player)
            )
            game.refs.instance_id(self, Zone.GRAVEYARD.value)
            raise CastingError("Leaky finds itself illegal")

        return [(self, action)]


def test_rollback_restores_every_mutation_made_by_the_rejected_action():
    p0 = ScriptedPlayer("Player1", [Decision.obj(printed=_Leaky), None])
    game = _game(p0)
    leaky = _Leaky()
    set_board_state(game, 0, hand=[leaky])
    instance = game.refs.instance_id(leaky, Zone.HAND.value)
    before = _fingerprint(game)

    assert take_priority(game, p0) is True

    assert _fingerprint(game) == before
    assert leaky.history == [] and leaky.counter == [0]
    assert game.refs.instance_id(leaky, Zone.HAND.value) == instance
    assert len(p0.rejections) == 1


def test_snapshot_restores_a_played_out_game_in_place():
    game = _game()
    elves, growth = LlanowarElves(), GiantGrowth()
    set_board_state(game, 0, hand=[elves, growth], mana={ManaType.GREEN: 2})
    p0 = game.players[0]
    before = _fingerprint(game)
    snapshot = take_snapshot(game)

    cast_spell(game, p0, elves)
    resolve_stack(game)
    cast_spell(game, p0, growth)
    resolve_stack(game)
    assert _fingerprint(game) != before

    snapshot.restore()
    assert _fingerprint(game) == before
    assert game.get_hand(p0).get_all() == [elves, growth]


def test_rollback_keeps_the_players_transcript_and_intents():
    game = _game()
    p0 = game.players[0]
    p0.start_intent("kept", Intent(pattern=priority_pattern(0)))
    snapshot = take_snapshot(game)
    ask(p0, priority_query(game, p0)[0])

    snapshot.restore()

    assert len(p0.transcript.all()) == 1
    p0.end_intent("kept")


# ---------------------------------------------------------------------------
# Multi-face cards: one object per face, or one object and a face question
# ---------------------------------------------------------------------------


class _FaceA(Sorcery):
    pass


class _FaceB(Sorcery):
    pass


class _TwoFaced(Sorcery):
    """A card whose faces are distinct objects; ``per_face`` picks how a
    Priority Query presents it."""

    def __init__(self, per_face: bool, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Two Faced")
        kwargs.setdefault("mana_cost", ManaCost.parse("{0}"))
        super().__init__(**kwargs)
        self.per_face = per_face
        self.faces = (_FaceA(name="Face A"), _FaceB(name="Face B"))
        self.cast_face: type | None = None

    def _cast(self, game, player, face):
        self.cast_face = type(face)
        return cast_spell(game, player, self)

    def cast_offers(self, game, player, from_zone, mode):
        if self.per_face:
            return [(face, lambda f=face: self._cast(game, player, f)) for face in self.faces]

        def ask_face():
            options = tuple(
                game.refs.object_decision(face, zone=from_zone.value) for face in self.faces
            )
            source = game.refs.object_decision(self, zone=from_zone.value)
            answer = ask(player, PlayerQuery(source=(source,), prompt="Which face?",
                                             options=options, min=1, max=1))
            face = self.faces[options.index(answer.selected[0])]
            return self._cast(game, player, face)

        return [(self, ask_face)]


@pytest.mark.parametrize("per_face", [True, False])
def test_ordered_preferences_cast_the_intended_face_in_either_presentation(per_face):
    game = _game()
    card = _TwoFaced(per_face)
    set_board_state(game, 0, hand=[card])
    p0 = game.players[0]
    # Face B, otherwise the card and then Face B.
    p0.start_intent("face", Intent(pattern=GameRef(), preferences=(
        Decision.obj(printed=_FaceB), Decision.obj(printed=_TwoFaced),
    )))

    assert take_priority(game, p0) is False

    assert game.stack.peek().source is card and card.cast_face is _FaceB
    asked = [r.query for r in p0.transcript.all()]
    assert len(asked) == (1 if per_face else 2)
