"""Action scripts and choice retries in the Known-Best Workspace
(DECISION-MODEL.md › Priority actions › Legality and Action scripts).

Run inside ``known_best/workspace`` by ``tests/test_known_best_action_scripts.py``:
the module imports the workspace's ``engine`` and ``test_utils``, which the repo
suite cannot import in-process alongside other workspaces.
"""

from __future__ import annotations

import pytest
from engine.card import Artifact, Instant, Sorcery
from engine.card_queries import choose_object
from engine.casting import CastingError, cast_spell
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
from engine.stack import priority_loop
from engine.queries import PlayerQuery, ask
from engine.types import ManaCost, Phase, Step, Zone
import test_utils
from test_utils import (
    act,
    act_illegal,
    activate_card_ability,
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


def test_act_fails_once_rejection_exhausts_its_preferences_and_is_rolled_back():
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
def test_rejection_drops_the_highest_ranked_preference_used_and_retries(presentation):
    """Gleam is illegal: whether the engine offered Gleam at once (one query)
    or asked Blade then Gleam (two queries), the retry casts Blade."""
    game, blade = _with_blade(presentation, gleam_legal=False)
    script(game, 0, act(GleamFace, BladeCard), pass_priority())
    take_priority(game, game.players[0])
    assert blade.cast_face == "blade" and _on_stack(game, blade)
    # The rejected attempt and its retry were one entry: the next is still pending.
    assert [e.kind.value for e in game.players[0].pending_entries] == ["pass"]
    assert len(game.players[0].transcript.priority_queries()) == 2


def test_rejected_attempt_is_rolled_back_before_the_retry():
    game = _game()
    costly, bolt = Costly(), Bolt()
    set_board_state(game, 0, hand=[costly, bolt])
    script(game, 0, act(Costly, Bolt))
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


def _chooser_game(illegal=()):
    game = _game()
    chooser = Chooser(illegal)
    set_board_state(game, 0, hand=[chooser], battlefield=[_artifact("Bad"), _artifact("Good")])
    return game, chooser


def _choose(*names, negative=False) -> Intent:
    return Intent(
        pattern=GameRef(card=frozenset({("name", "Chooser")})),
        preferences=tuple(Decision.obj(name=name) for name in names),
        negative=negative,
    )


def test_choice_intents_answer_resolution_time_choices():
    game, chooser = _chooser_game()
    game.players[0].start_intent("choose", _choose("Good"))
    cast_card(game, game.players[0], chooser)
    assert chooser.chosen == "Good"


def test_rejected_resolution_choice_retries_from_before_the_object_resolved():
    game, chooser = _chooser_game(illegal={"Bad"})
    game.players[0].start_intent("choose", _choose("Bad", "Good"))
    cast_card(game, game.players[0], chooser)
    assert chooser.chosen == "Good"
    assert game.get_graveyard(game.players[0]).contains(chooser)
    queries = [r for r in game.players[0].transcript.all() if r.query.prompt == "Choose one"]
    assert len(queries) == 2


def test_resolution_choice_fails_once_its_preferences_are_exhausted():
    game, chooser = _chooser_game(illegal={"Bad", "Good"})
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
    game.players[0].start_intent("choose", _choose("Bad", "Good"))
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
    game.players[0].start_intent("choose", _choose("Bad", "Good"))
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


def _pick(*names, negative=False) -> Intent:
    return Intent(
        pattern=GameRef(card=frozenset({("name", "Picker")})),
        preferences=tuple(Decision.obj(name=name) for name in names),
        negative=negative,
    )


def test_abandoned_attempts_let_the_resolution_go_on():
    game, picker = _picker_game(illegal={"Bad"})
    game.players[0].start_intent("pick", _pick("Bad", negative=True))
    cast_card(game, game.players[0], picker)
    # Both picks were rejected and abandoned; the resolution still finished.
    assert picker.picks == [None, None] and _life(game) == 20
    assert game.get_graveyard(game.players[0]).contains(picker)


def test_each_attempt_retries_its_own_rejected_pick():
    game, picker = _picker_game(illegal={"Bad"})
    game.players[0].start_intent("pick", _pick("Bad", "Good"))
    cast_card(game, game.players[0], picker)
    # Each pick is a fresh attempt: Bad is rejected and Good taken, twice.
    assert picker.picks == ["Good", "Good"] and _life(game) == 22


def test_an_attempt_that_exhausts_its_preferences_fails():
    game, picker = _picker_game(illegal={"Bad", "Good"})
    game.players[0].start_intent("pick", _pick("Bad", "Good"))
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
    game.players[0].start_intent("pick", _pick("Bad", "Good"))
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


def _cast_choice(*names, negative=False) -> Intent:
    return Intent(
        pattern=GameRef(card=frozenset({("name", "Choosing Cast")})),
        preferences=tuple(Decision.obj(name=name) for name in names),
        negative=negative,
    )


def test_a_choice_intent_during_a_cast_retries_its_own_fallback_and_keeps_the_entry():
    game, spell = _choosing_cast_game()
    game.players[0].start_intent("choose", _cast_choice("Bad", "Good"))
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


def _sourced(source: str, *names, negative=False) -> Intent:
    return Intent(
        pattern=GameRef(card=frozenset({("name", source)})),
        preferences=tuple(Decision.obj(name=name) for name in names),
        negative=negative,
    )


def _two_chooser_game(**kwargs):
    game = _game()
    card = TwoChooser(**kwargs)
    set_board_state(game, 0, hand=[card], battlefield=[_artifact("Bad"), _artifact("Good")])
    return game, card


def test_a_resolution_rejection_retries_the_intent_that_owns_it_not_an_earlier_one():
    game, card = _two_chooser_game(illegal={"Bad"})
    p0 = game.players[0]
    p0.start_intent("first", _sourced("First Source", "Good"))
    p0.start_intent("second", _sourced("Second Source", "Bad", "Good"))
    cast_card(game, p0, card)
    assert card.chosen == ("Good", "Good")


def test_only_the_player_who_owns_a_rejection_hears_it():
    game, card = _two_chooser_game(first=0, second=1, illegal={"Bad"})
    p0, p1 = game.players
    p0.start_intent("first", _sourced("First Source", "Bad", "Good"))
    p1.start_intent("second", _sourced("Second Source", "Bad", "Good"))
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
    p0.start_intent("second", _sourced("Second Source", "Bad", "Good"))
    with pytest.raises(PostconditionError):
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
