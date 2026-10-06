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


def _run(args: list[str], *, path: tuple[Path, ...] = ()) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=600, check=False,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(map(str, (WORKSPACE, *path))),
             "PYTHONDONTWRITEBYTECODE": "1"},
    )


def _codemod(path: Path, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return _run([str(CODEMOD), "--workspace", str(WORKSPACE), *(["--check"] if check else []),
                 str(path)])


def _pytest(path: Path, *, beside: bool = False) -> subprocess.CompletedProcess[str]:
    """Run the test file *path*; with *beside*, modules next to it import."""
    return _run(["-m", "pytest", str(path), "-q", "-p", "no:cacheprovider", "-p", "no:xdist",
                 "-c", str(WORKSPACE / "pytest.ini"), "--rootdir", str(path.parent)],
                path=(path.parent,) if beside else ())


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
    # A constructor counts only as the engine's own, imported by name.
    "GameRef redefined after its import": '''
from engine.decisions import GameRef


def GameRef(**attrs):
    return attrs


def test_label():
    assert dict(GameRef(card=frozenset({("name", "Abrade")}))["card"])["name"] == "Abrade"
''',
    "GameRef shadowed by a parameter and an assignment": '''
from engine.decisions import GameRef


def test_parameter(GameRef=lambda **attrs: attrs):
    assert dict(GameRef(card=frozenset({("name", "Abrade")}))["card"])["name"] == "Abrade"


def test_assignment():
    GameRef = lambda **attrs: attrs  # noqa: E731
    assert dict(GameRef(card=frozenset({("name", "Abrade")}))["card"])["name"] == "Abrade"
''',
    "qualified GameRef call": '''
import engine.decisions as decisions


def test_label():
    assert dict(decisions.GameRef(card=frozenset({("name", "Abrade")})).card)["name"] == "Abrade"
''',
    "aliased GameRef import": '''
from engine.decisions import GameRef as Ref


def test_label():
    assert dict(Ref(card=frozenset({("name", "Abrade")})).card)["name"] == "Abrade"
''',
    # A wildcard import may bind any name the rewrite relies on, and extending
    # one with another name would not compile.
    "wildcard import from the card's own module": '''
from cards.fdn.fdn_188.card_impl import *  # noqa: F403
from engine.decisions import Decision


def test_label():
    assert Decision.obj(name="Abrade") is not None
''',
    "class name captured by a match mapping's rest": '''
from engine.decisions import Decision


def test_label():
    match {"x": 1}:
        case {**Abrade}:
            assert Abrade == {"x": 1}
            assert Decision.obj(name="Abrade") is not None
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


_FOREIGN = {
    "Decision imported from an unrelated module": ("decision_helpers.py", '''
class Decision:
    @staticmethod
    def obj(**attrs):
        return attrs
''', '''
from decision_helpers import Decision


def test_label():
    assert Decision.obj(name="Abrade") == {"name": "Abrade"}
'''),
    "Decision rebound by a later wildcard import": ("decision_helpers.py", '''
class Decision:
    @staticmethod
    def obj(**attrs):
        return attrs
''', '''
from engine.decisions import Decision
from decision_helpers import *  # noqa: F403


def test_label():
    assert Decision.obj(name="Abrade") == {"name": "Abrade"}
'''),
    "GameRef called on an unrelated module": ("ref_helpers.py", '''
def GameRef(**attrs):
    return attrs
''', '''
import ref_helpers


def test_label():
    assert dict(ref_helpers.GameRef(card=frozenset({("name", "Abrade")}))["card"])["name"] == "Abrade"
'''),
}


@pytest.mark.parametrize("case", list(_FOREIGN))
def test_a_constructor_from_another_module_is_reported_and_the_file_left_whole(tmp_path, case):
    helper, helper_source, source = _FOREIGN[case]
    _write(tmp_path / "fdn" / "fdn_188" / helper, helper_source)
    path = _write(tmp_path / "fdn" / "fdn_188" / "tests.py", source)
    original = path.read_text()
    before = _pytest(path, beside=True)
    assert before.returncode == 0, before.stdout[-3000:]
    result = _codemod(path)
    assert "changed 0 files" in result.stdout and "0 sites need a hand edit" not in result.stdout, result.stdout
    assert path.read_text() == original and _pytest(path, beside=True).returncode == 0
    for _ in range(2):
        assert _codemod(path, check=True).returncode == 1


# Every construct that binds a name, each binding X. Any of them binding a
# constructor or the class a rewrite would import leaves the file manual.
_BINDS_X = {
    "assignment": "X = None",
    "annotation": "X: int",
    "augmented assignment": "X += 1",
    "deletion": "del X",
    "for target": "for X in ():\n    pass",
    "with target": "with open(__file__) as X:\n    pass",
    "walrus": "(X := 1)",
    "comprehension target": "[X for X in ()]",
    "def": "def X():\n    pass",
    "async def": "async def X():\n    pass",
    "class": "class X:\n    pass",
    "parameter": "def f(X):\n    pass",
    "positional-only parameter": "def f(X, /):\n    pass",
    "keyword-only parameter": "def f(*, X):\n    pass",
    "star parameter": "def f(*X):\n    pass",
    "double-star parameter": "def f(**X):\n    pass",
    "lambda parameter": "lambda X: X",
    "import alias": "import os as X",
    "from-import alias": "from os import path as X",
    "except name": "try:\n    pass\nexcept Exception as X:\n    pass",
    "match capture": "match 1:\n    case X:\n        pass",
    "match as": "match 1:\n    case 1 as X:\n        pass",
    "match star": "match []:\n    case [*X]:\n        pass",
    "match mapping rest": "match {}:\n    case {**X}:\n        pass",
    "global": "def f():\n    global X",
    "type parameter": "def f[X]():\n    pass",
    "class type parameter": "class C[X]:\n    pass",
    "type alias": "type X = int",
    "type alias parameter": "type A[X] = int",
}

_USES = {
    "Decision": "from engine.decisions import Decision\n\n\ndef test_label():\n    Decision.obj(name=\"Abrade\")\n",
    "GameRef": "from engine.decisions import GameRef\n\n\ndef test_label():\n"
               "    GameRef(card=frozenset({(\"name\", \"Abrade\")}))\n",
    "Abrade": "from engine.decisions import Decision\n\n\ndef test_label():\n    Decision.obj(name=\"Abrade\")\n",
}


def test_any_binding_of_a_name_the_rewrite_relies_on_leaves_the_file_whole(tmp_path):
    folder = tmp_path / "fdn" / "fdn_188"
    files = {}
    for shadowed, use in _USES.items():
        for i, binds in enumerate(_BINDS_X.values()):
            source = use + "\n\n" + binds.replace("X", shadowed) + "\n"
            files[_write(folder / f"test_{shadowed}_{i}.py", source)] = source
    controls = [_write(folder / f"test_control_{name}.py", use) for name, use in _USES.items()]
    result = _codemod(folder)
    assert result.returncode == 0, result.stderr
    for path, source in files.items():
        assert path.read_text() == source, path.name
        assert f"{path}:" in result.stdout, path.name
    # The same uses with nothing rebinding them convert.
    for path in controls:
        assert "printed=Abrade" in path.read_text() or '("printed", Abrade)' in path.read_text()


def test_a_reexported_engine_decision_still_converts(tmp_path):
    path = _write(tmp_path / "fdn" / "fdn_188" / "tests.py", '''
from test_interface import Decision


def test_label():
    assert Decision.obj(name="Abrade") is not None
''')
    assert "changed 1 files; 0 sites need a hand edit" in _codemod(path).stdout
    rewritten = path.read_text()
    assert "Decision.obj(printed=Abrade)" in rewritten
    assert "from cards.fdn.fdn_188.card_impl import Abrade" in rewritten
    assert _pytest(path).returncode == 0
    assert _codemod(path, check=True).returncode == 0


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


def test_a_rewrite_that_would_not_compile_is_reported_and_not_written(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("printed_identity_codemod", CODEMOD)
    codemod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, codemod)
    spec.loader.exec_module(codemod)
    catalog = codemod.Catalog(
        by_name={"Abrade": codemod.PrintedRef("Abrade", "cards.fdn.fdn_188.card_impl")},
        modes={},
        canonical={"Decision": frozenset({"engine.decisions"}), "GameRef": frozenset({"engine.decisions"})},
    )
    path = _write(tmp_path / "fdn" / "fdn_188" / "tests.py", '''
from engine.decisions import Decision


def test_label():
    Decision.obj(name="Abrade")
''')
    original = path.read_text()
    assert "printed=Abrade" in codemod.rewrite_file(path, catalog).source
    monkeypatch.setattr(codemod, "_import_edits", lambda rw, tree: ([], "from broken import (\n"))
    rewrite = codemod.rewrite_file(path, catalog)
    assert rewrite.source == original
    assert any("would not compile" in line for line in rewrite.manual)
