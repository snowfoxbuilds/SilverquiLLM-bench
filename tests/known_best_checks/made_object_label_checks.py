"""Tokens and spell copies are labels a test matches to what the engine makes
(TEST-INTERFACE.md): an engine numbers what it makes in its own order, so a
test's ``token(n)`` or ``spell_copy(n)`` names the object a view check first
found where the expected view had it, and keeps naming it. Objects first
seen at different view checks never trade labels; objects first seen
together are matched by where they show.

Every Known-Best Audited suite is rerun with the engine numbering what it
makes in another order (``renumbered_made.py``).

Run inside ``known_best/workspace`` by
``tests/test_known_best_gameplay_regressions.py``.
"""

from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import test_interface as ti
from cards.fdn.fdn_10.card_impl import DivineResilience
from cards.fdn.fdn_192.card_impl import BurstLightning
from engine.card import Creature, Sorcery
from engine.game import create_token
from engine.rollback import take_snapshot
from engine.stack import StackObject
from engine.types import CardType, Phase, Zone
from table import Table, appears, copied, moves
from test_interface import PlayDiverged, Side, card, create_game, spell_copy, token

REPO = Path(__file__).resolve().parents[2]
WORKSPACE = REPO / "known_best/workspace"
AUDITED = REPO / "known_best/data/tests/audited"


def _main(p0=None, p1=None):
    return create_game(p0 or Side(), p1 or Side(), start=(Phase.PRECOMBAT_MAIN, 0))


class Twin(Sorcery):
    """Copy each instant card in your graveyard, in graveyard order, and put
    the copies on the stack. ``reverse`` makes the engine number them in the
    opposite order to the one it puts them on the stack in."""

    reverse = False

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Twin")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        opponent = next(p for p in game.players if p is not self.controller)
        made = []
        for original in self.controller.zones[Zone.GRAVEYARD].get_all():
            if CardType.INSTANT in original.card_types:
                dup = copy.copy(original)
                made.append((dup, StackObject(source=dup, controller=self.controller, targets=[opponent], is_spell=True)))
        for dup, _ in reversed(made) if self.reverse else made:
            game.created_copies.append(dup)
        for _, obj in made:
            game.stack.push(obj)


class ReversedTwin(Twin):
    reverse = True


def _twin(cls=Twin):
    twin, bolt, shield = card(cls), card(BurstLightning), card(DivineResilience)
    t = Table(_main(Side(hand=[twin], graveyard=[bolt, shield])))
    t.act(0, twin, then=[moves(twin, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(twin, Zone.GRAVEYARD), copied(BurstLightning, 0), copied(DivineResilience, 0)])
    return t


@pytest.mark.parametrize("cls", [Twin, ReversedTwin])
def test_copies_made_together_are_matched_by_where_they_show_whatever_order_the_engine_numbers_them(cls):
    final = _twin(cls).run()
    assert [(seen.card, seen.handle) for seen in final.stack] == [
        (DivineResilience, spell_copy(2)), (BurstLightning, spell_copy(1)),
    ]


def test_a_copy_label_names_the_copy_it_was_matched_to():
    t = _twin(ReversedTwin)
    t.run()
    game = t.game
    bottom = game.stack.objects()[-1].source
    assert ti._numbered(game, ti.SpellCopy).by_id[id(bottom)] == spell_copy(2)
    assert ti._find(game, spell_copy(1)) is bottom


def _swapped(expected):
    return ti._rename(expected, {ti.SpellCopy: {1: 2, 2: 1}})


def test_a_label_stays_on_its_copy():
    t = _twin(ReversedTwin)
    expected = t.run()
    game = t.game
    raw = ti._raw_view(game)
    assert ti._match_labels(game, expected, raw) == {ti.Token: {}, ti.SpellCopy: {}}
    assert ti._match_labels(game, _swapped(expected), raw) is None


def _without_top(view_):
    return ti.replace(view_, stack=view_.stack[1:])


def _top_as(view_, cls):
    top = ti.replace(view_.stack[0], card=cls)
    return ti.replace(view_, stack=(top, *view_.stack[1:]))


@pytest.mark.parametrize("change", ["missing", "extra", "other class"])
def test_a_copy_of_another_class_a_missing_or_an_extra_copy_still_differs(change):
    t = _twin()
    expected = t.run()
    game = t.game
    raw = ti._raw_view(game)
    if change == "missing":
        assert ti._match_labels(game, _without_top(expected), raw) is None
    elif change == "extra":
        assert ti._match_labels(game, expected, _without_top(raw)) is None
    else:
        assert ti._match_labels(game, _top_as(expected, BurstLightning), raw) is None


def test_a_view_check_that_differs_reports_the_labels_and_when_each_was_first_seen():
    twin, bolt, shield = card(ReversedTwin), card(BurstLightning), card(DivineResilience)
    t = Table(_main(Side(hand=[twin], graveyard=[bolt, shield])))
    t.act(0, twin, then=[moves(twin, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(twin, Zone.GRAVEYARD), copied(DivineResilience, 0), copied(BurstLightning, 0)])
    with pytest.raises(PlayDiverged) as raised:
        t.run()
    report = str(raised.value)
    assert "Actual view (tokens and copies by the engine's numbers)" in report
    assert "copy 1 [turn 1 precombat main, player 0's turn, after action 3]" in report


def _bolt_on_the_stack():
    bolt = card(BurstLightning)
    game = _main(Side(hand=[bolt]))
    original = game.players[0].zones[Zone.HAND].get_all()[0]
    game.players[0].zones[Zone.HAND].remove(original)
    obj = StackObject(source=original, controller=game.players[0], targets=[game.players[1]], is_spell=True)
    game.stack.push(obj)
    return game, obj


def _copy(game, original):
    from engine.stack import copy_spell

    made = copy_spell(game, original, game.players[0])
    game.stack.push(made)
    return made


def test_a_label_on_a_copy_a_rollback_discards_is_free_again():
    game, original = _bolt_on_the_stack()
    snapshot = take_snapshot(game)
    discarded = _copy(game, original)
    assert ti._find(game, spell_copy(1)) is discarded.source
    snapshot.restore()
    assert ti._find(game, spell_copy(1)) is None
    retried = _copy(game, original)
    assert ti._find(game, spell_copy(1)) is retried.source


# ---------------------------------------------------------------------------
# Windows: objects first seen at different view checks never trade labels
# ---------------------------------------------------------------------------


def _bear(game, controller):
    (made,) = create_token(game, controller, Creature(name="Bear", base_power=2, base_toughness=2))
    return made


def _observe(game, expected):
    raw = ti._raw_view(game)
    stamp = ti._clock(game).stamp(raw)
    for kind in (ti.Token, ti.SpellCopy):
        ti._labels(game, kind).observe(game, expected, raw, stamp)
    ti._clock(game).actions += 1
    return raw


def _labelled(game, raw, labels):
    """``raw`` with tokens shown by ``labels``: engine number -> label."""
    return ti._rename(raw, {ti.Token: labels, ti.SpellCopy: {}})


def test_tokens_from_different_windows_never_trade_labels_however_the_engine_numbers_them():
    game = _main()
    first = _bear(game, game.players[0])
    raw = _observe(game, _labelled(game, ti._raw_view(game), {1: 1}))
    second = _bear(game, game.players[0])
    # The engine renumbers: the second token made becomes its token 1.
    game.created_tokens[:] = [second, first]
    ti._numbered(game, ti.Token).objects.clear()
    raw = ti._raw_view(game)
    expected_first_tapped = ti._rename(raw, {ti.Token: {2: 1, 1: 2}})
    _observe(game, expected_first_tapped)
    found = ti._match_labels(game, expected_first_tapped, raw)
    assert found is not None and found[ti.Token] == {1: 2, 2: 1}
    ti._labels(game, ti.Token).bind(game, found[ti.Token])
    assert ti._find(game, token(1)) is first and ti._find(game, token(2)) is second
    # With the first token tapped, only the labelling that keeps each label
    # on its own window's token matches.
    first.is_tapped = True
    raw = ti._raw_view(game)
    assert ti._match_labels(game, ti._rename(raw, {ti.Token: {2: 1, 1: 2}}), raw) is not None
    assert ti._match_labels(game, raw, raw) is None


def test_copies_from_different_windows_never_trade_labels():
    game, original = _bolt_on_the_stack()
    first = _copy(game, original)
    _observe(game, ti.view(game))
    second = _copy(game, original)
    raw = ti._raw_view(game)
    by_engine = {s.handle.number for s in raw.stack if isinstance(s.handle, ti.SpellCopy)}
    assert by_engine == {1, 2}
    # The same view with the two copies' labels swapped: copy 1 shows where
    # the second copy, first seen a window later, is.
    swapped = ti._rename(raw, {ti.SpellCopy: {1: 2, 2: 1}})
    _observe(game, swapped)
    assert ti._match_labels(game, swapped, raw) is None
    assert ti._match_labels(game, raw, raw) is not None
    del first, second


class MakeThree(Sorcery):
    """Create three 1/1 creature tokens."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Make Three")
        super().__init__(**kwargs)

    def on_resolve(self, game):
        for _ in range(3):
            create_token(game, self.controller, Creature(name="Token", base_power=1, base_toughness=1))
        # The engine numbers them in the opposite order.
        game.created_tokens[-3:] = reversed(game.created_tokens[-3:])


def test_tokens_one_effect_makes_are_labels_whatever_order_the_engine_numbers_them():
    make = card(MakeThree)
    t = Table(_main(Side(hand=[make])))
    t.act(0, make, then=[moves(make, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(make, Zone.GRAVEYARD), appears(0), appears(0), appears(0)])
    final = t.run()
    assert {seen.handle for seen in final.players[0].battlefield} == {token(1), token(2), token(3)}


def test_a_token_label_held_through_a_later_window():
    make, again = card(MakeThree), card(MakeThree)
    t = Table(_main(Side(hand=[make, again])))
    t.act(0, make, then=[moves(make, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(make, Zone.GRAVEYARD), appears(0), appears(0), appears(0)])
    t.act(0, again, then=[moves(again, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(again, Zone.GRAVEYARD), appears(0), appears(0), appears(0)])
    t.run()
    labels = ti._labels(t.game, ti.Token)
    stamps = {label: labels.label_stamps[label].actions for label in range(1, 7)}
    assert len({stamps[1], stamps[2], stamps[3]}) == 1 and len({stamps[4], stamps[5], stamps[6]}) == 1
    assert stamps[1] != stamps[4]


# ---------------------------------------------------------------------------
# Every Audited suite holds whatever order the engine numbers what it makes in
# ---------------------------------------------------------------------------


def _audited(target: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(target), "-q", "-p", "no:cacheprovider", "-p", "no:xdist",
         "-p", "renumbered_made", "-c", str(WORKSPACE / "pytest.ini"), "--rootdir", str(WORKSPACE)],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=600, check=False,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(map(str, (Path(__file__).parent, WORKSPACE, REPO))),
             "PYTHONDONTWRITEBYTECODE": "1"},
    )


def test_every_fdn_audited_case_holds_with_made_objects_renumbered():
    result = _audited(AUDITED / "fdn")
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]


def test_every_engine_audited_case_holds_with_made_objects_renumbered(tmp_path):
    # Staged as a workspace stages them, beside the engine rather than inside it.
    staged = tmp_path / "engine_tests"
    shutil.copytree(AUDITED / "engine", staged, ignore=shutil.ignore_patterns("test_card_impl_ast_guard.py"))
    result = _audited(staged)
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]


def test_the_renumbering_really_renumbers():
    probe = (
        "import renumbered_made, pytest\n"
        "mp = pytest.MonkeyPatch()\n"
        "renumbered_made.renumber_made(mp)\n"
        "from test_interface import Side, create_game, view\n"
        "from engine.types import Phase\n"
        "from engine.card import Creature\n"
        "from engine.game import create_token\n"
        "game = create_game(Side(), Side(), start=(Phase.PRECOMBAT_MAIN, 0))\n"
        "a = create_token(game, game.players[0], Creature(name='A', base_power=1, base_toughness=1))[0]\n"
        "b = create_token(game, game.players[0], Creature(name='B', base_power=2, base_toughness=2))[0]\n"
        "print([made is a for made in game.created_tokens].index(True) > [made is b for made in game.created_tokens].index(True))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=WORKSPACE, capture_output=True, text=True, timeout=120, check=False,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(map(str, (Path(__file__).parent, WORKSPACE, REPO)))},
    )
    assert result.stdout.strip() == "True", result.stdout + result.stderr
