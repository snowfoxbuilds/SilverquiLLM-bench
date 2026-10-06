"""The Test Interface and its host-side helpers on the Known-Best Engine
(TEST-INTERFACE.md).

Run inside ``known_best/workspace`` by ``tests/test_known_best_test_interface.py``:
the module imports the workspace's ``engine``, ``cards`` and ``test_interface``,
which the repo suite cannot import in-process alongside other workspaces.
"""

from __future__ import annotations

import dataclasses
import time

import pytest
import test_interface as ti
from cards.fdn.fdn_134.card_impl import (
    AjaniCallerOfThePride,
    AjaniCallerOfThePrideAbility1,
    AjaniCallerOfThePrideAbility3,
)
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain, MountainAbility1
from engine.card import Creature, Sorcery
from engine.card_queries import choose_object, query_yes_no
from engine.decisions import Decision, InvalidPlayerChoiceError
from engine.game import gain_life
from engine.types import CardType, ManaType, Phase, Step, Zone
from test_interface import (
    PlayDiverged,
    Side,
    act,
    act_illegal,
    branch,
    card,
    chosen_at_random,
    coin,
    create_game,
    pass_priority,
    player,
    run,
    shuffled,
    token,
    view,
)

from silverquillm.table import (
    ScriptError,
    Table,
    appears,
    ceases,
    life,
    moves,
    off_stack,
    on_stack,
    taps,
    wins,
)

# ---------------------------------------------------------------------------
# Check-only cards
# ---------------------------------------------------------------------------


class Bear(Creature):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Bear")
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)


class CoinToss(Sorcery):
    """Flip a coin; heads, you gain 5 life."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Coin Toss")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if game.flip_coin():
            gain_life(game, self.controller, 5)


class RandomDiscard(Sorcery):
    """Each opponent discards a card at random."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Random Discard")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.game import discard

        opponent = next(p for p in game.players if p is not self.controller)
        hand = game.get_hand(opponent).get_all()
        for chosen in game.choose_at_random(hand, 1):
            discard(game, opponent, chosen)


class Reshuffle(Sorcery):
    """Shuffle your library."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Reshuffle")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        game.get_library(self.controller).shuffle(game)


class PickTwo(Sorcery):
    """Choose an artifact you control, then a creature you control; each
    gains you 1 life. The two questions offer the same cards."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Pick Two")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        mine = game.get_battlefield(self.controller).get_all()
        for wanted in (CardType.ARTIFACT, CardType.CREATURE):
            chosen = choose_object(
                game, self.controller, mine, f"choose an {wanted.value}",
                source_card=self, optional=True, question=wanted,
            )
            if chosen is not None:
                gain_life(game, self.controller, 1)


class PickBear(Sorcery):
    """Choose a creature you control: a Bear is refused; you gain 3 life."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Pick Bear")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        mine = game.get_battlefield(self.controller).get_all()
        chosen = choose_object(game, self.controller, mine, "choose a permanent", source_card=self)
        if isinstance(chosen, Bear):
            raise InvalidPlayerChoiceError("a Bear cannot be chosen")
        gain_life(game, self.controller, 3)


class Stall(Sorcery):
    """Takes far too long to resolve."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Stall")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        time.sleep(ti.QUESTION_TIMEOUT + 0.5)


class PickTwice(Sorcery):
    """Choose a permanent you control, then choose one again; you gain 1 life
    for each choice."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Pick Twice")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        for _ in range(2):
            mine = game.get_battlefield(self.controller).get_all()
            choose_object(game, self.controller, mine, "choose a permanent", source_card=self)
            gain_life(game, self.controller, 1)


class PickOne(Sorcery):
    """Choose a permanent you control; you gain 1 life."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Pick One")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        mine = game.get_battlefield(self.controller).get_all()
        choose_object(game, self.controller, mine, "choose a permanent", source_card=self)
        gain_life(game, self.controller, 1)


class PickBoth(Sorcery):
    """Choose both permanents you control, in an order; you gain 1 life if the
    first chosen is a Plains."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Pick Both")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.queries import PlayerQuery, ask
        from engine.refs_registry import object_options

        seat = game.refs.seat_of(self.controller)
        mine = game.get_battlefield(self.controller).get_all()
        options, by_decision = object_options(game.refs, ((c, "battlefield", seat) for c in mine))
        query = PlayerQuery(
            source=(game.refs.object_decision(self, zone="stack", controller_seat=seat),),
            prompt="order your permanents",
            options=options,
            min=len(options),
            max=len(options),
        )
        first = by_decision[ask(self.controller, query).selected[0]]
        if isinstance(first, Plains):
            gain_life(game, self.controller, 1)


class RandomPlayerLoses(Sorcery):
    """A player chosen at random loses 3 life."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Random Player Loses")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        for chosen in game.choose_at_random(list(game.players), 1):
            chosen.life -= 3


def _main(p0=None, p1=None, active=0):
    return create_game(p0 or Side(), p1 or Side(), start=(Phase.PRECOMBAT_MAIN, active))


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_construction_opens_the_starting_window():
    game = _main(Side(battlefield=[Bear]), active=1)
    v = view(game)
    assert (v.step, v.active, v.asked) == (Phase.PRECOMBAT_MAIN, 1, 1)
    assert game.turn_number == 2 and game.window is not None


def test_seat_0_starts_on_turn_1_and_skips_its_first_draw():
    library = [card(Plains), card(Plains)]
    game = create_game(Side(library=library), start=(Step.UPKEEP, 0))
    assert game.turn_number == 1
    t = Table(game)
    t.pass_(0)
    t.pass_(1)
    final = t.run()
    assert final.step is Step.DRAW and final.where(library[0]) is Zone.LIBRARY


def test_constructed_permanents_are_ready_tapped_or_loyal():
    bear, tapped = card(Bear), card(Mountain, tapped=True)
    game = _main(Side(battlefield=[bear, tapped, AjaniCallerOfThePride]))
    assert not bear.card.summoning_sick and tapped.card.is_tapped
    ajani = next(c for c in game.get_battlefield(game.players[0]).get_all() if isinstance(c, AjaniCallerOfThePride))
    assert ajani.loyalty == 4


def test_construction_places_cards_with_life_and_mana_and_never_shuffles():
    library = [card(Plains), card(Mountain), card(Plains)]
    game = _main(Side(library=library, life=7, mana={ManaType.RED: 2}))
    v = view(game)
    assert [seen.handle for seen in v.players[0].library] == library
    assert v.players[0].life == 7 and game.players[0].mana_pool.total() == 2


@pytest.mark.parametrize("step", [Step.UNTAP, Step.CLEANUP])
def test_construction_refuses_a_step_without_a_priority_window(step):
    with pytest.raises(ValueError):
        create_game(start=(step, 0))


def test_only_a_permanent_starts_tapped():
    with pytest.raises(ValueError):
        _main(Side(hand=[card(Bear, tapped=True)]))


# ---------------------------------------------------------------------------
# The Player View
# ---------------------------------------------------------------------------


def test_the_view_shows_only_what_a_player_sees():
    bolt = card(BurstLightning)
    game = _main(Side(hand=[bolt], battlefield=[Bear]), Side(graveyard=[Plains], exile=[Mountain]))
    v = view(game)
    assert v.where(bolt) is Zone.HAND
    seen = v.players[0].battlefield[0]
    assert (seen.card, seen.owner, seen.tapped) == (Bear, 0, False)
    assert v.players[1].graveyard[0].card is Plains and v.players[1].exile[0].card is Mountain
    assert not hasattr(seen, "power") and not v.stack and not v.game_over
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.active = 1


def test_unordered_zones_compare_whatever_the_order():
    a, b = card(Bear), card(Plains)
    first = ti.PlayerView(life=20, hand=(ti.Seen(Bear, 0, False, a), ti.Seen(Plains, 0, False, b)))
    second = ti.PlayerView(life=20, hand=(ti.Seen(Plains, 0, False, b), ti.Seen(Bear, 0, False, a)))
    assert first == second


def test_a_handle_follows_its_card_and_a_spell_on_the_stack():
    bolt, mountain = card(BurstLightning), card(Mountain)
    game = _main(Side(hand=[bolt], battlefield=[mountain]))
    t = Table(game)
    t.act(0, MountainAbility1, then=[taps(mountain)])
    t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
    final = t.run()
    assert final.where(bolt) is Zone.STACK and final.stack[0].handle is bolt


# ---------------------------------------------------------------------------
# Playing
# ---------------------------------------------------------------------------


def _bolt_game():
    bolt, mountain = card(BurstLightning), card(Mountain)
    return _main(Side(hand=[bolt], battlefield=[mountain])), bolt, mountain


def test_a_spell_resolves_and_play_stops_when_the_scripts_run_out():
    game, bolt, mountain = _bolt_game()
    t = Table(game)
    t.act(0, MountainAbility1, then=[taps(mountain)])
    t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])
    final = t.run()
    assert final.players[1].life == 18 and final.where(bolt) is Zone.GRAVEYARD and final.asked == 0


def test_an_unexpected_change_diverges_with_a_narrated_report():
    game, bolt, mountain = _bolt_game()
    t = Table(game)
    t.act(0, MountainAbility1, then=[taps(mountain)])
    t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, 17)])
    with pytest.raises(PlayDiverged) as failure:
        t.run()
    report = str(failure.value)
    assert "Player 1 passes" in report and "life 17" in report and "life 18" in report


def test_an_act_whose_action_is_not_offered_diverges():
    game = _main(Side(hand=[BurstLightning]))
    with pytest.raises(PlayDiverged, match="not offered"):
        run(game, [act(Mountain)], [])


def test_an_act_rejected_with_no_branch_left_diverges():
    game = _main(Side(hand=[BurstLightning]))
    with pytest.raises(PlayDiverged, match="no branch left"):
        run(game, [act(BurstLightning, choices=[player(1)])], [])


def test_an_illegal_loyalty_activation_leaves_the_planeswalker_free_to_activate():
    game = _main(Side(battlefield=[AjaniCallerOfThePride]))
    t = Table(game)
    t.act_illegal(0, AjaniCallerOfThePrideAbility3, note="-8 on 4 loyalty")
    t.act(0, AjaniCallerOfThePrideAbility1, then=[on_stack(AjaniCallerOfThePrideAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(AjaniCallerOfThePrideAbility1)])
    t.run()


def test_an_act_illegal_that_takes_effect_diverges():
    game, _, _ = _bolt_game()
    with pytest.raises(PlayDiverged, match="took effect"):
        run(game, [act_illegal(MountainAbility1)], [])


def test_a_question_nothing_answers_diverges():
    game = _main(Side(hand=[PickBear], battlefield=[Plains, Mountain]))
    with pytest.raises(PlayDiverged, match="nothing in player 0's script answers"):
        run(game, [act(PickBear), pass_priority()], [pass_priority()], check_views=False)


def test_a_mandatory_question_with_exactly_its_minimum_is_filled():
    game = _main(Side(hand=[PickBear], battlefield=[Plains]))
    final = run(game, [act(PickBear), pass_priority()], [pass_priority()], check_views=False)
    assert final.players[0].life == 23


def test_a_rejected_choice_is_answered_from_the_next_branch():
    game = _main(Side(hand=[PickBear], battlefield=[Bear, Plains]))
    resolving = pass_priority(branches=[[Bear], [Plains]], note="a Bear is refused")
    final = run(game, [act(PickBear), resolving], [pass_priority()], check_views=False)
    assert final.players[0].life == 23


def test_a_script_running_out_while_another_has_entries_diverges():
    game = _main()
    with pytest.raises(PlayDiverged, match="ran out while player 1"):
        run(game, [], [pass_priority()])


def test_a_game_ending_with_entries_left_diverges():
    bolt, mountain = card(BurstLightning), card(Mountain)
    game = _main(Side(hand=[bolt], battlefield=[mountain]), Side(life=2))
    t = Table(game)
    t.act(0, MountainAbility1, then=[taps(mountain)])
    t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, 0), wins(0)])
    final = t.run()
    assert final.game_over and final.winner == 0
    game2 = _main(Side(hand=[card(BurstLightning)], battlefield=[card(Mountain)]), Side(life=2))
    with pytest.raises(PlayDiverged, match="ended with entries left"):
        run(
            game2,
            [act(MountainAbility1), act(BurstLightning, choices=[player(1)]), pass_priority(), pass_priority()],
            [pass_priority()],
            check_views=False,
        )


def test_a_slow_engine_times_out_between_questions(monkeypatch):
    monkeypatch.setattr(ti, "QUESTION_TIMEOUT", 0.5)
    game = _main(Side(hand=[Stall]))
    started = time.monotonic()
    with pytest.raises(PlayDiverged, match="more than"):
        run(game, [act(Stall), pass_priority()], [pass_priority()], check_views=False)
    assert time.monotonic() - started < ti.QUESTION_TIMEOUT + 3


def test_an_entry_without_a_view_expects_nothing_visible_to_change():
    game = _main(Side(hand=[PickBear], battlefield=[Plains]))
    with pytest.raises(PlayDiverged, match="the view differs from the expected view"):
        run(game, [act(PickBear), pass_priority()], [pass_priority()])


def test_drivers_stop_once_the_game_is_over():
    import signal

    import test_utils
    from engine.stack import priority_loop
    from engine.turn import _do_cleanup_step, run_turn

    game = _main(Side(hand=[BurstLightning], mana={ManaType.RED: 1}), Side(life=2))
    final = run(game, [act(BurstLightning, choices=[player(1)]), pass_priority()], [pass_priority()], check_views=False)
    assert final.game_over

    def hung(signum, frame):
        raise AssertionError("a driver kept stepping a game that is over")

    previous = signal.signal(signal.SIGALRM, hung)
    signal.alarm(2)
    try:
        priority_loop(game)
        _do_cleanup_step(game)
        run_turn(game)
        test_utils.resolve_stack(game)
        test_utils.advance_game_to_phase(game, Phase.ENDING, Step.END)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


def _pick_two(per_query=None, branches=None):
    game = _main(Side(hand=[PickTwo], battlefield=[ArtifactBear]))
    entry = pass_priority(branches=branches) if branches else pass_priority(per_query=per_query)
    return game, entry


class ArtifactBear(Creature):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Artifact Bear")
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs["card_types"] = {CardType.ARTIFACT, CardType.CREATURE}
        super().__init__(**kwargs)


def test_per_query_keys_tell_questions_apart():
    game, entry = _pick_two(per_query={CardType.ARTIFACT: [ArtifactBear], CardType.CREATURE: []})
    final = run(game, [act(PickTwo), entry], [pass_priority()], check_views=False)
    assert final.players[0].life == 21


def test_a_raw_string_per_query_key_is_refused():
    with pytest.raises(TypeError):
        act(PickTwo, per_query={"artifact": [ArtifactBear]})


def test_a_branch_repeats_by_default_and_distinct_chooses_once():
    game, repeat = _pick_two(branches=[branch(choices=[ArtifactBear])])
    assert run(game, [act(PickTwo), repeat], [pass_priority()], check_views=False).players[0].life == 22
    game, once = _pick_two(branches=[branch(choices=[ArtifactBear], distinct=True)])
    assert run(game, [act(PickTwo), once], [pass_priority()], check_views=False).players[0].life == 21


def test_a_handle_names_one_of_two_cards_of_a_class():
    tapped, untapped = card(Bear, tapped=True), card(Bear)
    game = _main(Side(hand=[BurstLightning], mana={ManaType.RED: 1}), Side(battlefield=[tapped, untapped]))
    final = run(game, [act(BurstLightning, choices=[untapped]), pass_priority()], [pass_priority()], check_views=False)
    assert final.where(untapped) is Zone.GRAVEYARD and final.where(tapped) is Zone.BATTLEFIELD


def test_a_handle_names_one_of_two_identical_cards():
    first, second = card(Bear), card(Bear)
    game = _main(Side(hand=[BurstLightning], mana={ManaType.RED: 1}), Side(battlefield=[first, second]))
    final = run(game, [act(BurstLightning, choices=[second]), pass_priority()], [pass_priority()], check_views=False)
    assert final.where(second) is Zone.GRAVEYARD and final.where(first) is Zone.BATTLEFIELD


@pytest.mark.parametrize("chosen", [0, 1])
def test_a_handle_names_the_ability_of_its_own_permanent(chosen):
    mountains = [card(Mountain), card(Mountain)]
    game = _main(Side(battlefield=mountains))
    t = Table(game)
    t.act(0, mountains[chosen], then=[taps(mountains[chosen])])
    final = t.run()
    assert [final.players[0].battlefield[i].tapped for i in range(2)].count(True) == 1


def test_a_distinct_branch_never_fills_a_question_with_an_object_it_chose():
    game = _main(Side(hand=[PickTwice], battlefield=[Bear]))
    final = run(game, [act(PickTwice), pass_priority(choices=[Bear])], [pass_priority()], check_views=False)
    assert final.players[0].life == 22
    game = _main(Side(hand=[PickTwice], battlefield=[Bear]))
    with pytest.raises(PlayDiverged, match="nothing in player 0's script answers"):
        run(game, [act(PickTwice), pass_priority(choices=[Bear], distinct=True)], [pass_priority()], check_views=False)


def test_a_question_whose_answer_is_an_order_is_never_filled():
    game = _main(Side(hand=[PickBoth], battlefield=[Mountain, Plains]))
    with pytest.raises(PlayDiverged, match="nothing in player 0's script answers"):
        run(game, [act(PickBoth), pass_priority()], [pass_priority()], check_views=False)
    game = _main(Side(hand=[PickBoth], battlefield=[Mountain, Plains]))
    final = run(game, [act(PickBoth), pass_priority(choices=[Plains, Mountain])], [pass_priority()], check_views=False)
    assert final.players[0].life == 21


def test_an_empty_per_query_answer_never_fills_an_order():
    game = _main(Side(hand=[PickBoth], battlefield=[Mountain, Plains]))
    script = [act(PickBoth), pass_priority(per_query={(lambda query: True): []})]
    with pytest.raises(PlayDiverged, match="nothing in player 0's script answers"):
        run(game, script, [pass_priority()], check_views=False)


@pytest.mark.parametrize("order", [(Mountain, Plains), (Plains, Mountain)])
def test_an_empty_per_query_answer_never_fills_a_choice_of_one_of_two(order):
    game = _main(Side(hand=[PickOne], battlefield=list(order)))
    script = [act(PickOne), pass_priority(per_query={(lambda query: True): []})]
    with pytest.raises(PlayDiverged, match="nothing in player 0's script answers"):
        run(game, script, [pass_priority()], check_views=False)


def test_an_empty_per_query_answer_fills_a_forced_singleton():
    game = _main(Side(hand=[PickOne], battlefield=[Mountain]))
    final = run(game, [act(PickOne), pass_priority(per_query={(lambda query: True): []})], [pass_priority()], check_views=False)
    assert final.players[0].life == 21


# ---------------------------------------------------------------------------
# Chance
# ---------------------------------------------------------------------------


def test_a_coin_flip_is_answered_by_the_chance_script():
    for heads, total in ((True, 25), (False, 20)):
        game = _main(Side(hand=[CoinToss]))
        final = run(game, [act(CoinToss), pass_priority()], [pass_priority()], chance=[coin(heads)], check_views=False)
        assert final.players[0].life == total


def test_a_choice_at_random_is_answered_by_the_chance_script():
    keep, lose = card(Bear), card(Plains)
    game = _main(Side(hand=[RandomDiscard]), Side(hand=[keep, lose]))
    final = run(game, [act(RandomDiscard), pass_priority()], [pass_priority()], chance=[chosen_at_random(lose)], check_views=False)
    assert final.where(lose) is Zone.GRAVEYARD and final.where(keep) is Zone.HAND


@pytest.mark.parametrize("seat", [0, 1])
def test_a_choice_at_random_of_a_player_takes_the_named_seat(seat):
    game = _main(Side(hand=[RandomPlayerLoses]))
    final = run(
        game, [act(RandomPlayerLoses), pass_priority()], [pass_priority()],
        chance=[chosen_at_random(player(seat))], check_views=False,
    )
    assert final.players[seat].life == 17 and final.players[1 - seat].life == 20


def test_a_shuffle_is_answered_top_first():
    a, b, c = card(Plains), card(Mountain), card(Bear)
    game = _main(Side(hand=[Reshuffle], library=[a, b, c]))
    final = run(game, [act(Reshuffle), pass_priority()], [pass_priority()], chance=[shuffled(c, a, b)], check_views=False)
    assert [seen.handle for seen in final.players[0].library] == [c, a, b]


def test_a_random_event_with_nothing_to_answer_it_diverges():
    game = _main(Side(hand=[CoinToss]))
    with pytest.raises(PlayDiverged, match="nothing in the chance script"):
        run(game, [act(CoinToss), pass_priority()], [pass_priority()], check_views=False)


# ---------------------------------------------------------------------------
# The host-side table
# ---------------------------------------------------------------------------


def test_the_table_refuses_an_entry_out_of_turn():
    t = Table(_main())
    with pytest.raises(ScriptError):
        t.pass_(1)


def test_passing_through_a_turn_untaps_and_draws():
    land, drawn = card(Mountain, tapped=True), card(Plains)
    game = _main(Side(battlefield=[land]), Side(library=[drawn]), active=0)
    t = Table(game)
    t.pass_to(Step.UPKEEP, 0)
    final = t.run()
    assert final.where(drawn) is Zone.HAND and final.players[0].battlefield[0].tapped is False
    assert (final.step, final.active) == (Step.UPKEEP, 0)
    assert "player 1 draws" in " ".join(e.narration for script in t.scripts for e in script)


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


def _make_tokens(game, controller, *sizes):
    from engine.game import create_token

    for size in sizes:
        create_token(game, controller, Creature(name=f"{size}/{size} Token", base_power=size, base_toughness=size))


class MakeOne(Sorcery):
    """Create a 1/1 creature token."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Make One")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        _make_tokens(game, self.controller, 1)


class MakeThree(Sorcery):
    """Create three 1/1 creature tokens."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Make Three")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        _make_tokens(game, self.controller, 1, 1, 1)


class MakeOneAndTwo(Sorcery):
    """Create a 1/1 creature token and a 2/2 creature token."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Make One and Two")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        _make_tokens(game, self.controller, 1, 2)


class Muster(Sorcery):
    """Choose a creature you control; you gain life equal to its power."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Muster")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        mine = [c for c in game.get_battlefield(self.controller).get_all() if CardType.CREATURE in c.card_types]
        chosen = choose_object(game, self.controller, mine, "choose a creature", source_card=self)
        gain_life(game, self.controller, chosen.power)


def _cast_and_resolve(t, spell, *, choices=(), then=()):
    # A choice while the spell resolves falls in its caster's pass, the
    # entry they are answering from then.
    t.act(0, spell, then=[moves(spell, Zone.STACK)])
    t.pass_(0, choices=list(choices))
    t.pass_(1, then=[moves(spell, Zone.GRAVEYARD), *then])


def test_a_token_is_followed_by_its_number_and_shows_no_class():
    make = card(MakeOne)
    t = Table(_main(Side(hand=[make])))
    _cast_and_resolve(t, make, then=[appears(0)])
    final = t.run()
    (seen,) = final.players[0].battlefield
    assert seen.card is None and seen.handle == token(1) and final.where(token(1)) is Zone.BATTLEFIELD


def test_tokens_made_alike_are_interchangeable():
    make, muster = card(MakeThree), card(Muster)
    t = Table(_main(Side(hand=[make, muster])))
    _cast_and_resolve(t, make, then=[appears(0), appears(0), appears(0)])
    _cast_and_resolve(t, muster, choices=[token(3)], then=[life(0, 21)])
    final = t.run()
    assert {seen.handle for seen in final.players[0].battlefield} == {token(1), token(2), token(3)}


@pytest.mark.parametrize(("chosen", "gained"), [(1, 1), (2, 2)])
def test_tokens_one_effect_makes_are_numbered_in_the_order_it_makes_them(chosen, gained):
    make, muster = card(MakeOneAndTwo), card(Muster)
    t = Table(_main(Side(hand=[make, muster])))
    _cast_and_resolve(t, make, then=[appears(0), appears(0)])
    _cast_and_resolve(t, muster, choices=[token(chosen)], then=[life(0, 20 + gained)])
    assert t.run().players[0].life == 20 + gained


class MakeAndConfirm(Sorcery):
    """Create a 1/1 and a 2/2 creature token, choose a token you control and
    confirm it; declining is refused. You gain life equal to its power."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Make and Confirm")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        _make_tokens(game, self.controller, 1, 2)
        tokens = [c for c in game.get_battlefield(self.controller).get_all() if getattr(c, "is_token", False)]
        chosen = choose_object(game, self.controller, tokens, "choose a token", source_card=self)
        if not query_yes_no(game, self.controller, "confirm the token?", source_card=self):
            raise InvalidPlayerChoiceError("the token must be confirmed")
        gain_life(game, self.controller, chosen.power)


class MakeSacrificeMake(Sorcery):
    """Create a 1/1 creature token, sacrifice it, then create a 2/2 creature token."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Make, Sacrifice, Make")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.game import sacrifice

        _make_tokens(game, self.controller, 1)
        (first,) = [c for c in game.get_battlefield(self.controller).get_all() if getattr(c, "is_token", False)]
        sacrifice(game, self.controller, first)
        _make_tokens(game, self.controller, 2)


class SacrificeTokens(Sorcery):
    """Sacrifice every token you control."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Sacrifice Tokens")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.game import sacrifice

        for obj in list(game.get_battlefield(self.controller).get_all()):
            if getattr(obj, "is_token", False):
                sacrifice(game, self.controller, obj)


class MakeForEach(Sorcery):
    """Create a 2/2 creature token for your opponent, then a 1/1 for you."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Make for Each")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        opponent = next(p for p in game.players if p is not self.controller)
        _make_tokens(game, opponent, 2)
        _make_tokens(game, self.controller, 1)


_CONFIRM_THEN = [appears(0), appears(0)]


def test_a_retried_resolution_numbers_its_new_tokens_afresh():
    make = card(MakeAndConfirm)
    t = Table(_main(Side(hand=[make])))
    t.act(0, make, then=[moves(make, Zone.STACK)])
    t.pass_(0, branches=[[token(1), Decision.no()], [token(1), Decision.yes()]], note="declining is refused")
    t.pass_(1, then=[moves(make, Zone.GRAVEYARD), *_CONFIRM_THEN, life(0, 21)])
    final = t.run()
    assert final.players[0].life == 21
    assert {seen.handle for seen in final.players[0].battlefield} == {token(1), token(2)}


def test_a_confirmed_token_needs_no_retry():
    make = card(MakeAndConfirm)
    t = Table(_main(Side(hand=[make])))
    _cast_and_resolve(t, make, choices=[token(2), Decision.yes()], then=[*_CONFIRM_THEN, life(0, 22)])
    assert t.run().players[0].life == 22


def test_a_refused_resolution_with_no_branch_left_diverges():
    make = card(MakeAndConfirm)
    t = Table(_main(Side(hand=[make])))
    t.act(0, make, then=[moves(make, Zone.STACK)])
    t.pass_(0, choices=[token(1), Decision.no()])
    t.pass_(1, then=[moves(make, Zone.GRAVEYARD), *_CONFIRM_THEN])
    with pytest.raises(PlayDiverged, match="no branch left"):
        t.run()


def test_a_token_that_left_keeps_its_number():
    make = card(MakeSacrificeMake)
    t = Table(_main(Side(hand=[make])))
    _cast_and_resolve(t, make, then=[appears(0), ceases(token(1)), appears(0)])
    final = t.run()
    assert [seen.handle for seen in final.players[0].battlefield] == [token(2)]
    assert final.where(token(1)) is None


def test_a_token_made_after_one_left_takes_the_next_number():
    first, sweep, second, muster = card(MakeOne), card(SacrificeTokens), card(MakeOneAndTwo), card(Muster)
    t = Table(_main(Side(hand=[first, sweep, second, muster])))
    _cast_and_resolve(t, first, then=[appears(0)])
    _cast_and_resolve(t, sweep, then=[ceases(token(1))])
    _cast_and_resolve(t, second, then=[appears(0), appears(0)])
    _cast_and_resolve(t, muster, choices=[token(3)], then=[life(0, 22)])
    final = t.run()
    assert {seen.handle for seen in final.players[0].battlefield} == {token(2), token(3)}


def test_tokens_one_effect_makes_for_both_seats_are_numbered_seat_0_first():
    make, muster = card(MakeForEach), card(Muster)
    t = Table(_main(Side(hand=[make, muster])))
    _cast_and_resolve(t, make, then=[appears(1), appears(0)])
    _cast_and_resolve(t, muster, choices=[token(1)], then=[life(0, 21)])
    final = t.run()
    assert final.players[0].battlefield[0].handle == token(1)
    assert final.players[1].battlefield[0].handle == token(2)


def test_the_table_numbers_tokens_appearing_together_seat_0_first():
    t = Table(_main())
    t.pass_(0, then=[appears(1), appears(0)])
    expected = t.expected
    assert expected.players[0].battlefield[0].handle == token(1)
    assert expected.players[1].battlefield[0].handle == token(2)
