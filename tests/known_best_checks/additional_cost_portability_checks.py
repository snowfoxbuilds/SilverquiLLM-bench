"""Eaten Alive's Audited Tests hold for every way an engine may present its
additional cost (rule 601.2b): Known-Best offers only the alternatives the
caster can pay and picks a sole payable one itself, but an engine may offer
both and reject an unpayable one when it is paid (ADR-017), in either order.

Each Audited case runs under four presentations — Known-Best's, with both
alternatives always offered, and each with the alternatives in reverse order —
together with checks that a rejected cast leaves its mana and its creature to
pay for a legal one.

Run inside ``known_best/workspace`` by
``tests/test_known_best_gameplay_regressions.py``.
"""

from __future__ import annotations

import importlib.util
import inspect
from dataclasses import replace
from pathlib import Path

import engine.additional_costs
import engine.queries
import pytest
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_172.card_impl import EatenAlive, EatenAliveAbility1
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_276.card_impl import Swamp
from engine.decisions import Decision
from engine.types import ManaType, Phase, Zone
from test_interface import PlayDiverged, Side, card, create_game

from table import Table, moves, taps

AUDITED = Path(__file__).resolve().parents[2] / "known_best/data/tests/audited/fdn/fdn_172/tests.py"
HOW_TO_PAY = "Choose how to pay the additional cost"
MAIN = (Phase.PRECOMBAT_MAIN, 0)
SACRIFICE = Decision.ability(index=0, printed=EatenAliveAbility1)
PAY_MANA = Decision.ability(index=1, printed=EatenAliveAbility1)
PRESENTATIONS = ["payable only", "payable only, reversed", "both offered", "both offered, reversed"]


def _load_audited():
    spec = importlib.util.spec_from_file_location("eaten_alive_audited", AUDITED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDITED_MODULE = _load_audited()
AUDITED_CASES = [
    (cls, name)
    for _, cls in inspect.getmembers(AUDITED_MODULE, inspect.isclass)
    if cls.__module__ == AUDITED_MODULE.__name__ and cls.__name__.startswith("Test")
    for name, _ in inspect.getmembers(cls, inspect.isfunction)
    if name.startswith("test_")
]


@pytest.fixture(params=PRESENTATIONS)
def asked(request, monkeypatch):
    """Present the additional cost as the parameter says; returns the cost
    questions asked, as the option lists offered."""
    if request.param.startswith("both offered"):
        monkeypatch.setattr(engine.additional_costs, "_feasible", lambda *args, **kwargs: True)
    reverse = request.param.endswith("reversed")
    original = engine.queries.ask
    questions = []

    def ask(player, query):
        if query.prompt == HOW_TO_PAY:
            questions.append(query.options)
            if reverse:
                query = replace(query, options=tuple(reversed(query.options)))
        return original(player, query)

    monkeypatch.setattr(engine.queries, "ask", ask)
    return questions


def test_the_audited_suite_has_every_case():
    assert len(AUDITED_CASES) == 8


@pytest.mark.parametrize("case", AUDITED_CASES, ids=lambda c: f"{c[0].__name__}.{c[1]}")
def test_audited_case_holds_however_the_cost_is_presented(case, asked):
    cls, name = case
    getattr(cls(), name)()


@pytest.mark.parametrize(
    "name",
    ["test_sacrificing_a_creature_pays_the_additional_cost", "test_paying_three_and_black_pays_the_additional_cost"],
)
def test_offering_both_alternatives_asks_which_to_pay(name, monkeypatch):
    """The presentation that offers both alternatives does ask, so the
    Audited scripts' answers to it are exercised."""
    monkeypatch.setattr(engine.additional_costs, "_feasible", lambda *args, **kwargs: True)
    questions = []
    original = engine.queries.ask

    def ask(player, query):
        if query.prompt == HOW_TO_PAY:
            questions.append(query)
        return original(player, query)

    monkeypatch.setattr(engine.queries, "ask", ask)
    getattr(AUDITED_MODULE.TestEatenAliveAdditionalCost(), name)()
    assert [len(q.options) for q in questions] == [2]


def test_offering_both_alternatives_rejects_the_unpayable_one(monkeypatch):
    """Choosing the sacrifice with no creature to sacrifice is rejected rather
    than paid as nothing, and the question is asked again."""
    monkeypatch.setattr(engine.additional_costs, "_feasible", lambda *args, **kwargs: True)
    eaten, theirs = card(EatenAlive), card(SavannahLions)
    t = Table(create_game(
        Side(hand=[eaten], library=[card(Plains)], mana={ManaType.BLACK: 2, ManaType.COLORLESS: 3}),
        Side(battlefield=[theirs], library=[card(Plains)]),
        start=MAIN,
    ))
    t.act_illegal(0, eaten, SACRIFICE, choices=[theirs])
    t.act(0, eaten, PAY_MANA, choices=[theirs], then=[moves(eaten, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(eaten, Zone.GRAVEYARD), moves(theirs, Zone.EXILE)])
    t.run()


def test_a_rejected_cast_keeps_its_mana_for_a_legal_one(asked):
    """One mana short of {3}{B}{B}, with nothing to sacrifice: the cast is
    rejected with either alternative; tapping a Swamp then pays the full
    {3}{B}{B} with the mana that was in the pool."""
    eaten, swamp, theirs = card(EatenAlive), card(Swamp), card(SavannahLions)
    t = Table(create_game(
        Side(hand=[eaten], battlefield=[swamp], library=[card(Plains)], mana={ManaType.BLACK: 2, ManaType.COLORLESS: 2}),
        Side(battlefield=[theirs], library=[card(Plains)]),
        start=MAIN,
    ))
    t.act_illegal(0, branches=[[eaten, SACRIFICE], [eaten, PAY_MANA]], choices=[theirs])
    t.act(0, swamp, then=[taps(swamp)])
    t.act(0, eaten, PAY_MANA, choices=[theirs], then=[moves(eaten, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(eaten, Zone.GRAVEYARD), moves(theirs, Zone.EXILE)])
    t.run()


def test_a_rejected_cast_keeps_its_creature_for_a_legal_one(asked):
    """With a creature but no {B}: the cast is rejected with either
    alternative and the creature stays; tapping a Swamp for {B} then casts
    it by sacrificing that creature."""
    eaten, swamp, mine, theirs = card(EatenAlive), card(Swamp), card(SavannahLions), card(SavannahLions)
    t = Table(create_game(
        Side(hand=[eaten], battlefield=[swamp, mine], library=[card(Plains)], mana={ManaType.COLORLESS: 4}),
        Side(battlefield=[theirs], library=[card(Plains)]),
        start=MAIN,
    ))
    t.act_illegal(0, branches=[[eaten, SACRIFICE], [eaten, PAY_MANA]], choices=[theirs])
    t.act(0, swamp, then=[taps(swamp)])
    t.act(0, eaten, SACRIFICE, choices=[theirs], then=[moves(eaten, Zone.STACK), moves(mine, Zone.GRAVEYARD)])
    t.pass_(0)
    t.pass_(1, then=[moves(eaten, Zone.GRAVEYARD), moves(theirs, Zone.EXILE)])
    t.run()


def test_an_answer_naming_neither_alternative_is_not_invented(monkeypatch):
    """A script that names no alternative where both are offered is not
    answered for it: play diverges at the question."""
    monkeypatch.setattr(engine.additional_costs, "_feasible", lambda *args, **kwargs: True)
    eaten, mine, theirs = card(EatenAlive), card(SavannahLions), card(SavannahLions)
    t = Table(create_game(
        Side(hand=[eaten], battlefield=[mine], library=[card(Plains)], mana={ManaType.BLACK: 1}),
        Side(battlefield=[theirs], library=[card(Plains)]),
        start=MAIN,
    ))
    t.act(0, eaten, choices=[theirs], then=[moves(eaten, Zone.STACK), moves(mine, Zone.GRAVEYARD)])
    with pytest.raises(PlayDiverged, match="answers this question"):
        t.run()
