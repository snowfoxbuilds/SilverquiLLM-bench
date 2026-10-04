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
from engine.decisions import (
    Decision,
    GameRef,
    InvalidPlayerChoiceError,
    PostconditionError,
)
from engine.intent_player import Intent, ScriptEntryError
from engine.priority import take_priority
from engine.queries import PlayerQuery, ask
from engine.types import ManaCost, Phase, Step, Zone
from test_utils import (
    act,
    act_illegal,
    activate_card_ability,
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

    def __init__(self, illegal=(), **kwargs) -> None:
        super().__init__(name="Chooser", mana_cost=ManaCost(), **kwargs)
        self.illegal = set(illegal)
        self.chosen = None

    def on_resolve(self, game) -> None:
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
    # Rolled back to before Chooser resolved, and play stopped there.
    assert chooser.chosen is None and _on_stack(game, chooser)


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
