"""Action scripts and choice retries in the Known-Best Workspace
(DECISION-MODEL.md › Priority actions › Legality and Action scripts).

Run inside ``known_best/workspace`` by ``tests/test_known_best_action_scripts.py``:
the module imports the workspace's ``engine`` and ``test_utils``, which the repo
suite cannot import in-process alongside other workspaces.
"""

from __future__ import annotations

import pytest
from engine.card import Artifact, ArtifactCreature, Creature, Instant, Sorcery
from engine.player import Player
from engine.card_queries import choose_object
from engine.casting import CastingError, cast_spell, cast_spell_free
from engine.game import create_game as engine_create_game
from engine.game import gain_life
from engine.decisions import (
    Decision,
    GameRef,
    InvalidPlayerChoiceError,
    PostconditionError,
)
from engine.intent_player import Intent, ScriptEntryError
from engine import attempts
from engine.priority import take_priority
from engine.stack import StackObject, copy_spell, priority_loop, resolve_top_of_stack
from engine.queries import Answer, PlayerQuery, ask
from engine.types import CardType, ManaCost, Phase, Step, Zone
from engine.zones import move_to_zone
import test_utils
from test_utils import (
    act,
    act_illegal,
    activate_card_ability,
    branch,
    advance_game_to_phase,
    advance_to_phase,
    cast_card,
    create_game,
    pass_priority,
    resolve_stack,
    run_scripts,
    script,
    set_board_state,
)

# ---------------------------------------------------------------------------
# A two-face test card, presentable either way an engine may choose
# ---------------------------------------------------------------------------


class GleamFace(Sorcery):
    """The test card's second face."""


class BladeCard(Artifact):
    """A two-face card: Blade (an artifact) // Gleam (a sorcery).

    ``presentation`` is how the engine offers it: ``"one"`` offers each face
    at priority, ``"two"`` offers the card and then asks which face.
    """

    def __init__(self, presentation: str, gleam_legal: bool = True, **kwargs) -> None:
        super().__init__(name="Blade", mana_cost=ManaCost(), **kwargs)
        self.presentation = presentation
        self.gleam_legal = gleam_legal
        self.gleam = GleamFace(name="Gleam", mana_cost=ManaCost())
        self.cast_face: str | None = None

    def cast_offers(self, game, player, from_zone, mode):
        if self.presentation == "one":
            return [
                (self, lambda: self._cast(game, player, "blade")),
                (self.gleam, lambda: self._cast(game, player, "gleam")),
            ]
        return [(self, lambda: self._cast(game, player, self._ask_face(game, player)))]

    def _ask_face(self, game, player) -> str:
        blade = game.refs.object_decision(self, zone=Zone.HAND.value)
        gleam = game.refs.object_decision(self.gleam, zone=Zone.HAND.value)
        query = PlayerQuery(
            source=(blade,), prompt="Cast which face?", options=(blade, gleam), min=1, max=1
        )
        return "gleam" if ask(player, query).selected == (gleam,) else "blade"

    def _cast(self, game, player, face: str):
        if face == "gleam" and not self.gleam_legal:
            raise CastingError("Gleam cannot be cast now")
        self.cast_face = face
        return cast_spell(game, player, self)


class Bolt(Instant):
    def __init__(self, **kwargs) -> None:
        super().__init__(name="Bolt", mana_cost=ManaCost(), **kwargs)


class Costly(Sorcery):
    def __init__(self, **kwargs) -> None:
        super().__init__(name="Costly", mana_cost=ManaCost(generic=3), **kwargs)


class Chooser(Sorcery):
    """On resolution, choose an artifact on the battlefield; the engine accepts
    any and rejects the ones named in ``illegal`` with InvalidPlayerChoiceError."""

    def __init__(self, illegal=(), gain=0, **kwargs) -> None:
        super().__init__(name="Chooser", mana_cost=ManaCost(), **kwargs)
        self.illegal = set(illegal)
        self.gain = gain
        self.chosen = None

    def on_resolve(self, game) -> None:
        if self.gain:
            gain_life(game, self.controller, self.gain)
        candidates = [
            card
            for player in game.players
            for card in game.get_battlefield(player).get_all()
            if not isinstance(card, Chooser)
        ]
        chosen = choose_object(game, self.controller, candidates, "Choose one", source_card=self)
        if chosen.name in self.illegal:
            raise InvalidPlayerChoiceError(f"{chosen.name} cannot be chosen")
        self.chosen = chosen.name


class ChoosingCast(Sorcery):
    """While being cast, asks for an artifact and rejects ``illegal`` ones."""

    def __init__(self, illegal=(), **kwargs) -> None:
        super().__init__(name="Choosing Cast", mana_cost=ManaCost(), **kwargs)
        self.illegal = set(illegal)

    def cast_offers(self, game, player, from_zone, mode):
        return [(self, lambda: self._cast(game, player))]

    def _cast(self, game, player):
        candidates = game.get_battlefield(player).get_all()
        chosen = choose_object(game, player, candidates, "Choose one", source_card=self)
        if chosen.name in self.illegal:
            raise InvalidPlayerChoiceError(f"{chosen.name} cannot be chosen")
        return cast_spell(game, player, self)


def _artifact(name: str) -> Artifact:
    return Artifact(name=name, mana_cost=ManaCost())


def _game():
    game = create_game()
    for player in game.players:
        player.drawn_from_empty_library = False
    game.phase, game.step = Phase.PRECOMBAT_MAIN, None
    game.active_player_index = game.priority_player_index = 0
    return game


def _with_blade(presentation: str, gleam_legal: bool = True):
    game = _game()
    blade = BladeCard(presentation, gleam_legal)
    set_board_state(game, 0, hand=[blade])
    return game, blade


def _on_stack(game, card) -> bool:
    return any(obj.source is card for obj in game.stack._items)


# ---------------------------------------------------------------------------
# act
# ---------------------------------------------------------------------------


def test_act_takes_the_action_and_leaves_the_stack_in_place():
    game, blade = _with_blade("one")
    script(game, 0, act(BladeCard))
    run_scripts(game)
    assert _on_stack(game, blade) and blade.cast_face == "blade"
    assert game.players[0].pending_entries == ()


def test_act_fails_when_not_offered():
    game = _game()
    script(game, 0, act(BladeCard))
    with pytest.raises(ScriptEntryError) as failure:
        run_scripts(game)
    assert failure.value.reason == "not offered"
    assert isinstance(failure.value, PostconditionError)


def test_act_fails_once_rejection_exhausts_its_branches_and_is_rolled_back():
    game = _game()
    costly = Costly()
    set_board_state(game, 0, hand=[costly])
    script(game, 0, act(Costly))
    with pytest.raises(ScriptEntryError) as failure:
        run_scripts(game)
    assert failure.value.reason == "rejected"
    assert isinstance(failure.value.error.__cause__, CastingError)
    assert game.get_hand(game.players[0]).contains(costly)
    assert game.stack.is_empty()


def test_act_fails_when_it_misses_its_goal():
    game, _blade = _with_blade("one")
    script(game, 0, act(BladeCard, goal=lambda g: False))
    with pytest.raises(ScriptEntryError) as failure:
        run_scripts(game)
    assert failure.value.reason == "missed goal"


@pytest.mark.parametrize("presentation", ["one", "two"])
def test_one_entry_answers_every_query_of_its_action(presentation):
    game, blade = _with_blade(presentation)
    script(game, 0, act(GleamFace, BladeCard))
    run_scripts(game)
    assert blade.cast_face == "gleam" and _on_stack(game, blade)


@pytest.mark.parametrize("presentation", ["one", "two"])
def test_a_rejection_retries_with_the_next_branch(presentation):
    """Gleam is illegal: whether the engine offered Gleam at once (one query)
    or asked Blade then Gleam (two queries), the second branch casts Blade."""
    game, blade = _with_blade(presentation, gleam_legal=False)
    script(
        game, 0,
        act(branches=[[GleamFace, BladeCard], [BladeCard]]),
        pass_priority(),
    )
    take_priority(game, game.players[0])
    assert blade.cast_face == "blade" and _on_stack(game, blade)
    # The rejected attempt and its retry were one entry: the next is still pending.
    assert [e.kind.value for e in game.players[0].pending_entries] == ["pass"]
    assert len(game.players[0].transcript.priority_queries()) == 2


@pytest.mark.parametrize("presentation", ["one", "two"])
def test_one_branch_is_not_retried(presentation):
    """Preferences that would reach a legal Blade still fail once Gleam is
    rejected: nothing is retried that the test did not write as a branch."""
    game, blade = _with_blade(presentation, gleam_legal=False)
    script(game, 0, act(GleamFace, BladeCard))
    with pytest.raises(ScriptEntryError) as failure:
        run_scripts(game)
    assert failure.value.reason == "rejected"
    assert game.get_hand(game.players[0]).contains(blade)


def test_a_branch_whose_action_is_not_offered_is_skipped():
    game, blade = _with_blade("one")
    script(game, 0, act(branches=[[Bolt], [BladeCard]]))
    run_scripts(game)
    assert blade.cast_face == "blade" and _on_stack(game, blade)


def test_a_branch_carries_its_own_choices():
    game = _game()
    keep, bad = _artifact("Keep"), _artifact("Bad")
    cast = ChoosingCast(illegal={"Bad"})
    set_board_state(game, 0, hand=[cast], battlefield=[bad, keep])
    script(game, 0, act(branches=[
        branch(ChoosingCast, choices=[Decision.obj(instance=bad.instance_id)]),
        branch(ChoosingCast, choices=[Decision.obj(instance=keep.instance_id)]),
    ]))
    run_scripts(game)
    assert _on_stack(game, cast)


def test_an_entry_takes_preferences_or_branches_not_both():
    with pytest.raises(TypeError):
        act(BladeCard, branches=[[BladeCard]])
    with pytest.raises(TypeError):
        Intent(pattern=GameRef(), preferences=(Decision.yes(),), branches=[[Decision.no()]])


def test_rejected_attempt_is_rolled_back_before_the_retry():
    game = _game()
    costly, bolt = Costly(), Bolt()
    set_board_state(game, 0, hand=[costly, bolt])
    script(game, 0, act(branches=[[Costly], [Bolt]]))
    run_scripts(game)
    assert game.get_hand(game.players[0]).contains(costly)
    assert _on_stack(game, bolt) and len(game.stack) == 1


# ---------------------------------------------------------------------------
# act_illegal and pass entries
# ---------------------------------------------------------------------------


def test_act_illegal_passes_when_not_offered():
    game = _game()
    script(game, 0, act_illegal(BladeCard))
    run_scripts(game)
    assert game.stack.is_empty() and game.players[0].pending_entries == ()


@pytest.mark.parametrize("presentation", ["one", "two"])
def test_act_illegal_passes_when_rejected(presentation):
    game, blade = _with_blade(presentation, gleam_legal=False)
    script(game, 0, act_illegal(GleamFace))
    run_scripts(game)
    assert game.stack.is_empty() and game.get_hand(game.players[0]).contains(blade)


def test_act_illegal_fails_when_it_takes_effect():
    game, _blade = _with_blade("one")
    script(game, 0, act_illegal(GleamFace))
    with pytest.raises(ScriptEntryError) as failure:
        run_scripts(game)
    assert failure.value.reason == "took effect"


def test_act_illegal_hands_the_same_window_to_the_next_entry():
    game, blade = _with_blade("one", gleam_legal=False)
    script(game, 0, act_illegal(GleamFace), act(BladeCard))
    run_scripts(game)
    assert blade.cast_face == "blade" and (game.phase, game.step) == (Phase.PRECOMBAT_MAIN, None)


@pytest.mark.parametrize("presentation", ["one", "two"])
def test_act_illegal_passes_when_every_branch_is_refused_or_not_offered(presentation):
    game, blade = _with_blade(presentation, gleam_legal=False)
    costly = Costly()
    set_board_state(game, 0, hand=[blade, costly])
    script(game, 0, act_illegal(branches=[[GleamFace], [Costly]]), pass_priority())
    run_scripts(game)
    assert game.stack.is_empty() and blade.cast_face is None
    assert game.players[0].pending_entries == ()


def test_act_illegal_fails_when_a_later_branch_takes_effect():
    game, blade = _with_blade("one", gleam_legal=False)
    script(game, 0, act_illegal(branches=[[GleamFace], [BladeCard]]))
    with pytest.raises(ScriptEntryError) as failure:
        run_scripts(game)
    assert failure.value.reason == "took effect"


def test_pass_entries_skip_priority_windows():
    game = _game()
    bolt = Bolt()
    set_board_state(game, 0, hand=[bolt])
    script(game, 0, pass_priority(), act(Bolt))
    run_scripts(game)
    # Both players passed on an empty stack, so the Bolt was cast in the next step.
    assert (game.phase, game.step) == (Phase.COMBAT, Step.BEGIN_COMBAT)
    assert _on_stack(game, bolt)


def test_a_dry_script_passes():
    game, blade = _with_blade("one")
    assert take_priority(game, game.players[0]) is True
    run_scripts(game)
    assert game.stack.is_empty() and game.get_hand(game.players[0]).contains(blade)


def test_responses_alternate_priority_and_stop_with_the_stack_in_place():
    game = _game()
    blade, bolt = BladeCard("one"), Bolt()
    set_board_state(game, 0, hand=[blade])
    set_board_state(game, 1, hand=[bolt])
    script(game, 0, act(BladeCard))
    script(game, 1, act(Bolt))
    run_scripts(game)
    assert [obj.source for obj in game.stack._items][-1] is bolt
    assert len(game.stack) == 2


# ---------------------------------------------------------------------------
# Choices raised while casting or resolving
# ---------------------------------------------------------------------------


def _named_intent(source: str, names, negative: bool, branches) -> Intent:
    """An intent choosing objects by name: ``names`` is one branch, or
    ``branches`` lists several, tried in order after each rejection."""
    return Intent(
        pattern=GameRef(card=frozenset({("name", source)})),
        preferences=tuple(Decision.obj(name=name) for name in names),
        negative=negative,
        branches=[[Decision.obj(name=name) for name in b] for b in branches],
    )


def _chooser_game(illegal=()):
    game = _game()
    chooser = Chooser(illegal)
    set_board_state(game, 0, hand=[chooser], battlefield=[_artifact("Bad"), _artifact("Good")])
    return game, chooser


def _choose(*names, negative=False, branches=()) -> Intent:
    return _named_intent("Chooser", names, negative, branches)


def test_choice_intents_answer_resolution_time_choices():
    game, chooser = _chooser_game()
    game.players[0].start_intent("choose", _choose("Good"))
    cast_card(game, game.players[0], chooser)
    assert chooser.chosen == "Good"


def test_rejected_resolution_choice_retries_from_before_the_object_resolved():
    game, chooser = _chooser_game(illegal={"Bad"})
    game.players[0].start_intent("choose", _choose(branches=[["Bad"], ["Good"]]))
    cast_card(game, game.players[0], chooser)
    assert chooser.chosen == "Good"
    assert game.get_graveyard(game.players[0]).contains(chooser)
    queries = [r for r in game.players[0].transcript.all() if r.query.prompt == "Choose one"]
    assert len(queries) == 2


def test_resolution_choice_fails_once_its_branches_are_exhausted():
    game, chooser = _chooser_game(illegal={"Bad", "Good"})
    game.players[0].start_intent("choose", _choose(branches=[["Bad"], ["Good"]]))
    with pytest.raises(PostconditionError):
        cast_card(game, game.players[0], chooser)


def test_a_resolution_choice_with_one_branch_fails_on_its_rejection():
    game, chooser = _chooser_game(illegal={"Bad"})
    game.players[0].start_intent("choose", _choose("Bad", "Good"))
    with pytest.raises(PostconditionError):
        cast_card(game, game.players[0], chooser)


def test_negative_resolution_choice_counts_as_a_pass():
    game, chooser = _chooser_game(illegal={"Bad"})
    game.players[0].start_intent("choose", _choose("Bad", negative=True))
    cast_card(game, game.players[0], chooser)
    # Rolled back to the rejected choice, and the resolution ended there.
    assert chooser.chosen is None and not _on_stack(game, chooser)


def test_negative_choice_while_casting_counts_as_a_pass():
    game = _game()
    spell = ChoosingCast(illegal={"Bad"})
    set_board_state(game, 0, hand=[spell], battlefield=[_artifact("Bad")])
    game.players[0].start_intent(
        "choose",
        Intent(
            pattern=GameRef(card=frozenset({("name", "Choosing Cast")})),
            preferences=(Decision.obj(name="Bad"),),
            negative=True,
        ),
    )
    script(game, 0, act(ChoosingCast))
    run_scripts(game)
    assert game.stack.is_empty() and game.get_hand(game.players[0]).contains(spell)


# ---------------------------------------------------------------------------
# The helpers are one-entry scripts
# ---------------------------------------------------------------------------


def test_cast_card_raises_the_engine_error_for_a_rejected_cast():
    game = _game()
    costly = Costly()
    with pytest.raises(CastingError):
        cast_card(game, game.players[0], costly)
    assert game.get_hand(game.players[0]).contains(costly)


def test_cast_card_leaves_the_players_own_script_alone():
    game = _game()
    script(game, 0, pass_priority())
    cast_card(game, game.players[0], Bolt(), resolve=False)
    assert [e.kind.value for e in game.players[0].pending_entries] == ["pass"]


def test_activate_card_ability_raises_ability_error_when_not_offered():
    from engine.abilities import AbilityError

    game = _game()
    rock = _artifact("Rock")
    set_board_state(game, 1, battlefield=[rock])
    with pytest.raises(AbilityError):
        activate_card_ability(game, game.players[0], rock)
    resolve_stack(game)


# ---------------------------------------------------------------------------
# Rejection boundaries (DECISION-MODEL.md › Legality › Rejection boundary)
# ---------------------------------------------------------------------------


def _life(game, seat=0) -> int:
    return game.players[seat].life


def test_an_abandoned_choice_keeps_the_effects_before_it():
    game, chooser = _chooser_game(illegal={"Bad"})
    chooser.gain = 3
    game.players[0].start_intent("choose", _choose("Bad", negative=True))
    cast_card(game, game.players[0], chooser)
    assert _life(game) == 23 and chooser.chosen is None


def test_a_retried_choice_does_not_repeat_the_effects_before_it():
    game, chooser = _chooser_game(illegal={"Bad"})
    chooser.gain = 3
    game.players[0].start_intent("choose", _choose(branches=[["Bad"], ["Good"]]))
    cast_card(game, game.players[0], chooser)
    assert _life(game) == 23 and chooser.chosen == "Good"


def _drive_priority_loop(game, chooser):
    script(game, 0, act(Chooser))
    run_scripts(game)
    priority_loop(game)


def _drive_run_scripts(game, chooser):
    script(game, 0, act(Chooser), pass_priority())
    script(game, 1, pass_priority(), pass_priority())
    run_scripts(game)


def _drive_resolve_stack(game, chooser):
    script(game, 0, act(Chooser))
    run_scripts(game)
    resolve_stack(game)


@pytest.mark.parametrize("drive", [_drive_priority_loop, _drive_run_scripts, _drive_resolve_stack],
                         ids=["priority_loop", "run_scripts", "resolve_stack"])
def test_every_driver_retries_a_rejected_resolution_choice_the_same_way(drive):
    game, chooser = _chooser_game(illegal={"Bad"})
    chooser.gain = 3
    game.players[0].start_intent("choose", _choose(branches=[["Bad"], ["Good"]]))
    drive(game, chooser)
    assert chooser.chosen == "Good" and _life(game) == 23
    assert game.get_graveyard(game.players[0]).contains(chooser)


class Picker(Sorcery):
    """Picks twice while resolving, each pick its own attempt: a picked artifact
    gains its controller 1 life, and ``illegal`` picks are rejected."""

    def __init__(self, illegal=(), **kwargs) -> None:
        super().__init__(name="Picker", mana_cost=ManaCost(), **kwargs)
        self.illegal = set(illegal)
        self.picks: list[str | None] = []

    def on_resolve(self, game) -> None:
        for _ in range(2):
            took, name = attempts.attempt(game, lambda: self._pick(game))
            self.picks.append(name if took else None)

    def _pick(self, game) -> str:
        candidates = game.get_battlefield(self.controller).get_all()
        chosen = choose_object(game, self.controller, candidates, "Pick one", source_card=self)
        if chosen.name in self.illegal:
            raise InvalidPlayerChoiceError(f"{chosen.name} cannot be picked")
        gain_life(game, self.controller, 1)
        return chosen.name


def _picker_game(illegal=()):
    game = _game()
    picker = Picker(illegal)
    set_board_state(game, 0, hand=[picker], battlefield=[_artifact("Good"), _artifact("Bad")])
    return game, picker


def _pick(*names, negative=False, branches=()) -> Intent:
    return _named_intent("Picker", names, negative, branches)


def test_abandoned_attempts_let_the_resolution_go_on():
    game, picker = _picker_game(illegal={"Bad"})
    game.players[0].start_intent("pick", _pick("Bad", negative=True))
    cast_card(game, game.players[0], picker)
    # Both picks were rejected and abandoned; the resolution still finished.
    assert picker.picks == [None, None] and _life(game) == 20
    assert game.get_graveyard(game.players[0]).contains(picker)


def test_each_attempt_retries_its_own_rejected_pick():
    game, picker = _picker_game(illegal={"Bad"})
    game.players[0].start_intent("pick", _pick(branches=[["Bad"], ["Good"]]))
    cast_card(game, game.players[0], picker)
    # Each pick is a fresh attempt from its first branch: Bad is rejected and
    # Good taken, twice.
    assert picker.picks == ["Good", "Good"] and _life(game) == 22


def test_an_attempt_that_exhausts_its_branches_fails():
    game, picker = _picker_game(illegal={"Bad", "Good"})
    game.players[0].start_intent("pick", _pick(branches=[["Bad"], ["Good"]]))
    with pytest.raises(PostconditionError):
        cast_card(game, game.players[0], picker)


class OnceBadPicker(Picker):
    """Rejects Bad only on its second pick, after a first legal pick."""

    def _pick(self, game) -> str:
        self.illegal = {"Bad"} if self.picks else set()
        return super()._pick(game)


def test_a_later_rejected_attempt_keeps_an_earlier_successful_one():
    game = _game()
    picker = OnceBadPicker()
    set_board_state(game, 0, hand=[picker], battlefield=[_artifact("Bad"), _artifact("Good")])
    game.players[0].start_intent("pick", _pick(branches=[["Bad"], ["Good"]]))
    cast_card(game, game.players[0], picker)
    assert picker.picks == ["Bad", "Good"] and _life(game) == 22


def test_an_exhausted_later_attempt_keeps_the_earlier_one_in_place():
    game = _game()
    picker = OnceBadPicker()
    set_board_state(game, 0, hand=[picker], battlefield=[_artifact("Bad")])
    game.players[0].start_intent("pick", _pick("Bad"))
    with pytest.raises(PostconditionError):
        cast_card(game, game.players[0], picker)
    assert picker.picks == ["Bad"] and _life(game) == 21


# ---------------------------------------------------------------------------
# Who owns a rejection
# ---------------------------------------------------------------------------


def _choosing_cast_game(illegal=("Bad",)):
    game = _game()
    spell = ChoosingCast(illegal=set(illegal))
    artifacts = [_artifact("Bad"), _artifact("Good")]
    set_board_state(game, 0, hand=[spell, Bolt()], battlefield=artifacts)
    return game, spell


def _cast_choice(*names, negative=False, branches=()) -> Intent:
    return _named_intent("Choosing Cast", names, negative, branches)


def test_a_choice_intent_during_a_cast_retries_its_next_branch_and_keeps_the_entry():
    game, spell = _choosing_cast_game()
    game.players[0].start_intent("choose", _cast_choice(branches=[["Bad"], ["Good"]]))
    script(game, 0, act(ChoosingCast), act(Bolt))
    take_priority(game, game.players[0])
    assert _on_stack(game, spell)
    assert [e.describe() for e in game.players[0].pending_entries] == ["act(Bolt)"]


class TwoChooser(Sorcery):
    """While resolving, ``first`` and then ``second`` (seats) each choose an
    artifact on its own query; ``illegal`` second choices are rejected."""

    def __init__(self, first=0, second=0, illegal=(), **kwargs) -> None:
        super().__init__(name="Two Chooser", mana_cost=ManaCost(), **kwargs)
        self.first, self.second, self.illegal = first, second, set(illegal)
        self.firsts = Artifact(name="First Source", mana_cost=ManaCost())
        self.seconds = Artifact(name="Second Source", mana_cost=ManaCost())
        self.chosen: tuple[str, str] | None = None

    def on_resolve(self, game) -> None:
        candidates = [c for p in game.players for c in game.get_battlefield(p).get_all()]
        first, second = game.players[self.first], game.players[self.second]
        a = choose_object(game, first, candidates, "First", source_card=self.firsts)
        b = choose_object(game, second, candidates, "Second", source_card=self.seconds)
        if b.name in self.illegal:
            raise InvalidPlayerChoiceError(f"{b.name} cannot be chosen second")
        self.chosen = (a.name, b.name)


def _sourced(source: str, *names, negative=False, branches=()) -> Intent:
    return _named_intent(source, names, negative, branches)


def _two_chooser_game(**kwargs):
    game = _game()
    card = TwoChooser(**kwargs)
    set_board_state(game, 0, hand=[card], battlefield=[_artifact("Bad"), _artifact("Good")])
    return game, card


def test_a_resolution_rejection_retries_the_intent_that_owns_it_not_an_earlier_one():
    game, card = _two_chooser_game(illegal={"Bad"})
    p0 = game.players[0]
    p0.start_intent("first", _sourced("First Source", "Good"))
    p0.start_intent("second", _sourced("Second Source", branches=[["Bad"], ["Good"]]))
    cast_card(game, p0, card)
    assert card.chosen == ("Good", "Good")


def test_only_the_player_who_owns_a_rejection_hears_it():
    game, card = _two_chooser_game(first=0, second=1, illegal={"Bad"})
    p0, p1 = game.players
    p0.start_intent("first", _sourced("First Source", branches=[["Bad"], ["Good"]]))
    p1.start_intent("second", _sourced("Second Source", branches=[["Bad"], ["Good"]]))
    cast_card(game, p0, card)
    # Player 0's Bad was legal and kept; only player 1 fell back to Good.
    assert card.chosen == ("Bad", "Good")


# ---------------------------------------------------------------------------
# Negative intents
# ---------------------------------------------------------------------------


def test_a_negative_choice_that_takes_effect_while_casting_fails():
    game, _spell = _choosing_cast_game(illegal=())
    game.players[0].start_intent("choose", _cast_choice("Bad", negative=True))
    script(game, 0, act(ChoosingCast))
    with pytest.raises(PostconditionError):
        run_scripts(game)


def test_a_negative_choice_that_takes_effect_while_resolving_fails():
    game, chooser = _chooser_game()
    game.players[0].start_intent("choose", _choose("Bad", negative=True))
    with pytest.raises(PostconditionError):
        cast_card(game, game.players[0], chooser)


def test_a_negative_intent_whose_choice_is_not_offered_checks_nothing():
    game, chooser = _chooser_game()
    game.players[0].start_intent("choose", _choose("Missing", negative=True))
    cast_card(game, game.players[0], chooser)
    game.players[0].end_intent("choose")
    assert chooser.chosen == "Bad"


def test_a_later_unrelated_rejection_does_not_mask_a_forbidden_choice():
    game, card = _two_chooser_game(illegal={"Bad"})
    p0 = game.players[0]
    p0.start_intent("first", _sourced("First Source", "Bad", negative=True))
    p0.start_intent("second", _sourced("Second Source", branches=[["Bad"], ["Good"]]))
    with pytest.raises(PostconditionError, match="negative intent forbids"):
        cast_card(game, p0, card)


def test_a_negative_choice_outside_any_attempt_fails_at_end_intent():
    game = _game()
    bad = _artifact("Bad")
    set_board_state(game, 0, battlefield=[bad])
    p0 = game.players[0]
    p0.start_intent("choose", _sourced("Bad", "Bad", negative=True))
    choose_object(game, p0, [bad], "Choose one", source_card=bad)
    with pytest.raises(PostconditionError):
        p0.end_intent("choose")


# ---------------------------------------------------------------------------
# run_scripts keeps the priority round between calls
# ---------------------------------------------------------------------------


def test_one_pass_carries_over_to_the_next_call_on_an_empty_stack():
    game = _game()
    bolt = Bolt()
    set_board_state(game, 0, hand=[bolt])
    script(game, 0, pass_priority())
    run_scripts(game)
    assert game.priority_player_index == 1
    script(game, 0, act(Bolt))
    run_scripts(game)
    # Player 1's dry pass completed the round, so the Bolt went in the next step.
    assert (game.phase, game.step) == (Phase.COMBAT, Step.BEGIN_COMBAT) and _on_stack(game, bolt)


def test_two_passes_on_an_empty_stack_move_on_at_the_next_call():
    game = _game()
    bolt = Bolt()
    set_board_state(game, 0, hand=[bolt])
    script(game, 0, pass_priority())
    script(game, 1, pass_priority())
    run_scripts(game)
    assert (game.phase, game.step) == (Phase.PRECOMBAT_MAIN, None)
    script(game, 0, act(Bolt))
    run_scripts(game)
    assert (game.phase, game.step) == (Phase.COMBAT, Step.BEGIN_COMBAT) and _on_stack(game, bolt)


def test_two_passes_over_a_spell_resolve_it_at_the_next_call():
    game, blade = _with_blade("one")
    bolt = Bolt()
    set_board_state(game, 0, hand=[blade, bolt])
    script(game, 0, act(BladeCard), pass_priority())
    script(game, 1, pass_priority())
    run_scripts(game)
    assert _on_stack(game, blade)
    script(game, 0, act(Bolt))
    run_scripts(game)
    assert not _on_stack(game, blade) and _on_stack(game, bolt)


def test_priority_stays_with_a_player_who_acted():
    game = _game()
    set_board_state(game, 0, hand=[Bolt()])
    script(game, 0, act(Bolt))
    run_scripts(game)
    assert game.priority_player_index == 0
    script(game, 0, pass_priority())
    run_scripts(game)
    assert game.priority_player_index == 1 and len(game.stack) == 1


def test_resolve_stack_starts_a_fresh_round():
    game = _game()
    bolt, second = Bolt(), Bolt()
    set_board_state(game, 0, hand=[bolt, second])
    script(game, 0, act(Bolt), pass_priority())
    run_scripts(game)
    resolve_stack(game)
    script(game, 0, act(Bolt))
    run_scripts(game)
    # The active player acted first in the fresh round, still in the main phase.
    assert (game.phase, game.step) == (Phase.PRECOMBAT_MAIN, None) and len(game.stack) == 1


def test_advance_to_phase_starts_a_fresh_round():
    game = _game()
    set_board_state(game, 0, hand=[Bolt()])
    script(game, 0, pass_priority())
    run_scripts(game)
    advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
    script(game, 0, act(Bolt))
    run_scripts(game)
    assert (game.phase, game.step) == (Phase.POSTCOMBAT_MAIN, None) and len(game.stack) == 1


def test_an_exact_priority_budget_is_enough():
    game = _game()
    set_board_state(game, 0, hand=[Bolt()])
    script(game, 0, act(Bolt))
    run_scripts(game, max_priority=1)
    assert len(game.stack) == 1


def test_an_insufficient_priority_budget_fails():
    game = _game()
    set_board_state(game, 0, hand=[Bolt()])
    script(game, 0, pass_priority(), act(Bolt))
    with pytest.raises(test_utils.TestSetupError):
        run_scripts(game, max_priority=1)


# ---------------------------------------------------------------------------
# Review round 2: the enclosing action, handler-wide ranks, abandoned
# resolutions, ordinary players, and the shared priority round
# ---------------------------------------------------------------------------


class OpponentCast(Sorcery):
    """While being cast, asks the opponent to choose an artifact; Bad is refused."""

    def __init__(self, **kwargs) -> None:
        super().__init__(name="Opponent Cast", mana_cost=ManaCost(), **kwargs)

    def cast_offers(self, game, player, from_zone, mode):
        return [(self, lambda: self._cast(game, player))]

    def _cast(self, game, player):
        opponent = game.players[1 - game.players.index(player)]
        candidates = [c for p in game.players for c in game.get_battlefield(p).get_all()]
        chosen = choose_object(game, opponent, candidates, "Opponent chooses", source_card=self)
        if chosen.name == "Bad":
            raise InvalidPlayerChoiceError("Bad cannot be chosen")
        return cast_spell(game, player, self)


def _opponent_cast_game(*entries):
    game = _game()
    spell = OpponentCast()
    artifacts = [_artifact("Bad"), _artifact("Good")]
    set_board_state(game, 0, hand=[spell, Bolt()], battlefield=artifacts)
    game.players[1].start_intent("choose", _sourced("Opponent Cast", branches=[["Bad"], ["Good"]]))
    script(game, 0, *entries)
    return game, spell


def test_another_players_rejected_choice_keeps_the_casters_entry():
    game, spell = _opponent_cast_game(act(OpponentCast), act(Bolt))
    assert take_priority(game, game.players[0]) is False
    assert _on_stack(game, spell) and len(game.stack) == 1
    assert [e.describe() for e in game.players[0].pending_entries] == ["act(Bolt)"]


def test_another_players_rejected_choice_retries_a_casters_last_entry():
    game, spell = _opponent_cast_game(act(OpponentCast))
    assert take_priority(game, game.players[0]) is False
    assert _on_stack(game, spell) and game.players[0].pending_entries == ()


class PairChooser(Sorcery):
    """Resolving, chooses one of Bad/Good plus a mandatory Followup — in one
    combined query or two decomposed ones — and refuses any pair with Bad."""

    def __init__(self, combined: bool, illegal=("Bad",), followup="Followup", **kwargs) -> None:
        super().__init__(name="Pair Chooser", mana_cost=ManaCost(), **kwargs)
        self.combined, self.illegal, self.followup = combined, set(illegal), followup
        self.chosen: list[str] | None = None

    def on_resolve(self, game) -> None:
        cards = {c.name: c for c in game.get_battlefield(self.controller).get_all()}
        pick = [cards["Bad"], cards["Good"]]
        follow = [cards[self.followup]]
        if self.combined:
            chosen = choose_object(game, self.controller, pick + follow, "Choose two",
                                   source_card=self, min=2, max=2)
        else:
            chosen = [choose_object(game, self.controller, pick, "Choose one", source_card=self),
                      choose_object(game, self.controller, follow, "Then", source_card=self)]
        names = sorted(c.name for c in chosen)
        if self.illegal & set(names) or self.followup not in names:
            raise InvalidPlayerChoiceError(f"{names} cannot be chosen")
        self.chosen = names


def _pair_game(combined: bool, *prefs, negative=False, branches=(), **kwargs):
    game = _game()
    card = PairChooser(combined, **kwargs)
    artifacts = [_artifact(n) for n in ("Bad", "Good", "Followup", "Filler")]
    set_board_state(game, 0, hand=[card], battlefield=artifacts)
    game.players[0].start_intent(
        "pair", _sourced("Pair Chooser", *prefs, negative=negative, branches=branches)
    )
    return game, card


_PAIR_BRANCHES = [["Bad", "Followup"], ["Good", "Followup"]]


@pytest.mark.parametrize("combined", [True, False], ids=["combined", "decomposed"])
def test_a_rejection_retries_the_owning_handlers_next_branch_across_its_queries(combined):
    game, card = _pair_game(combined, branches=_PAIR_BRANCHES)
    cast_card(game, game.players[0], card)
    assert card.chosen == ["Followup", "Good"]


@pytest.mark.parametrize("combined", [True, False], ids=["combined", "decomposed"])
def test_a_single_branch_is_not_revised_after_a_rejection(combined):
    """Good is preferred too, but only in the one branch that chose Bad."""
    game, card = _pair_game(combined, "Bad", "Good", "Followup")
    with pytest.raises(PostconditionError):
        cast_card(game, game.players[0], card)


def test_a_rejection_owned_by_a_mandatory_fill_advances_its_handlers_branch():
    game, card = _pair_game(False, branches=[["Bad"], ["Good"]], followup="Filler")
    cast_card(game, game.players[0], card)
    assert card.chosen == ["Filler", "Good"]


@pytest.mark.parametrize("combined", [True, False], ids=["combined", "decomposed"])
def test_a_handler_that_runs_out_of_branches_fails(combined):
    game, card = _pair_game(combined, branches=_PAIR_BRANCHES, illegal=("Bad", "Good"))
    with pytest.raises(PostconditionError):
        cast_card(game, game.players[0], card)


@pytest.mark.parametrize("combined", [True, False], ids=["combined", "decomposed"])
def test_a_negative_handlers_rejection_counts_as_a_pass(combined):
    game, card = _pair_game(combined, "Bad", negative=True)
    cast_card(game, game.players[0], card)
    assert card.chosen is None


def _in_zone(game, card, zone, seat=0) -> bool:
    return game.players[seat].zones[zone].contains(card)


def _abandon_through_priority_loop(game, card):
    script(game, 0, act(card_class(card)))
    run_scripts(game)
    priority_loop(game)


def _abandon_through_run_scripts(game, card):
    script(game, 0, act(card_class(card)), pass_priority())
    script(game, 1, pass_priority(), pass_priority())
    run_scripts(game)


def _abandon_through_resolve_stack(game, card):
    script(game, 0, act(card_class(card)))
    run_scripts(game)
    resolve_stack(game)


def card_class(card) -> type:
    return type(card)


@pytest.mark.parametrize("drive", [_abandon_through_priority_loop, _abandon_through_run_scripts,
                                   _abandon_through_resolve_stack],
                         ids=["priority_loop", "run_scripts", "resolve_stack"])
def test_an_abandoned_resolution_still_moves_the_spell_off_the_stack(drive):
    game, chooser = _chooser_game(illegal={"Bad"})
    chooser.gain = 3
    game.players[0].start_intent("choose", _choose("Bad", negative=True))
    drive(game, chooser)
    assert game.stack.is_empty() and not _in_zone(game, chooser, Zone.STACK)
    assert _in_zone(game, chooser, Zone.GRAVEYARD) and _life(game) == 23


def test_an_abandoned_flashback_resolution_exiles_the_spell():
    game = _game()
    chooser = Chooser(illegal={"Bad"})
    chooser.flashback_cost = ManaCost()
    set_board_state(game, 0, graveyard=[chooser], battlefield=[_artifact("Bad"), _artifact("Good")])
    game.players[0].start_intent("choose", _choose("Bad", negative=True))
    script(game, 0, act(Chooser))
    run_scripts(game)
    resolve_stack(game)
    assert not _in_zone(game, chooser, Zone.STACK) and _in_zone(game, chooser, Zone.EXILE)


def test_an_abandoned_copy_ceases_to_exist_and_the_original_below_stays_pending():
    game, chooser = _chooser_game(illegal={"Bad"})
    game.players[0].start_intent("choose", _choose("Bad", negative=True))
    script(game, 0, act(Chooser))
    run_scripts(game)
    copy = copy_spell(game, game.stack.peek(), game.players[0])
    game.stack.push(copy)
    resolve_stack(game)
    # The copy was abandoned and ceased to exist; play stopped with the original pending.
    assert [obj.source for obj in game.stack._items] == [chooser]
    assert not any(game.players[0].zones[z].contains(copy.source) for z in Zone)
    game.players[0].end_intent("choose")
    game.players[0].start_intent("choose", _choose("Good"))
    resolve_stack(game)
    assert chooser.chosen == "Good" and _in_zone(game, chooser, Zone.GRAVEYARD)


class SelfExiler(Chooser):
    """Exiles itself, then chooses: an effect that has already moved its source."""

    def on_resolve(self, game) -> None:
        move_to_zone(game, self, Zone.STACK, Zone.EXILE)
        super().on_resolve(game)


def test_an_abandoned_resolution_does_not_move_a_source_its_effect_already_moved():
    game = _game()
    card = SelfExiler(illegal={"Bad"})
    set_board_state(game, 0, hand=[card], battlefield=[_artifact("Bad"), _artifact("Good")])
    game.players[0].start_intent("choose", _choose("Bad", negative=True))
    cast_card(game, game.players[0], card)
    assert _in_zone(game, card, Zone.EXILE) and not _in_zone(game, card, Zone.GRAVEYARD)
    assert not _in_zone(game, card, Zone.STACK)


def test_an_abandoned_ability_leaves_its_source_where_it_is():
    game = _game()
    source = _artifact("Source")
    set_board_state(game, 0, battlefield=[source, _artifact("Bad"), _artifact("Good")])
    chooser = Chooser(illegal={"Bad"})
    chooser.controller = game.players[0]
    game.stack.push(StackObject(source=source, controller=game.players[0],
                                on_resolve=chooser.on_resolve))
    game.players[0].start_intent("choose", _choose("Bad", negative=True))
    resolve_stack(game)
    assert game.stack.is_empty() and _in_zone(game, source, Zone.BATTLEFIELD)


# ---- ordinary Player implementations ----------------------------------------


class PlainPlayer(Player):
    """A Player with no intents: it picks by name in order and answers a
    rejection with ``verdict`` (``None`` keeps the default raise). Its
    decision-side state is listed in ``rollback_exempt``, as the hook requires."""

    rollback_exempt = frozenset({"picks", "verdict", "heard"})

    def __init__(self, name: str, picks=(), verdict=None) -> None:
        super().__init__(name)
        self.picks = list(picks)
        self.verdict = verdict
        self.heard: list[int] = []

    def answer(self, query):
        for name in self.picks:
            for option in query.options:
                if dict(option.attrs).get("name") == name:
                    return Answer(selected=(option,))
        return Answer(selected=query.options[:query.min])

    def on_attempt_rejected(self, context, answer, error):
        self.heard.append(self.life)
        if self.verdict is None:
            return super().on_attempt_rejected(context, answer, error)
        if self.verdict == "retry":
            self.picks.pop(0)
        return self.verdict


def _plain_game(p0):
    game = engine_create_game(p0, PlainPlayer("Player2"), [], [])
    game.phase, game.step = Phase.PRECOMBAT_MAIN, None
    for player in game.players:
        player.game = game
    set_board_state(game, 0, battlefield=[_artifact("Bad"), _artifact("Good")])
    return game


def _gain_choose_gain(game, player):
    """Gain 2, choose an artifact, gain 3; Bad is refused."""
    gain_life(game, player, 2)
    candidates = game.get_battlefield(player).get_all()
    chosen = choose_object(game, player, candidates, "Choose", source_card=candidates[0])
    gain_life(game, player, 3)
    if chosen.name == "Bad":
        raise InvalidPlayerChoiceError("Bad cannot be chosen")
    return chosen.name


def _resolve_plain(game, operation):
    game.stack.push(StackObject(source=None, controller=game.players[0], on_resolve=operation))
    return resolve_top_of_stack(game)


@pytest.mark.parametrize(("verdict", "life", "completed"),
                         [("retry", 25, True), ("pass", 22, False)])
def test_an_ordinary_player_hears_a_resolution_rejection_after_the_rollback(
    verdict, life, completed
):
    p0 = PlainPlayer("Player1", picks=["Bad", "Good"], verdict=verdict)
    game = _plain_game(p0)
    assert _resolve_plain(game, lambda g: _gain_choose_gain(g, p0)) is completed
    assert p0.heard == [22] and p0.life == life


def test_an_ordinary_players_default_raises_after_the_rollback():
    p0 = PlainPlayer("Player1", picks=["Bad"])
    game = _plain_game(p0)
    with pytest.raises(InvalidPlayerChoiceError):
        _resolve_plain(game, lambda g: _gain_choose_gain(g, p0))
    assert p0.heard == [22] and p0.life == 22


def test_an_ordinary_players_explicit_attempt_is_rolled_back_alone():
    p0 = PlainPlayer("Player1", verdict="pass")
    game = _plain_game(p0)
    results = []

    def resolve(g):
        for name in ("Good", "Bad"):
            p0.picks = [name]
            results.append(attempts.attempt(g, lambda: _gain_choose_gain(g, p0)))

    assert _resolve_plain(game, resolve) is True
    # The first attempt took Good (+5); the second, Bad, rolled back to its own start.
    assert results == [(True, "Good"), (False, None)] and p0.life == 25


# ---- effect-granted casts ---------------------------------------------------


class Refused(Sorcery):
    """A spell its own rules refuse to cast."""

    def __init__(self, **kwargs) -> None:
        super().__init__(name="Refused", mana_cost=ManaCost(), **kwargs)

    def can_cast(self, game) -> bool:
        return False


class GrantedCaster(Sorcery):
    """Resolving, lets its controller choose and cast free one card from each
    of ``offers`` — each cast its own attempt, as Uldaros casts its copies."""

    def __init__(self, offers, **kwargs) -> None:
        super().__init__(name="Granted Caster", mana_cost=ManaCost(), **kwargs)
        self.offers = offers
        self.casts: list[bool] = []

    def on_resolve(self, game) -> None:
        player = self.controller
        for offer in self.offers:
            took, _ = attempts.attempt(game, lambda o=offer: self._cast_one(game, player, o))
            self.casts.append(took)

    def _cast_one(self, game, player, offer):
        card = choose_object(game, player, offer, "Cast which?", source_card=self)
        return cast_spell_free(game, player, card, Zone.HAND)


def _granted_game(*names, negative=False, branches=()):
    game = _game()
    first, refused, second = Bolt(), Refused(), Bolt()
    caster = GrantedCaster([[first], [refused, second]])
    set_board_state(game, 0, hand=[caster, first, refused, second])
    game.players[0].start_intent("cast", _named_intent("Granted Caster", names, negative, branches))
    return game, caster, first, refused, second


def test_a_rejected_later_granted_cast_retries_and_keeps_the_earlier_cast():
    game, caster, first, refused, second = _granted_game(branches=[["Refused"], ["Bolt"]])
    cast_card(game, game.players[0], caster, resolve=False)
    resolve_top_of_stack(game)
    assert caster.casts == [True, True] and _in_zone(game, refused, Zone.HAND)
    assert [obj.source for obj in game.stack._items] == [first, second]


def test_an_abandoned_later_granted_cast_keeps_the_earlier_cast():
    game, caster, first, refused, _second = _granted_game("Refused", negative=True)
    cast_card(game, game.players[0], caster, resolve=False)
    resolve_top_of_stack(game)
    assert caster.casts == [True, False] and _in_zone(game, refused, Zone.HAND)
    assert [obj.source for obj in game.stack._items] == [first]


# ---- the shared priority round ----------------------------------------------


def _one_pass_then(game, operation):
    set_board_state(game, 0, hand=[Bolt()])
    script(game, 0, pass_priority())
    run_scripts(game)
    assert (game.priority_player_index, game.priority_passes) == (1, 1)
    operation(game)
    script(game, 0, act(Bolt))
    run_scripts(game)


def test_an_empty_resolve_stack_starts_a_fresh_round():
    game = _game()
    _one_pass_then(game, resolve_stack)
    assert (game.phase, game.step) == (Phase.PRECOMBAT_MAIN, None) and len(game.stack) == 1


def test_a_direct_resolution_starts_a_fresh_round():
    game = _game()

    def resolve_directly(g):
        g.stack.push(StackObject(source=None, controller=g.players[1], on_resolve=lambda _g: None))
        resolve_top_of_stack(g)

    _one_pass_then(game, resolve_directly)
    assert (game.phase, game.step) == (Phase.PRECOMBAT_MAIN, None) and len(game.stack) == 1


def test_advance_game_to_phase_starts_a_fresh_round():
    game = _game()
    _one_pass_then(game, lambda g: advance_game_to_phase(g, Phase.POSTCOMBAT_MAIN))
    assert (game.phase, game.step) == (Phase.POSTCOMBAT_MAIN, None) and len(game.stack) == 1


def test_an_action_between_calls_starts_a_fresh_round():
    game = _game()
    set_board_state(game, 1, hand=[Bolt()])

    def opponent_acts(g):
        cast_card(g, g.players[1], g.get_hand(g.players[1]).get_all()[0], resolve=False)

    _one_pass_then(game, opponent_acts)
    # Player 1 acted and kept priority, then passed; player 0's Bolt answered in the same step.
    assert (game.phase, game.step) == (Phase.PRECOMBAT_MAIN, None) and len(game.stack) == 2


def test_two_passes_with_a_spell_pending_stay_due_when_the_scripts_run_out():
    game = _game()
    set_board_state(game, 0, hand=[Bolt(), Bolt()])
    script(game, 0, act(Bolt), pass_priority())
    script(game, 1, pass_priority())
    run_scripts(game)
    assert game.priority_passes == 2 and len(game.stack) == 1
    script(game, 0, act(Bolt))
    run_scripts(game)
    assert len(game.stack) == 1 and game.priority_passes == 0


# ---------------------------------------------------------------------------
# Review round 3: the entry owns its action's answers and ends with it,
# rollback reaches what runs outside the game, one shared priority round
# ---------------------------------------------------------------------------


class SplitCast(Sorcery):
    """While being cast, asks Bad or Good, then a mandatory Filler; a cast that
    chose an ``illegal`` one is refused."""

    def __init__(self, illegal=("Bad",), **kwargs) -> None:
        super().__init__(name="Split Cast", mana_cost=ManaCost(), **kwargs)
        self.illegal = set(illegal)
        self.chose: str | None = None

    def cast_offers(self, game, player, from_zone, mode):
        return [(self, lambda: self._cast(game, player))]

    def _cast(self, game, player):
        cards = {c.name: c for c in game.get_battlefield(player).get_all()}
        first = choose_object(game, player, [cards["Bad"], cards["Good"]], "Pick", source_card=self)
        choose_object(game, player, [cards["Filler"]], "Then", source_card=self)
        if first.name in self.illegal:
            raise InvalidPlayerChoiceError(f"{first.name} cannot be picked")
        self.chose = first.name
        return cast_spell(game, player, self)


def _split_game(*entries, illegal=("Bad",)):
    game = _game()
    spell = SplitCast(illegal=illegal)
    artifacts = [_artifact("Bad"), _artifact("Good"), _artifact("Filler")]
    set_board_state(game, 0, hand=[spell, Bolt()], battlefield=artifacts)
    script(game, 0, *entries)
    return game, spell


def _named(*names):
    return tuple(Decision.obj(name=name) for name in names)


_SPLIT_BRANCHES = [
    branch(SplitCast, choices=_named("Bad")),
    branch(SplitCast, choices=_named("Good")),
]


def test_the_entry_owns_its_mandatory_fill_and_retries_its_next_branch():
    game, spell = _split_game(act(branches=_SPLIT_BRANCHES), act(Bolt))
    assert take_priority(game, game.players[0]) is False
    assert spell.chose == "Good" and _on_stack(game, spell)
    assert [e.describe() for e in game.players[0].pending_entries] == ["act(Bolt)"]


def test_the_entry_fails_once_its_branches_are_exhausted():
    game, _spell = _split_game(act(branches=_SPLIT_BRANCHES), illegal=("Bad", "Good"))
    with pytest.raises(ScriptEntryError) as failure:
        take_priority(game, game.players[0])
    assert failure.value.reason == "rejected"
    assert not game.players[0].acting


def test_a_baseline_preference_answers_ahead_of_an_entry_fill():
    game, spell = _split_game(act(SplitCast))
    game.players[0].set_baseline(Intent(pattern=GameRef(), preferences=_named("Good")))
    assert take_priority(game, game.players[0]) is False
    assert spell.chose == "Good"


def test_an_entry_choice_answers_ahead_of_a_baseline_preference():
    game, spell = _split_game(act(SplitCast, choices=_named("Good")), illegal=("Bad",))
    game.players[0].set_baseline(Intent(pattern=GameRef(), preferences=_named("Bad")))
    assert take_priority(game, game.players[0]) is False
    assert spell.chose == "Good"


def test_an_abandoned_action_clears_its_entry():
    game = _game()
    spell = ChoosingCast(illegal={"Bad"})
    set_board_state(game, 0, hand=[spell], battlefield=[_artifact("Bad")])
    game.players[0].start_intent("choose", _sourced("Choosing Cast", "Bad", negative=True))
    script(game, 0, act(ChoosingCast))
    assert take_priority(game, game.players[0]) is True
    assert not game.players[0].acting


def test_an_abandoned_entry_does_not_answer_a_later_resolution():
    game, chooser = _chooser_game()
    spell = ChoosingCast(illegal={"Bad"})
    set_board_state(game, 0, hand=[chooser, spell], battlefield=[_artifact("Bad"), _artifact("Good")])
    p0 = game.players[0]
    script(game, 0, act(Chooser))
    run_scripts(game)
    p0.start_intent("choose", _sourced("Choosing Cast", "Bad", negative=True))
    script(game, 0, act(ChoosingCast, choices=_named("Bad")))
    assert take_priority(game, p0) is True
    p0.end_intent("choose")
    p0.set_baseline(Intent(pattern=GameRef(), preferences=_named("Good")))
    resolve_stack(game)
    assert chooser.chosen == "Good"


def test_another_players_abandoned_choice_ends_the_casters_entry():
    game, spell = _opponent_cast_game(act(OpponentCast), act(Bolt))
    game.players[1].end_intent("choose")
    game.players[1].start_intent("choose", _sourced("Opponent Cast", "Bad", negative=True))
    assert take_priority(game, game.players[0]) is True
    assert not game.players[0].acting and not _on_stack(game, spell)
    assert [e.describe() for e in game.players[0].pending_entries] == ["act(Bolt)"]


def test_a_caught_helper_failure_leaves_no_entry_behind():
    game, chooser = _chooser_game()
    costly = Costly()
    set_board_state(game, 0, hand=[chooser, costly], battlefield=[_artifact("Bad"), _artifact("Good")])
    with pytest.raises(CastingError):
        cast_card(game, game.players[0], costly)
    assert not game.players[0].acting
    game.players[0].start_intent("choose", _choose("Good"))
    cast_card(game, game.players[0], chooser)
    assert chooser.chosen == "Good"


class Visitor(Chooser):
    """Counts its resolutions on itself and gains that much life before choosing."""

    def __init__(self, illegal=(), **kwargs) -> None:
        super().__init__(illegal, **kwargs)
        self.visits = 0

    def on_resolve(self, game) -> None:
        self.visits += 1
        gain_life(game, self.controller, self.visits)
        super().on_resolve(game)


def _copied_visitor(*prefs, negative=False, branches=()):
    game = _game()
    visitor = Visitor(illegal={"Bad"})
    set_board_state(game, 0, hand=[visitor], battlefield=[_artifact("Bad"), _artifact("Good")])
    script(game, 0, act(Visitor))
    run_scripts(game)
    copy = copy_spell(game, game.stack.peek(), game.players[0])
    game.stack.push(copy)
    game.players[0].start_intent("choose", _named_intent("Chooser", prefs, negative, branches))
    return game, visitor, copy


def test_a_retried_copy_restores_the_state_only_its_stack_object_reaches():
    game, visitor, copy = _copied_visitor(branches=[["Bad"], ["Good"]])
    assert resolve_top_of_stack(game) is True
    assert copy.source.visits == 1 and _life(game) == 21 and copy.source.chosen == "Good"
    assert [obj.source for obj in game.stack._items] == [visitor]  # the original still pending


def test_an_abandoned_copy_keeps_its_effects_before_the_choice():
    game, visitor, copy = _copied_visitor("Bad", negative=True)
    assert resolve_top_of_stack(game) is False
    assert copy.source.visits == 1 and _life(game) == 21 and copy.source.chosen is None
    assert [obj.source for obj in game.stack._items] == [visitor]


def test_an_ability_callback_with_captured_state_is_retried_from_its_start():
    game, _chooser = _chooser_game(illegal={"Bad"})
    seen = {"runs": 0}
    chooser = Chooser(illegal={"Bad"})
    chooser.controller = game.players[0]

    def resolve(g):
        seen["runs"] += 1
        chooser.on_resolve(g)

    game.stack.push(StackObject(source=None, controller=game.players[0], on_resolve=resolve))
    game.players[0].start_intent("choose", _choose(branches=[["Bad"], ["Good"]]))
    assert resolve_top_of_stack(game) is True
    assert seen["runs"] == 1 and chooser.chosen == "Good"


def test_an_explicit_attempt_restores_state_only_its_callable_reaches():
    game, _chooser = _chooser_game(illegal={"Bad"})
    picker = Picker(illegal={"Bad"})
    picker.controller = game.players[0]
    calls: list[int] = []

    def pick():
        calls.append(1)
        return picker._pick(game)

    def resolve(g):
        assert attempts.attempt(g, pick) == (True, "Good")

    game.stack.push(StackObject(source=None, controller=game.players[0], on_resolve=resolve))
    game.players[0].start_intent("pick", _pick(branches=[["Bad"], ["Good"]]))
    resolve_top_of_stack(game)
    assert calls == [1]


# ---- one priority round, whichever driver runs it ---------------------------


def test_priority_loop_finishes_a_round_run_scripts_began():
    game = _game()
    bolt = Bolt()
    set_board_state(game, 0, hand=[bolt])
    script(game, 0, pass_priority())
    run_scripts(game)
    assert (game.priority_player_index, game.priority_passes) == (1, 1)
    script(game, 0, act(Bolt))
    priority_loop(game)
    # Player 1's pass completed the round: the loop returned for the step to end.
    assert game.priority_passes == 2 and game.stack.is_empty()
    assert [e.describe() for e in game.players[0].pending_entries] == ["act(Bolt)"]


def test_run_scripts_carries_on_after_priority_loop_returns():
    game = _game()
    bolt = Bolt()
    set_board_state(game, 0, hand=[bolt])
    priority_loop(game)
    assert game.priority_passes == 2
    script(game, 0, act(Bolt))
    run_scripts(game)
    # The step change both passes made due happened first.
    assert (game.phase, game.step) == (Phase.COMBAT, Step.BEGIN_COMBAT) and _on_stack(game, bolt)


def test_priority_loop_resolves_a_spell_whose_two_passes_are_due():
    game = _game()
    set_board_state(game, 0, hand=[Bolt(), Bolt()])
    script(game, 0, act(Bolt), pass_priority())
    script(game, 1, pass_priority())
    run_scripts(game)
    assert game.priority_passes == 2 and len(game.stack) == 1
    priority_loop(game)
    assert game.stack.is_empty() and len(game.get_graveyard(game.players[0]).get_all()) == 1


def test_priority_loop_gives_the_retained_priority_back_to_the_nonactive_player():
    game = _game()
    bolt = Bolt()
    set_board_state(game, 1, hand=[bolt])
    script(game, 0, pass_priority())
    script(game, 1, act(Bolt))
    run_scripts(game)
    assert (game.priority_player_index, game.priority_passes) == (1, 0)
    first = len(game.players[1].transcript.priority_queries())
    priority_loop(game)
    assert game.stack.is_empty() and game.get_graveyard(game.players[1]).contains(bolt)
    assert len(game.players[1].transcript.priority_queries()) > first


def test_zero_passes_start_the_same_round_in_either_driver():
    for drive in (run_scripts, priority_loop):
        game = _game()
        set_board_state(game, 0, hand=[Bolt()])
        script(game, 0, act(Bolt))
        drive(game)
        assert game.players[0].pending_entries == ()


# ---------------------------------------------------------------------------
# Review round 4: final nested rejections, expected-illegal branches,
# cleanup priority windows, per-question preferences
# ---------------------------------------------------------------------------


# ---- a final rejection passes enclosing attempts untouched ------------------


def test_a_final_nested_rejection_keeps_the_earlier_attempt():
    p0 = PlainPlayer("Player1")
    game = _plain_game(p0)

    def resolve(g):
        for name in ("Good", "Bad"):
            p0.picks = [name]
            attempts.attempt(g, lambda: _gain_choose_gain(g, p0))

    with pytest.raises(InvalidPlayerChoiceError):
        _resolve_plain(game, resolve)
    # The Good attempt (+5) stays; the Bad one rolled back to its own start.
    assert p0.life == 25 and p0.heard == [25]


def test_a_final_nested_rejection_is_heard_once():
    p0 = PlainPlayer("Player1")
    game = _plain_game(p0)

    def resolve(g):
        p0.picks = ["Good"]
        choose_object(g, p0, g.get_battlefield(p0).get_all(), "Outer", source_card=None)
        gain_life(g, p0, 5)
        p0.picks = ["Bad"]
        attempts.attempt(g, lambda: _gain_choose_gain(g, p0))

    with pytest.raises(InvalidPlayerChoiceError) as failure:
        _resolve_plain(game, resolve)
    assert p0.heard == [25] and p0.life == 25
    assert str(failure.value) == "Bad cannot be chosen"


def test_a_final_nested_rejection_keeps_an_earlier_granted_cast():
    p0 = PlainPlayer("Player1", picks=["Refused"])
    game = _plain_game(p0)
    first, refused, second = Bolt(), Refused(), Bolt()
    caster = GrantedCaster([[first], [refused, second]])
    caster.controller = p0
    set_board_state(game, 0, hand=[first, refused, second])
    with pytest.raises(InvalidPlayerChoiceError):
        _resolve_plain(game, caster.on_resolve)
    assert [obj.source for obj in game.stack._items] == [first] and len(p0.heard) == 1


def test_a_final_rejection_two_attempts_deep_keeps_both_outer_effects():
    p0 = PlainPlayer("Player1")
    game = _plain_game(p0)

    def resolve(g):
        gain_life(g, p0, 1)

        def middle():
            gain_life(g, p0, 10)
            p0.picks = ["Bad"]
            attempts.attempt(g, lambda: _gain_choose_gain(g, p0))

        attempts.attempt(g, middle)

    with pytest.raises(InvalidPlayerChoiceError):
        _resolve_plain(game, resolve)
    assert p0.life == 31 and p0.heard == [31]


# ---- act_illegal settles each branch before the next entry ------------------


def _bolt_cast_in_main(game) -> bool:
    return (game.phase, game.step) == (Phase.PRECOMBAT_MAIN, None) and any(
        isinstance(obj.source, Bolt) for obj in game.stack._items
    )


@pytest.mark.parametrize("negative", [False, True], ids=["positive", "negative"])
def test_act_illegal_settles_a_refused_choice_its_intent_cannot_retry(negative):
    game, spell = _choosing_cast_game()
    game.players[0].start_intent("choose", _cast_choice("Bad", negative=negative))
    script(game, 0, act_illegal(ChoosingCast), act(Bolt))
    run_scripts(game)
    assert _bolt_cast_in_main(game) and not _on_stack(game, spell)


def test_act_illegal_settles_a_refused_baseline_choice():
    game, spell = _choosing_cast_game()
    game.players[0].set_baseline(Intent(pattern=GameRef(), preferences=_named("Bad")))
    script(game, 0, act_illegal(ChoosingCast), act(Bolt))
    run_scripts(game)
    assert _bolt_cast_in_main(game) and not _on_stack(game, spell)


def test_act_illegal_settles_a_refused_choice_the_opponent_cannot_retry():
    game, spell = _opponent_cast_game(act_illegal(OpponentCast), act(Bolt))
    game.players[1].end_intent("choose")
    game.players[1].start_intent("choose", _sourced("Opponent Cast", "Bad"))
    run_scripts(game)
    assert _bolt_cast_in_main(game) and not _on_stack(game, spell)


def test_act_illegal_without_a_successor_entry_ends_its_window():
    game, spell = _choosing_cast_game()
    game.players[0].start_intent("choose", _cast_choice("Bad"))
    script(game, 0, act_illegal(ChoosingCast))
    run_scripts(game)
    assert game.stack.is_empty() and game.players[0].pending_entries == ()


def test_act_illegal_tries_its_later_branch_after_an_in_action_rejection():
    game, spell = _choosing_cast_game()
    script(game, 0, act_illegal(branches=[
        branch(ChoosingCast, choices=_named("Bad")),
        branch(ChoosingCast, choices=_named("Good")),
    ]))
    with pytest.raises(ScriptEntryError) as failure:
        run_scripts(game)
    assert failure.value.reason == "took effect"


def test_act_illegal_lets_an_intent_retry_and_fails_when_the_action_takes_effect():
    game, spell = _choosing_cast_game()
    game.players[0].start_intent("choose", _cast_choice(branches=[["Bad"], ["Good"]]))
    script(game, 0, act_illegal(ChoosingCast))
    with pytest.raises(ScriptEntryError) as failure:
        run_scripts(game)
    assert failure.value.reason == "took effect"


# ---- cleanup grants priority in a fresh window each time --------------------


def _doomed(game, player) -> Creature:
    """A 2/1 with a -1/-1 counter, kept alive until end of turn by +0/+1."""
    from engine.continuous_effects import (
        DURATION_END_OF_TURN,
        ContinuousEffect,
        Layer,
        SubLayer,
    )

    doomed = Creature(name="Doomed", mana_cost=ManaCost(), base_power=2, base_toughness=1)
    set_board_state(game, game.players.index(player), battlefield=[doomed])
    doomed.minus_one_counters = 1
    doomed._base_minus_one_counters = 1
    game.effect_manager.add(ContinuousEffect(
        source=doomed,
        layer=Layer.POWER_TOUGHNESS,
        sublayer=SubLayer.MODIFY_PT,
        apply=lambda g: setattr(doomed, "modified_toughness", doomed.base_toughness + 1),
        duration=DURATION_END_OF_TURN,
    ))
    game.effect_manager.apply_all(game)
    return doomed


def _watch_deaths(game, effect) -> None:
    """Whenever a creature dies, a trigger of player 0's resolves ``effect``."""
    from engine.events import CreatureDiesTriggeredEvent
    from engine.triggers import TriggerRegistration

    watcher = _artifact("Watcher")
    set_board_state(game, 0, battlefield=[watcher])
    game.trigger_manager.register(TriggerRegistration(
        event_type=CreatureDiesTriggeredEvent, condition=None, effect=effect,
        source=watcher, controller=game.players[0],
    ))


def test_a_script_responds_in_a_cleanup_step_that_grants_priority():
    game = _game()
    game.phase, game.step = Phase.ENDING, Step.END
    bolt = Bolt()
    set_board_state(game, 0, hand=[bolt])
    _watch_deaths(game, lambda g: gain_life(g, g.players[0], 1))
    _doomed(game, game.players[0])
    script(game, 0, pass_priority(), act(Bolt))
    run_scripts(game)
    assert (game.phase, game.step) == (Phase.ENDING, Step.CLEANUP)
    assert game.stack.peek().source is bolt and len(game.stack) == 2
    assert _life(game) == 20


def test_each_cleanup_that_grants_priority_starts_a_fresh_round():
    from engine.turn import _do_cleanup_step

    game = _game()
    game.phase, game.step = Phase.ENDING, Step.CLEANUP
    p0 = game.players[0]
    seen: list[int] = []

    def on_death(g):
        seen.append(len(p0.transcript.priority_queries()))
        if len(seen) == 1:
            _doomed(g, p0)

    _watch_deaths(game, on_death)
    _doomed(game, p0)
    _do_cleanup_step(game)
    # Each trigger resolves after both players passed in its own window.
    assert seen == [1, 3]


def test_a_cleanup_without_priority_moves_on_to_the_next_turn():
    game = _game()
    game.phase, game.step = Phase.ENDING, Step.END
    turn = game.turn_number
    script(game, 1, pass_priority(), pass_priority())
    run_scripts(game)
    assert game.turn_number == turn + 1 and game.step != Step.CLEANUP


# ---- per-question preferences -----------------------------------------------


class TypedPicker(Sorcery):
    """Resolving, chooses one artifact and one creature — distinct cards — as
    Uldaros chooses a card of each type. ``presentation`` is how the engine
    asks: ``"offer"`` offers every candidate for each type and rejects a
    wrong or repeated pick, ``"filter"`` offers only the legal ones,
    ``"bare"`` filters without annotating which type it asks for, and
    ``"combined"`` asks one question for both types."""

    TYPES = (CardType.ARTIFACT, CardType.CREATURE)

    def __init__(self, presentation: str, **kwargs) -> None:
        super().__init__(name="Typed Picker", mana_cost=ManaCost(), **kwargs)
        self.presentation = presentation
        self.picked: list = []

    def on_resolve(self, game) -> None:
        candidates = game.get_battlefield(self.controller).get_all()
        if self.presentation == "combined":
            picked = choose_object(game, self.controller, candidates, "Choose one of each type",
                                   source_card=self, min=0, max=2)
            if not _assignable(picked, self.TYPES):
                raise InvalidPlayerChoiceError("the cards cannot fill distinct types")
            self.picked = picked
            return
        for card_type in self.TYPES:
            offered = [
                c for c in candidates
                if self.presentation == "offer" or (card_type in c.card_types and c not in self.picked)
            ]
            question = None if self.presentation == "bare" else card_type
            card = choose_object(game, self.controller, offered, "Choose a card of the type",
                                 source_card=self, question=question)
            if card_type not in card.card_types or card in self.picked:
                raise InvalidPlayerChoiceError(f"{card.name} cannot be chosen as {card_type.value}")
            self.picked.append(card)


def _assignable(cards, types) -> bool:
    return len(set(map(id, cards))) == len(cards) == 2 and any(
        types[0] in a.card_types and types[1] in b.card_types
        for a, b in (cards, cards[::-1])
    )


def _golems(presentation):
    game = _game()
    picker = TypedPicker(presentation)
    first, second = (ArtifactCreature(name="Golem", base_power=1, base_toughness=1) for _ in range(2))
    set_board_state(game, 0, hand=[picker], battlefield=[first, second])
    return game, picker, first, second


@pytest.mark.parametrize("presentation", ["offer", "filter", "combined"])
def test_one_branch_answers_each_question_by_what_it_asks_for(presentation):
    game, picker, first, second = _golems(presentation)
    a, b = Decision.obj(instance=first.instance_id), Decision.obj(instance=second.instance_id)
    game.players[0].start_intent("pick", Intent(
        pattern=GameRef(card=frozenset({("name", "Typed Picker")})),
        branches=[branch(a, b, per_query={CardType.ARTIFACT: [a], CardType.CREATURE: [b]})],
    ))
    cast_card(game, game.players[0], picker)
    assert {id(c) for c in picker.picked} == {id(first), id(second)}


def test_without_per_question_preferences_a_repeated_offer_is_rejected():
    game, picker, first, second = _golems("offer")
    a, b = Decision.obj(instance=first.instance_id), Decision.obj(instance=second.instance_id)
    game.players[0].start_intent("pick", Intent(
        pattern=GameRef(card=frozenset({("name", "Typed Picker")})), preferences=(a, b),
    ))
    with pytest.raises(PostconditionError):
        cast_card(game, game.players[0], picker)


def test_a_question_payload_matches_a_decision_by_satisfies_and_refuses_strings():
    from engine.decisions import MalformedAttrsError
    from engine.queries import asks_for, validate_query

    query = PlayerQuery(source=(), prompt="", options=(), min=0, max=0,
                        question=(Decision.obj(printed=Bolt, zone="hand"),))
    assert asks_for(query, Decision.obj(printed=Bolt)) and not asks_for(query, CardType.ARTIFACT)
    with pytest.raises(MalformedAttrsError):
        validate_query(PlayerQuery(source=(), prompt="", options=(), min=0, max=0,
                                   question=("artifact",)))
    with pytest.raises(TypeError):
        branch(Bolt, per_query={"artifact": [Bolt]})


# ---- the question payload is canonical and optional --------------------------


def test_a_question_payload_refuses_custom_symbols():
    import enum

    from engine.decisions import MalformedAttrsError
    from engine.queries import validate_query

    class Custom(enum.Enum):
        THING = 1

    for payload in ((Custom.THING,), (object(),), (3,), (str,), ("artifact",)):
        with pytest.raises(MalformedAttrsError):
            validate_query(PlayerQuery(source=(), prompt="", options=(), min=0, max=0,
                                       question=payload))
    validate_query(PlayerQuery(source=(), prompt="", options=(), min=0, max=0,
                               question=(CardType.ARTIFACT, Bolt, GameRef(), Decision.obj(printed=Bolt))))


class Rock(Artifact):
    def __init__(self, **kwargs) -> None:
        super().__init__(name="Rock", mana_cost=ManaCost(), **kwargs)


class Golem(ArtifactCreature):
    def __init__(self, **kwargs) -> None:
        super().__init__(name="Golem", mana_cost=ManaCost(), base_power=1, base_toughness=1, **kwargs)


class Cub(Creature):
    def __init__(self, **kwargs) -> None:
        super().__init__(name="Cub", mana_cost=ManaCost(), base_power=1, base_toughness=1, **kwargs)


def _offers(cls, but_not=None):
    """A predicate key: the query offers an object of ``cls`` (and none of
    ``but_not``)."""
    def offered(query, wanted):
        return any(dict(o.attrs).get("printed") is wanted for o in query.options)

    return lambda query: offered(query, cls) and not (but_not and offered(query, but_not))


@pytest.mark.parametrize("presentation", ["offer", "filter", "bare", "combined"])
def test_one_branch_infers_each_question_when_no_payload_says_it(presentation):
    """Rock as the artifact, Golem as the creature: payload keys answer an
    annotated engine, predicate keys infer the questions an unannotated one
    asks from what it offers, and the base preferences answer one combined
    question."""
    game = _game()
    picker = TypedPicker(presentation)
    rock, golem, cub = Rock(), Golem(), Cub()
    set_board_state(game, 0, hand=[picker], battlefield=[golem, rock, cub])
    game.players[0].start_intent("pick", Intent(
        pattern=GameRef(card=frozenset({("name", "Typed Picker")})),
        branches=[branch(Golem, Rock, per_query={
            CardType.ARTIFACT: [Rock],
            CardType.CREATURE: [Golem],
            _offers(Rock, but_not=Cub): [Rock],
            _offers(Cub, but_not=Rock): [Golem],
        })],
    ))
    cast_card(game, game.players[0], picker)
    assert {type(c) for c in picker.picked} == {Rock, Golem}


def test_the_first_matching_per_query_key_wins():
    game, picker, first, second = _golems("filter")
    a, b = Decision.obj(instance=first.instance_id), Decision.obj(instance=second.instance_id)
    game.players[0].start_intent("pick", Intent(
        pattern=GameRef(card=frozenset({("name", "Typed Picker")})),
        branches=[branch(a, b, per_query={
            (lambda query: True): [b],
            CardType.ARTIFACT: [a],
        })],
    ))
    cast_card(game, game.players[0], picker)
    # The always-true predicate came first, so the artifact question took b.
    assert picker.picked[0] is second


def test_per_query_chooses_a_priority_action():
    game = _game()
    blade = BladeCard("one")
    set_board_state(game, 0, hand=[blade])
    script(game, 0, act(branches=[branch(BladeCard, per_query={_offers(GleamFace): [GleamFace]})]))
    run_scripts(game)
    assert blade.cast_face == "gleam"


# ---------------------------------------------------------------------------
# Review round 5: fresh choice branches per entry, forced cleanup completion,
# explicit per-question overrides
# ---------------------------------------------------------------------------


def _two_choosing_casts(first_illegal, second_illegal):
    game = _game()
    first, second = ChoosingCast(illegal=first_illegal), ChoosingCast(illegal=second_illegal)
    set_board_state(game, 0, hand=[first, second], battlefield=[_artifact("Bad"), _artifact("Good")])
    entry = lambda spell: Decision.obj(instance=spell.instance_id)  # noqa: E731
    return game, first, second, entry


@pytest.mark.parametrize("owner", ["intent", "baseline"])
def test_a_successor_entry_starts_its_choices_from_their_first_branch(owner):
    game, first, second, entry = _two_choosing_casts({"Bad", "Good"}, {"Good"})
    branches = [[Decision.obj(name="Bad")], [Decision.obj(name="Good")]]
    if owner == "intent":
        game.players[0].start_intent("choose", _cast_choice(branches=[["Bad"], ["Good"]]))
    else:
        game.players[0].set_baseline(Intent(pattern=GameRef(), branches=branches))
    script(game, 0, act_illegal(entry(first)), act(entry(second)))
    run_scripts(game)
    assert _on_stack(game, second) and not _on_stack(game, first)
    assert (game.phase, game.step) == (Phase.PRECOMBAT_MAIN, None)


def test_a_successor_illegal_entry_tries_its_legal_first_choice():
    game, first, second, entry = _two_choosing_casts({"Bad", "Good"}, {"Good"})
    game.players[0].start_intent("choose", _cast_choice(branches=[["Bad"], ["Good"]]))
    script(game, 0, act_illegal(entry(first)), act_illegal(entry(second)))
    with pytest.raises(ScriptEntryError) as failure:
        run_scripts(game)
    assert failure.value.reason == "took effect"


class PickyOpponentCast(OpponentCast):
    """An opponent's choice while casting, refusing the ``illegal`` artifacts."""

    def __init__(self, illegal, **kwargs) -> None:
        super().__init__(**kwargs)
        self.illegal = set(illegal)

    def _cast(self, game, player):
        opponent = game.players[1 - game.players.index(player)]
        candidates = [c for p in game.players for c in game.get_battlefield(p).get_all()]
        chosen = choose_object(game, opponent, candidates, "Opponent chooses", source_card=self)
        if chosen.name in self.illegal:
            raise InvalidPlayerChoiceError(f"{chosen.name} cannot be chosen")
        return cast_spell(game, player, self)


def test_an_opponents_choice_starts_from_its_first_branch_for_a_successor_entry():
    game = _game()
    first, second = PickyOpponentCast({"Bad", "Good"}), PickyOpponentCast({"Good"})
    set_board_state(game, 0, hand=[first, second], battlefield=[_artifact("Bad"), _artifact("Good")])
    game.players[1].start_intent("choose", _sourced("Opponent Cast", branches=[["Bad"], ["Good"]]))
    script(game, 0, act_illegal(Decision.obj(instance=first.instance_id)),
           act(Decision.obj(instance=second.instance_id)))
    run_scripts(game)
    assert _on_stack(game, second) and not _on_stack(game, first)


def test_a_retried_entry_keeps_its_choices_branch():
    game, spell = _choosing_cast_game()
    game.players[0].start_intent("choose", _cast_choice(branches=[["Bad"], ["Good"]]))
    script(game, 0, act(ChoosingCast))
    run_scripts(game)
    assert _on_stack(game, spell)


def _paused_in_cleanup(second_effect):
    """A script responds in cleanup with Bolt above a death trigger whose
    effect is ``second_effect``; play stops there with both pending."""
    game = _game()
    game.phase, game.step = Phase.ENDING, Step.END
    set_board_state(game, 0, hand=[Bolt()])
    made = []

    def on_death(g):
        if not made:
            made.append(second_effect(g))

    _watch_deaths(game, on_death)
    _doomed(game, game.players[0])
    script(game, 0, pass_priority(), act(Bolt))
    run_scripts(game)
    assert game.step == Step.CLEANUP and len(game.stack) == 2
    return game, made


@pytest.mark.parametrize("finish", ["resolve_stack", "advance_game_to_phase"])
def test_a_forced_helper_finishes_the_cleanup_its_window_left_pending(finish):
    game, made = _paused_in_cleanup(lambda g: _doomed(g, g.players[0]))
    if finish == "resolve_stack":
        resolve_stack(game)
    else:
        advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    (second,) = made
    # The cleanup after the window removed the new until-end-of-turn boost.
    assert not game.get_battlefield(game.players[0]).contains(second)


def test_resolve_stack_outside_cleanup_only_resolves():
    game = _game()
    set_board_state(game, 0, hand=[Bolt()])
    script(game, 0, act(Bolt))
    run_scripts(game)
    resolve_stack(game)
    assert game.stack.is_empty() and (game.phase, game.step) == (Phase.PRECOMBAT_MAIN, None)


def test_an_empty_matching_per_query_entry_declines_an_optional_choice():
    game = _game()
    rock = _artifact("Rock")
    set_board_state(game, 0, battlefield=[rock])
    player = game.players[0]
    player.set_baseline(Intent(pattern=GameRef(), branches=[
        branch(Decision.obj(name="Rock"), per_query={CardType.ARTIFACT: []}),
    ]))
    chosen = choose_object(game, player, [rock], "Choose", optional=True, question=CardType.ARTIFACT)
    assert chosen is None


def test_an_empty_matching_per_query_entry_still_fills_a_mandatory_choice():
    game = _game()
    rock = _artifact("Rock")
    set_board_state(game, 0, battlefield=[rock])
    player = game.players[0]
    player.set_baseline(Intent(pattern=GameRef(), per_query={CardType.ARTIFACT: []}))
    assert choose_object(game, player, [rock], "Choose", question=CardType.ARTIFACT) is rock


def test_an_empty_matching_per_query_entry_offers_no_action():
    game = _game()
    set_board_state(game, 0, hand=[Bolt()])
    script(game, 0, act_illegal(Bolt, per_query={(lambda query: True): []}))
    run_scripts(game)
    assert game.stack.is_empty()


def test_the_first_matching_key_wins_even_when_empty():
    game = _game()
    rock = _artifact("Rock")
    set_board_state(game, 0, battlefield=[rock])
    player = game.players[0]
    player.set_baseline(Intent(pattern=GameRef(), per_query={
        CardType.ARTIFACT: [], (lambda query: True): [Decision.obj(name="Rock")],
    }))
    assert choose_object(game, player, [rock], "Choose", optional=True,
                         question=CardType.ARTIFACT) is None


def test_a_canonical_string_enum_is_a_per_query_key_but_a_string_is_not():
    from engine.decisions import Role

    branch(Bolt, per_query={Role.CONTROLLER: [Bolt]})
    with pytest.raises(TypeError):
        branch(Bolt, per_query={"controller": [Bolt]})


def test_an_intent_applies_shared_per_query_after_each_branchs_own():
    intent = Intent(pattern=GameRef(), branches=[
        [Decision.yes()],
        branch(Decision.no(), per_query={CardType.CREATURE: [Decision.yes()]}),
    ], per_query={CardType.ARTIFACT: [Decision.no()]})
    first, second = intent.plans
    assert [k for k, _ in first.per_query] == [CardType.ARTIFACT]
    assert [k for k, _ in second.per_query] == [CardType.CREATURE, CardType.ARTIFACT]
    with pytest.raises(TypeError):
        Intent(pattern=GameRef(), preferences=(Decision.yes(),), branches=[[Decision.no()]])


# ---------------------------------------------------------------------------
# Review round 6: handlers answer with their current branch, explicit
# overrides own their answer, forced helpers stop where play was abandoned
# ---------------------------------------------------------------------------


class TwoStepCast(Sorcery):
    """While being cast, asks Bad or Good, then Wrong or Right; refuses Bad
    and Wrong."""

    def __init__(self, **kwargs) -> None:
        super().__init__(name="Two Step Cast", mana_cost=ManaCost(), **kwargs)

    def cast_offers(self, game, player, from_zone, mode):
        return [(self, lambda: self._cast(game, player))]

    def _cast(self, game, player):
        cards = {c.name: c for c in game.get_battlefield(player).get_all()}
        for pair in (("Bad", "Good"), ("Wrong", "Right")):
            chosen = choose_object(game, player, [cards[n] for n in pair], "Pick", source_card=self)
            if chosen.name in ("Bad", "Wrong"):
                raise InvalidPlayerChoiceError(f"{chosen.name} refused")
        return cast_spell(game, player, self)


def test_the_baseline_answers_with_its_current_branch_inside_an_entrys_action():
    game = _game()
    spell = TwoStepCast()
    set_board_state(game, 0, hand=[spell],
                    battlefield=[_artifact(n) for n in ("Bad", "Good", "Wrong", "Right")])
    game.players[0].set_baseline(Intent(pattern=GameRef(), branches=[
        _named("Bad"), _named("Good", "Right"),
    ]))
    script(game, 0, act(TwoStepCast))
    run_scripts(game)
    assert _on_stack(game, spell)


class OptionalPick(Sorcery):
    """While being cast, may choose an artifact (``optional``) or must."""

    def __init__(self, optional: bool, **kwargs) -> None:
        super().__init__(name="Optional Pick", mana_cost=ManaCost(), **kwargs)
        self.optional = optional
        self.chosen = "unset"

    def cast_offers(self, game, player, from_zone, mode):
        return [(self, lambda: self._cast(game, player))]

    def _cast(self, game, player):
        candidates = [c for c in game.get_battlefield(player).get_all()]
        chosen = choose_object(game, player, candidates, "Pick", source_card=self,
                               optional=self.optional, question=CardType.ARTIFACT)
        self.chosen = chosen.name if chosen is not None else None
        return cast_spell(game, player, self)


@pytest.mark.parametrize(("optional", "chosen"), [(True, None), (False, "Bad")])
def test_an_entrys_explicit_override_beats_a_baseline_preference(optional, chosen):
    game = _game()
    spell = OptionalPick(optional)
    set_board_state(game, 0, hand=[spell], battlefield=[_artifact("Bad"), _artifact("Rock")])
    game.players[0].set_baseline(Intent(pattern=GameRef(), preferences=_named("Rock")))
    script(game, 0, act(OptionalPick, per_query={CardType.ARTIFACT: []}))
    run_scripts(game)
    # Declined when optional; a mandatory choice fills its first option.
    assert spell.chosen == chosen


def test_without_an_override_the_baseline_preference_still_answers():
    game = _game()
    spell = OptionalPick(True)
    set_board_state(game, 0, hand=[spell], battlefield=[_artifact("Bad"), _artifact("Rock")])
    game.players[0].set_baseline(Intent(pattern=GameRef(), preferences=_named("Rock")))
    script(game, 0, act(OptionalPick))
    run_scripts(game)
    assert spell.chosen == "Rock"


def _abandoned_above_paused_cleanup():
    """Paused in cleanup with Bolt above a death trigger (which makes a
    second doomed creature), plus a resolving choice a negative intent's
    refusal abandons on top."""
    game, made = _paused_in_cleanup(lambda g: _doomed(g, g.players[0]))
    p0 = game.players[0]
    set_board_state(game, 0, battlefield=[_artifact("Bad"), _artifact("Good")])
    chooser = Chooser({"Bad"})
    chooser.controller = p0
    game.stack.push(StackObject(source=None, controller=p0, on_resolve=chooser.on_resolve))
    p0.start_intent("choose", _choose("Bad", negative=True))
    return game, made


def test_a_phase_helper_stops_where_a_cleanup_resolution_is_abandoned():
    game, made = _abandoned_above_paused_cleanup()
    turn = game.turn_number
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    assert (game.turn_number, game.step) == (turn, Step.CLEANUP) and len(game.stack) == 2
    assert made == []


def test_a_phase_helper_resumes_the_cleanup_it_stopped_in():
    game, made = _abandoned_above_paused_cleanup()
    turn = game.turn_number
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    game.players[0].end_intent("choose")
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    assert (game.turn_number, game.step) == (turn + 1, Step.UPKEEP)
    (second,) = made
    assert not game.get_battlefield(game.players[0]).contains(second)


# ---------------------------------------------------------------------------
# Review round 7: abandonment stops every driver; a retry starts from the
# restored boundary whatever the hooks changed
# ---------------------------------------------------------------------------


def test_priority_loop_stops_at_an_abandoned_resolution():
    game, visitor, copy = _copied_visitor("Bad", negative=True)
    script(game, 0, pass_priority())
    game.priority_passes = 2
    assert priority_loop(game) is False
    # The copy abandoned; the original below it and the pending entry wait.
    assert [obj.source for obj in game.stack._items] == [visitor]
    assert len(game.players[0].pending_entries) == 1 and _life(game) == 21


def test_native_cleanup_stops_at_an_abandoned_resolution():
    from engine.turn import _do_cleanup_step

    game, made = _abandoned_above_paused_cleanup()
    assert _do_cleanup_step(game) is False
    assert game.step == Step.CLEANUP and len(game.stack) == 2 and made == []


def _turn_with_abandoning_copy():
    game, visitor, copy = _copied_visitor("Bad", negative=True)
    game.players[0].set_baseline(Intent(pattern=GameRef(), preferences=_named("Good")))
    game.players[1].set_baseline(Intent(pattern=GameRef()))
    return game, visitor


def test_a_turn_stops_at_an_abandoned_resolution_and_resumes_without_repeating():
    from engine.turn import run_turn

    game, visitor = _turn_with_abandoning_copy()
    draws = len(game.get_library(game.players[0]).get_all())
    assert run_turn(game) is False
    assert (game.turn_number, game.phase, game.step) == (1, Phase.PRECOMBAT_MAIN, None)
    assert [obj.source for obj in game.stack._items] == [visitor]
    game.players[0].end_intent("choose")
    assert run_turn(game) is True
    assert game.turn_number == 2 and game.stack.is_empty()
    assert visitor.chosen == "Good"
    assert len(game.get_library(game.players[0]).get_all()) == draws


def test_run_turn_does_not_repeat_the_actions_of_a_step_run_scripts_entered():
    from engine.turn import run_turn

    game = _game()
    game.turn_number = 2  # the starting player skips only turn 1's draw
    game.phase, game.step = Phase.BEGINNING, Step.UPKEEP
    library = game.get_library(game.players[0])
    for _ in range(3):
        library.add(_artifact("Card"))
    script(game, 0, pass_priority(), pass_priority())
    script(game, 1, pass_priority())
    run_scripts(game)  # passes out of upkeep into the draw step, drawing
    assert game.step == Step.DRAW and len(library.get_all()) == 2
    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef()))
    run_turn(game)
    assert len(library.get_all()) == 2


class HookMutator(PlainPlayer):
    """Gains 7 life while hearing each rejection, then retries."""

    def on_attempt_rejected(self, context, answer, error):
        verdict = super().on_attempt_rejected(context, answer, error)
        gain_life(context.game, self, 7)
        return verdict


def test_a_priority_retry_starts_from_the_restored_boundary():
    p0 = HookMutator("Player1", picks=["Costly", "Bolt"], verdict="retry")
    game = _plain_game(p0)
    game.active_player_index = game.priority_player_index = 0
    set_board_state(game, 0, hand=[Costly(), Bolt()])
    take_priority(game, p0)
    assert p0.heard == [20] and p0.life == 20
    assert any(isinstance(obj.source, Bolt) for obj in game.stack._items)


def test_an_opponent_owned_priority_retry_starts_from_the_restored_boundary():
    game, spell = _opponent_cast_game(act(OpponentCast))
    opponent = game.players[1]
    original = opponent.on_attempt_rejected

    def mutate_then_hear(context, answer, error):
        gain_life(game, opponent, 7)
        return original(context, answer, error)

    opponent.on_attempt_rejected = mutate_then_hear
    take_priority(game, game.players[0])
    assert _on_stack(game, spell) and opponent.life == 20


# ---------------------------------------------------------------------------
# Review round 8: one step lifecycle, advanced by every driver
# ---------------------------------------------------------------------------


def _fresh_game():
    """A game at the start of turn 1: untap step, its actions pending."""
    game = create_game()
    for player in game.players:
        player.drawn_from_empty_library = False
    return game


def test_a_script_starts_after_the_untap_step():
    game = _fresh_game()
    rock = _artifact("Rock")
    set_board_state(game, 0, battlefield=[rock], hand=[Bolt()])
    rock.is_tapped = True
    script(game, 0, act(Bolt))
    run_scripts(game)
    assert (game.phase, game.step) == (Phase.BEGINNING, Step.UPKEEP)
    assert not rock.is_tapped and len(game.stack) == 1


def _completed_cleanup():
    game = _game()
    set_board_state(game, 0, hand=[Bolt()])
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    return game


def test_run_turn_does_not_reopen_a_completed_cleanup():
    from engine.turn import run_turn

    game = _completed_cleanup()
    script(game, 0, act(Bolt))
    assert run_turn(game) is True
    assert game.turn_number == 2 and game.stack.is_empty()
    assert len(game.players[0].pending_entries) == 1


def test_run_scripts_does_not_reopen_a_completed_cleanup():
    game = _completed_cleanup()
    script(game, 1, act(Bolt))
    set_board_state(game, 1, hand=[Bolt()])
    run_scripts(game)
    assert (game.turn_number, game.step) == (2, Step.UPKEEP) and len(game.stack) == 1


def _library(game, seat, cards):
    library = game.get_library(game.players[seat])
    for _ in range(cards):
        library.add(_artifact("Card"))
    return library


def test_scripted_play_skips_the_starting_players_first_draw():
    game = _fresh_game()
    library = _library(game, 0, 2)
    script(game, 0, pass_priority(), pass_priority())
    script(game, 1, pass_priority())
    run_scripts(game)
    assert game.step == Step.DRAW and len(library.get_all()) == 2


def test_scripted_play_draws_from_an_empty_library_on_a_later_turn():
    game = _fresh_game()
    game.turn_number = 2
    advance_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    script(game, 0, pass_priority(), pass_priority())
    script(game, 1, pass_priority())
    run_scripts(game)
    assert game.step == Step.DRAW and game.players[0].drawn_from_empty_library


def test_a_forced_exceptional_cleanup_is_not_reopened_by_the_next_driver():
    from engine.turn import run_turn

    game, made = _paused_in_cleanup(lambda g: _doomed(g, g.players[0]))
    resolve_stack(game)  # finishes the cleanup with every player passing
    set_board_state(game, 0, hand=[Bolt()])
    script(game, 0, act(Bolt))
    assert run_turn(game) is True
    assert game.turn_number == 2 and len(game.players[0].pending_entries) == 1


def test_run_turn_resumes_an_abandoned_cleanup_window():
    from engine.turn import run_turn

    game, made = _abandoned_above_paused_cleanup()
    assert run_turn(game) is False and game.step == Step.CLEANUP
    game.players[0].end_intent("choose")
    game.players[0].set_baseline(Intent(pattern=GameRef()))
    game.players[1].set_baseline(Intent(pattern=GameRef()))
    assert run_turn(game) is True and game.turn_number == 2
    (second,) = made
    assert not game.get_battlefield(game.players[0]).contains(second)


# ---- every driver hands off to every other ------------------------------------


def _counting(game, event_type):
    """Count the times *event_type* fires, without triggering anything."""
    from engine.triggers import TriggerRegistration

    seen = []
    holder = _artifact("Counter")
    set_board_state(game, 0, battlefield=[*game.get_battlefield(game.players[0]).get_all(), holder])
    game.trigger_manager.register(TriggerRegistration(
        event_type=event_type, condition=lambda g, e: seen.append(1) and False,
        effect=lambda g: None, source=holder, controller=game.players[0],
    ))
    return seen


def _start_end_step(game):
    advance_game_to_phase(game, Phase.ENDING, Step.END)


def _start_mid_end_round(game):
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    script(game, 0, pass_priority())
    run_scripts(game)


def _start_completed_cleanup(game):
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)


_STARTS = {
    "end step": (_start_end_step, ([pass_priority], [pass_priority, pass_priority])),
    "mid end round": (_start_mid_end_round, ([], [pass_priority, pass_priority])),
    "completed cleanup": (_start_completed_cleanup, ([], [pass_priority])),
}


def _finish_by_run_turn(game, entries):
    from engine.turn import run_turn

    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef()))
    assert run_turn(game) is True
    return False


def _finish_by_scripts(game, entries):
    p0, p1 = entries
    script(game, 0, *(make() for make in p0))
    script(game, 1, *(make() for make in p1))
    run_scripts(game)
    return True


def _finish_by_phase_helper(game, entries):
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    return True


@pytest.mark.parametrize("finish", [_finish_by_run_turn, _finish_by_scripts, _finish_by_phase_helper],
                         ids=["run_turn", "run_scripts", "phase helper"])
@pytest.mark.parametrize("start", list(_STARTS))
def test_each_driver_finishes_the_turn_another_began_exactly_once(start, finish):
    from engine.events import BeginningOfUpkeepTriggeredEvent, EndStepTriggeredEvent

    game = _game()
    for player in game.players:
        player.drawn_from_empty_library = False
    bear = Creature(name="Bear", mana_cost=ManaCost(), base_power=2, base_toughness=3)
    set_board_state(game, 0, battlefield=[bear])
    bear.damage_marked = 1
    end_steps = _counting(game, EndStepTriggeredEvent)
    upkeeps = _counting(game, BeginningOfUpkeepTriggeredEvent)
    begin, entries = _STARTS[start]
    begin(game)
    reaches_upkeep = finish(game, entries)
    assert game.turn_number == 2 and bear.damage_marked == 0
    assert len(end_steps) == 1
    assert len(upkeeps) == (1 if reaches_upkeep else 0)
    if reaches_upkeep:
        assert (game.phase, game.step) == (Phase.BEGINNING, Step.UPKEEP)
    assert all(not p.pending_entries for p in game.players)


def test_setup_only_phase_advance_performs_no_step_actions_for_later_drivers():
    game = _fresh_game()
    game.turn_number = 2
    library = _library(game, 0, 2)
    advance_to_phase(game, Phase.BEGINNING, Step.DRAW)
    script(game, 0, pass_priority())
    run_scripts(game)
    assert game.step == Step.DRAW and len(library.get_all()) == 2
