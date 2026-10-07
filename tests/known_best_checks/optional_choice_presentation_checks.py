"""Etali, Primal Storm's Audited cases hold however an engine asks which exiled
spells to cast: Known-Best asks yes/no for each card, but "you may cast any
number of spells from among them" is as naturally asked as a choice of the
cards to cast, choosing none to cast none. A script that answers only yes
passes only under the yes/no presentation, so each script also names the
cards it casts.

Every Audited case that resolves Etali's trigger runs under both
presentations, with a check that the card-choice presentation really asks for
cards.

Run inside ``known_best/workspace`` by
``tests/test_known_best_gameplay_regressions.py``.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import cards.fdn.fdn_194.card_impl as etali_impl
import pytest
from engine.card_queries import choose_object
from engine.types import Zone

REPO = Path(__file__).resolve().parents[2]
AUDITED = REPO / "known_best/data/tests/audited"
SUITES = {
    "fdn_165": AUDITED / "fdn/fdn_165/tests.py",
    "test_cast_spell_free": AUDITED / "engine/test_cast_spell_free.py",
    "test_casting": AUDITED / "engine/test_casting.py",
}
CHOOSE_CARDS = "Choose spells to cast without paying their mana costs"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(f"etali_audited_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _etali_cases():
    cases = []
    for name, path in SUITES.items():
        module = _load(name, path)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__ or not cls.__name__.startswith("Test"):
                continue
            for method, func in inspect.getmembers(cls, inspect.isfunction):
                if method.startswith("test_") and "etali" in inspect.getsource(func).lower():
                    cases.append((name, cls, method))
    return cases


ETALI_CASES = _etali_cases()


def _exiled(game, name: str):
    """The exiled card the yes/no prompt names, most recently exiled first."""
    for scripted in game.players:
        for exiled in reversed(scripted.zones[Zone.EXILE].get_all()):
            if getattr(exiled, "name", None) == name:
                return exiled
    raise AssertionError(f"no exiled card named {name!r}")


@pytest.fixture(params=["yes/no for each card", "cards to cast"])
def asked(request, monkeypatch):
    """Present Etali's casting choice as the parameter says; returns the
    card-choice questions asked, as (card name, card chosen or None)."""
    questions = []
    if request.param == "cards to cast":
        def cards_to_cast(game, player, prompt, *, source_card=None):
            name = prompt.removeprefix("Cast ").removesuffix(" without paying its mana cost?")
            chosen = choose_object(game, player, [_exiled(game, name)], CHOOSE_CARDS,
                                   source_card=source_card, optional=True)
            questions.append((name, chosen))
            return chosen is not None

        monkeypatch.setattr(etali_impl, "query_yes_no", cards_to_cast)
    return questions


def test_every_suite_has_etali_cases():
    assert {name for name, _, _ in ETALI_CASES} == set(SUITES)


@pytest.mark.parametrize("case", ETALI_CASES, ids=lambda c: f"{c[0]}.{c[1].__name__}.{c[2]}")
def test_audited_case_holds_however_the_casts_are_asked(case, asked):
    _, cls, method = case
    getattr(cls(), method)()


def test_the_card_choice_presentation_asks_for_cards(asked, request):
    """The card-choice presentation does ask, so the scripts' card answers
    are exercised."""
    if request.node.callspec.params["asked"] != "cards to cast":
        pytest.skip("only the card-choice presentation asks for cards")
    _, cls, method = next(c for c in ETALI_CASES if c[0] == "fdn_165")
    getattr(cls(), method)()
    assert [(name, chosen is not None) for name, chosen in asked] == [("Think Twice", True)]
