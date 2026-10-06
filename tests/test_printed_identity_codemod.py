"""The printed-identity codemod (scripts/printed_identity_codemod.py).

The codemod rewrites only sites that need no inference — a string literal at
a helper argument, a ``Decision`` name or mode, or a GameRef name pair,
mapped through the card registry — and reports every other name-carrying
site for a hand edit. Each case writes a small test file, runs the codemod
on it against the Known-Best Workspace's predefined classes, and runs the
file with pytest inside that workspace before and after. A converted file
must keep passing and check clean; a reported file must stay byte-identical,
keep passing, and keep ``--check`` failing.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO / "known_best/workspace"
CODEMOD = REPO / "scripts/printed_identity_codemod.py"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=600, check=False,
        env={**os.environ, "PYTHONPATH": str(WORKSPACE), "PYTHONDONTWRITEBYTECODE": "1"},
    )


def _codemod(path: Path, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return _run([str(CODEMOD), "--workspace", str(WORKSPACE), *(["--check"] if check else []),
                 str(path)])


def _pytest(path: Path) -> subprocess.CompletedProcess[str]:
    return _run(["-m", "pytest", str(path), "-q", "-p", "no:cacheprovider", "-p", "no:xdist",
                 "-c", str(WORKSPACE / "pytest.ini"), "--rootdir", str(path.parent)])


def _write(path: Path, source: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source).lstrip())
    return path


_MATCHES = '''
from engine.card import Instant
from engine.decisions import Decision, GameRef, ref_matches
from test_utils import create_game, set_board_state


def _matches(pattern, obj):
    game = create_game()
    set_board_state(game, 0, hand=[obj])
    return ref_matches(pattern, game.refs.object_decision(obj, zone="hand").ref)


class Zap(Instant):
    pass
'''


# ---- literals mapped through the registry are converted ----------------------


def test_registry_literals_convert_and_check_clean(tmp_path):
    path = _write(tmp_path / "fdn" / "fdn_188" / "tests.py", _MATCHES + '''
from cards.fdn.fdn_188.card_impl import Abrade
from test_utils import cast_spell


def _cast_by_name(game):
    cast_spell(game, 0, "Abrade")


def test_name_pair():
    assert _matches(GameRef(card=frozenset({("name", "Abrade")})), Abrade())


def test_decision_name():
    assert dict(Decision.obj(name="Abrade").attrs)["printed"] is Abrade


def test_own_mode():
    assert dict(Decision.mode("Damage").attrs)["printed"].__name__ == "AbradeAbility2"
''')
    assert _pytest(path).returncode != 0  # the name-based version is not class-based yet
    first = _codemod(path)
    assert "changed 1 files; 0 sites need a hand edit" in first.stdout, first.stdout
    rewritten = path.read_text()
    assert 'cast_spell(game, 0, Abrade)' in rewritten
    assert '("printed", Abrade)' in rewritten and "Decision.obj(printed=Abrade)" in rewritten
    assert "Decision.mode(printed=AbradeAbility2)" in rewritten
    assert "from cards.fdn.fdn_188.card_impl import Abrade, AbradeAbility2" in rewritten
    ran = _pytest(path)
    assert ran.returncode == 0, ran.stdout[-3000:]
    assert _codemod(path, check=True).returncode == 0


# ---- every other name-carrying site is reported, never rewritten ---------------

_CARD_HELPER = _MATCHES + '''
from cards.fdn.fdn_188.card_impl import Abrade


def card_ref(card_name):
    return GameRef(card=frozenset({("name", card_name)}))
'''

_REPORTED = {
    # The sixth review's cases.
    "annotated rebinding of a name attribute": _MATCHES + '''

def test_match():
    source = Zap(name="Abrade")
    source: Instant = Instant(name="Abrade")
    assert _matches(GameRef(card=frozenset({("name", source.name)})), source)
''',
    "nested function supplying a method receiver": _MATCHES + '''

class Helper:
    def card_ref(self, card_name):
        return GameRef(card=frozenset({("name", card_name)}))


class Labels:
    def card_ref(self, label):
        return label


def test_label():
    helper: Labels = Labels()

    def unused():
        helper = Helper()
        return helper

    assert helper.card_ref("Abrade") == "Abrade"
''',
    "nested string binding": _CARD_HELPER + '''
from cards.fdn.fdn_215.card_impl import Bushwhack

name = "Bushwhack"


def test_match():
    def unused():
        name = "Abrade"
        return name

    assert _matches(card_ref(name), Bushwhack())
''',
    # Earlier rounds' cases.
    "helper parameter with literal, keyword, default and parametrized callers": _CARD_HELPER + '''
import pytest


def test_literal():
    assert _matches(card_ref("Abrade"), Abrade())


def test_keyword():
    assert _matches(card_ref(card_name="Abrade"), Abrade())


def test_default(card_name="Abrade"):
    assert _matches(card_ref(card_name), Abrade())


@pytest.mark.parametrize("card_name", ["Abrade"])
def test_parametrized(card_name):
    assert _matches(card_ref(card_name), Abrade())
''',
    "helper passed to map or called with unpacked keywords": _CARD_HELPER + '''

def test_map():
    assert all(_matches(ref, Abrade()) for ref in map(card_ref, ["Abrade"]))


def test_unpacked():
    assert _matches(card_ref(**{"card_name": "Abrade"}), Abrade())
''',
    "rebound helper": _CARD_HELPER + '''

def label(value):
    return value


card_ref = label


def test_rebound():
    assert card_ref("Abrade") == "Abrade"
''',
    "local class shadowing the catalog class": _MATCHES + '''
from cards.fdn.fdn_188.card_impl import Abrade as RealAbrade


class Abrade(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Local spell")
        super().__init__(**kwargs)


def test_match():
    assert _matches(GameRef(card=frozenset({("name", "Abrade")})), RealAbrade())
''',
    "test object built with a printed card's name": _MATCHES + '''

def test_assigned_after_use():
    pattern = GameRef(card=frozenset({("name", "Abrade")}))
    source = Zap(name="Abrade")
    assert _matches(pattern, source)


def test_generic_object():
    source = Instant(name="Abrade")
    assert source.name == "Abrade"
''',
    "engine class re-exported by a card module": '''
from cards.fdn.fdn_188.card_impl import Instant
from engine.decisions import GameRef, ref_matches
from test_utils import create_game, set_board_state


def test_reexported():
    source = Instant(name="Abrade")
    game = create_game()
    set_board_state(game, 0, hand=[source])
    pattern = GameRef(card=frozenset({("name", "Abrade")}))
    assert ref_matches(pattern, game.refs.object_decision(source, zone="hand").ref)
''',
    "mode helper and computed mode": '''
from engine.decisions import Decision


def mode_of(mode_name):
    return Decision.mode(mode_name)


def test_literal():
    assert mode_of("Damage") == Decision.mode(name="Damage")
''',
    "name with no predefined card, and computed names": _MATCHES + '''
from test_utils import cast_spell


def _cast_computed(game, suffix):
    cast_spell(game, 0, f"Ab{suffix}")


def test_unknown():
    assert GameRef(card=frozenset({("name", "No Such Card")}))
''',
    # The final review's cases.
    "object built with a name that is not a literal": _MATCHES + '''
CARD_NAME = "Abrade"


def test_match():
    source = Zap(name=CARD_NAME)
    assert _matches(GameRef(card=frozenset({("name", "Abrade")})), source)
''',
    "object whose name default is not a literal": _MATCHES + '''
LABEL = "Abrade"


class Local(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", LABEL)
        super().__init__(**kwargs)


def test_match():
    assert _matches(GameRef(card=frozenset({("name", "Abrade")})), Local())
''',
    "imported helper redefined": '''
from test_utils import cast_spell


def cast_spell(game, seat, label):
    return label


def test_label():
    assert cast_spell(None, 0, "Abrade") == "Abrade"
''',
    "imported helper shadowed by a parameter and an assignment": '''
from test_utils import cast_spell


def test_parameter(cast_spell=lambda game, seat, label: label):
    assert cast_spell(None, 0, "Abrade") == "Abrade"


def test_assignment():
    cast_spell = lambda game, seat, label: label  # noqa: E731
    assert cast_spell(None, 0, "Abrade") == "Abrade"
''',
    "Decision rebound": '''
from engine.decisions import Decision


class Decision:
    @staticmethod
    def obj(**attrs):
        return attrs


def test_label():
    assert Decision.obj(name="Abrade") == {"name": "Abrade"}
''',
    "name pair naming a card outside a GameRef card field": '''
def test_metadata():
    metadata = dict([("name", "Abrade")])
    assert metadata["name"] == "Abrade"
''',
    "name comparison with a predefined card's name": _MATCHES + '''
from cards.fdn.fdn_188.card_impl import Abrade


def test_compare():
    assert Abrade().name == "Abrade"
''',
}


@pytest.mark.parametrize("case", list(_REPORTED))
def test_a_name_site_needing_inference_is_reported_and_the_file_left_whole(tmp_path, case):
    path = _write(tmp_path / "fdn" / "fdn_188" / "tests.py", _REPORTED[case])
    original = path.read_text()
    before = _pytest(path)
    assert before.returncode == 0, before.stdout[-3000:]
    result = _codemod(path)
    assert result.returncode == 0 and "0 sites need a hand edit" not in result.stdout, result.stdout
    assert path.read_text() == original
    assert _pytest(path).returncode == 0
    for _ in range(2):
        check = _codemod(path, check=True)
        assert check.returncode == 1 and "0 sites need a hand edit" not in check.stdout, check.stdout


# ---- class-based code is left alone -------------------------------------------

_ALREADY_CLASS_BASED = {
    "comprehension target shadowing a parameter": '''
from cards.fdn.fdn_188.card_impl import Abrade
from engine.decisions import GameRef


def label(card_name):
    refs = [GameRef(card=frozenset({("printed", card_name)})) for card_name in [Abrade]]
    assert refs
    return card_name


def test_label():
    assert label("Abrade") == "Abrade"
''',
    "nested printed card consumer": '''
from engine.decisions import GameRef


def label(card_name):
    def nested(card_name):
        return GameRef(card=frozenset({("printed", card_name)}))
    return card_name


def test_match():
    assert label("Abrade") == "Abrade"
''',
    "a name pair that is not a card identity": '''
from engine.decisions import GameRef


def test_metadata():
    metadata = dict([("name", "Not a card")])
    zone = GameRef(zone=frozenset({("name", "hand")}))
    assert metadata["name"] == "Not a card" and zone.zone
''',
    "nested printed mode consumer": '''
from engine.decisions import Decision


def label(mode_name):
    def nested(mode_name):
        return Decision.mode(printed=mode_name)
    return mode_name


def test_match():
    assert label("Damage") == "Damage"
''',
}


@pytest.mark.parametrize("case", list(_ALREADY_CLASS_BASED))
def test_class_based_code_is_left_alone_and_checks_clean(tmp_path, case):
    path = _write(tmp_path / "fdn" / "fdn_188" / "tests.py", _ALREADY_CLASS_BASED[case])
    original = path.read_text()
    result = _codemod(path)
    assert "changed 0 files; 0 sites need a hand edit" in result.stdout, result.stdout
    assert path.read_text() == original and _pytest(path).returncode == 0
    assert _codemod(path, check=True).returncode == 0


def test_a_helper_argument_check_inside_pytest_raises_is_left_alone(tmp_path):
    path = _write(tmp_path / "test_raises.py", '''
from test_utils import TestSetupError, cast_spell, create_game
import pytest


def test_refuses_names():
    with pytest.raises(TestSetupError):
        cast_spell(create_game(), 0, "Abrade")
''')
    assert "changed 0 files; 0 sites need a hand edit" in _codemod(path).stdout
