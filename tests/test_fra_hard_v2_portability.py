"""fra-hard-v2's hidden suites judge what takes effect, not how choices are presented.

ADR-017 lets an engine present a multi-face or prepared card as one option or
as its card and then a face question, and lets it offer an action the rules
forbid as long as choosing it is rejected. Each variant below rewraps the Test
Oracle Workspace's Priority Query that way — card behavior unchanged — and the
FRA suites must still pass; a faulty variant that lets an illegal action take
effect must make them fail.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks/fra-hard-v2"
ORACLE = BENCH / "data/test_oracle_workspace"

# Offers every ability of every permanent the player controls and every card in
# their exile and graveyard as a cast, legal or not; the engine's own casting and
# activation checks then reject the illegal ones.
OFFER_THEN_REJECT = '''
import engine.priority as _priority
from engine.casting import CastMode as _CastMode, cast_spell as _cast_spell
from engine.types import Zone as _Zone

_original = _priority.priority_query


def _offering_everything(game, player):
    query, actions = _original(game, player)
    seat = _priority._seat(game, player)
    extra = {}
    for source in _priority._controlled_permanents(game, player):
        for index, ability in enumerate(_priority.activatable_abilities(source, game)):
            decision = _priority._ability_decision(game, seat, source, index, ability)
            if decision not in actions:
                extra[decision] = _priority._activation(game, player, source, ability)
    for zone in (_Zone.EXILE, _Zone.GRAVEYARD):
        for card in list(player.zones[zone].get_all()):
            decision = game.refs.object_decision(card, zone=zone.value, controller_seat=seat)
            if decision not in actions:
                extra[decision] = (lambda c=card, z=zone: _cast_spell(game, player, c, from_zone=z,
                                                                     mode=_CastMode.NORMAL))
    actions = {**actions, **extra}
    options = tuple(actions)
    return query.__class__(source=query.source, prompt=query.prompt, options=options,
                           min=0, max=min(1, len(options))), actions


_priority.priority_query = _offering_everything
'''

# Presents a prepared spell as the permanent it was prepared from, then asks
# which of the two to cast.
CARD_THEN_FACE = '''
import engine.priority as _priority
from engine.decisions import InvalidPlayerChoiceError as _Invalid
from engine.queries import PlayerQuery as _Query, ask as _ask
from engine.types import Zone as _Zone

_original = _priority.priority_query


def _card_then_face(game, player):
    query, actions = _original(game, player)
    seat = _priority._seat(game, player)
    rewritten = {}
    for decision, action in actions.items():
        spell = next((card for card in player.zones[_Zone.COMMAND].get_all()
                      if game.refs.object_decision(card, zone="command", controller_seat=seat) == decision
                      and getattr(card, "prepared_source", None) is not None), None)
        if spell is None:
            rewritten[decision] = action
            continue
        source = spell.prepared_source
        card = game.refs.object_decision(source, zone="battlefield", controller_seat=seat)

        def choose_face(source=source, card=card, face=decision, cast=action):
            question = _Query(source=(card,), prompt="Cast which?", options=(card, face), min=1, max=1)
            if _ask(player, question).selected != (face,):
                raise _Invalid("a prepared permanent is not itself a spell to cast")
            return cast()

        rewritten[card] = choose_face
    options = tuple(rewritten)
    return query.__class__(source=query.source, prompt=query.prompt, options=options,
                           min=0, max=min(1, len(options))), rewritten


_priority.priority_query = _card_then_face
'''

# Presents a prepared spell through its card as above, and also keeps offering
# every other permanent a spell could be prepared from, in battlefield order,
# rejecting the ones that are not prepared.
CARD_THEN_FACE_ALL_SOURCES = CARD_THEN_FACE + '''
from engine.card import printed_class as _printed_class

_card_then_face_only = _priority.priority_query


def _every_source(game, player):
    query, actions = _card_then_face_only(game, player)
    seat = _priority._seat(game, player)
    kinds = {_printed_class(card) for card in player.zones[_Zone.COMMAND].get_all()
             if getattr(card, "prepared_source", None) is not None}
    kinds |= {_printed_class(card) for card in game.get_battlefield(player).get_all()
              if hasattr(card, "prepared")}
    permanents = [(card, game.refs.object_decision(card, zone="battlefield", controller_seat=seat))
                  for card in game.get_battlefield(player).get_all()]
    on_battlefield = {decision for _, decision in permanents}

    def unprepared():
        raise _Invalid("this permanent has no prepared spell")

    reordered = {d: a for d, a in actions.items() if d not in on_battlefield}
    for card, decision in permanents:
        if decision in actions:
            reordered[decision] = actions[decision]
        elif _printed_class(card) in kinds:
            reordered[decision] = unprepared
    actions = reordered
    options = tuple(actions)
    return query.__class__(source=query.source, prompt=query.prompt, options=options,
                           min=0, max=min(1, len(options))), actions


_priority.priority_query = _every_source
'''

# Presents prepared spells directly, but keeps offering — first — each prepared
# spell already cast and still on the stack, rejecting it when chosen.
CONSUMED_FACE_FIRST = '''
import engine.priority as _priority
from engine.decisions import InvalidPlayerChoiceError as _Invalid
from engine.types import Zone as _Zone

_original = _priority.priority_query


def _consumed_first(game, player):
    query, actions = _original(game, player)
    seat = _priority._seat(game, player)

    def consumed():
        raise _Invalid("that prepared spell has already been cast")

    stale = {}
    for spell in player.zones[_Zone.STACK].get_all():
        if getattr(spell, "prepared_source", None) is not None:
            stale[game.refs.object_decision(spell, zone="stack", controller_seat=seat)] = consumed
    actions = {**stale, **{d: a for d, a in actions.items() if d not in stale}}
    options = tuple(actions)
    return query.__class__(source=query.source, prompt=query.prompt, options=options,
                           min=0, max=min(1, len(options))), actions


_priority.priority_query = _consumed_first
'''

# Presents a prepared spell through its card as above, and first offers every
# card in exile of the same kind as a prepared spell's source (an exiled
# original whose copy is prepared), rejecting it when chosen.
EXILED_SOURCE_FIRST = CARD_THEN_FACE + '''
from engine.card import printed_class as _printed_class

_card_then_face_only = _priority.priority_query


def _exiled_first(game, player):
    query, actions = _card_then_face_only(game, player)
    seat = _priority._seat(game, player)
    kinds = {_printed_class(card.prepared_source) for card in player.zones[_Zone.COMMAND].get_all()
             if getattr(card, "prepared_source", None) is not None}

    def no_permission():
        raise _Invalid("an exiled card with no cast permission")

    stale = {}
    for card in player.zones[_Zone.EXILE].get_all():
        if getattr(card, "prepared_source", None) is None and _printed_class(card) in kinds:
            stale[game.refs.object_decision(card, zone="exile", controller_seat=seat)] = no_permission
    actions = {**stale, **{d: a for d, a in actions.items() if d not in stale}}
    options = tuple(actions)
    return query.__class__(source=query.source, prompt=query.prompt, options=options,
                           min=0, max=min(1, len(options))), actions


_priority.priority_query = _exiled_first
'''

# Hall of Echoes only: keeps offering, first, the copy ability of a Hall that is
# currently a copy of something else, rejecting it when chosen.
HALL_REMOVED_ABILITY_FIRST = '''
from types import SimpleNamespace as _Namespace

import engine.priority as _priority
from engine.decisions import InvalidPlayerChoiceError as _Invalid

_original = _priority.priority_query


def _removed_first(game, player):
    query, actions = _original(game, player)
    seat = _priority._seat(game, player)

    def removed():
        raise _Invalid("this permanent no longer has that ability")

    stale = {}
    for card in _priority._controlled_permanents(game, player):
        if getattr(card, "_copy_original_class", None) is HallOfEchoes:
            ability = _Namespace(printed=HallOfEchoesAbility2)
            stale[_priority._ability_decision(game, seat, card, 99, ability)] = removed
    actions = {**stale, **{d: a for d, a in actions.items() if d not in stale}}
    options = tuple(actions)
    return query.__class__(source=query.source, prompt=query.prompt, options=options,
                           min=0, max=min(1, len(options))), actions


_priority.priority_query = _removed_first
'''

# Faulty: a card in exile, or a spell copy held for a later cast, may be cast
# with no permission at all.
CASTS_ANYTHING_IN_EXILE = '''
import engine.casting as _casting
from engine.types import Zone as _Zone

_original_permission = _casting.cast_permission


def _always(game, player, card):
    permission = _original_permission(game, player, card)
    for zone in (_Zone.EXILE, _Zone.COMMAND):
        if permission is None and player.zones[zone].contains(card):
            return dict(player=player, card=card, zone=zone, life_cost=False,
                        departure_zone=None, source=None, normal_face_only=False)
    return permission


_casting.cast_permission = _always
'''

# Faulty: casting a prepared permanent's spell copy leaves it prepared.
PREPARED_AFTER_CASTING = '''
import engine.preparation as _preparation


def consume_preparation(game, spell):
    source = getattr(spell, "prepared_source", None)
    if source is not None:
        source.prepared = False
        source.prepared_copy = None
        _preparation.prepare(game, source, type(spell))
'''

# Faulty: a planeswalker's loyalty abilities may be activated any number of times a turn.
LOYALTY_EVERY_TIME = '''
import engine.abilities as _abilities
import engine.priority as _priority

_abilities._has_activated_loyalty_this_turn = lambda source, turn: False
_priority._has_activated_loyalty_this_turn = lambda source, turn: False
'''


def run_suite(card: str, suffix: str) -> tuple[int, int, str]:
    """Run ``card``'s hidden suite on the oracle with ``suffix`` appended to its
    implementation; return (passed, failed, output)."""
    code = card.split("_")[0]
    with tempfile.TemporaryDirectory(prefix=f"portability_{card}_") as tmp_dir:
        tmp = Path(tmp_dir)
        impl = (ORACLE / "cards" / code / card / "card_impl.py").read_text()
        (tmp / "card_impl.py").write_text(impl + "\n" + suffix)
        shutil.copy2(BENCH / "data/tests/audited" / code / card / "tests.py", tmp / "tests.py")
        env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(tmp), str(ORACLE), str(ROOT)]),
               "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(tmp / "tests.py"), "-q", "--no-header",
             "-p", "no:cacheprovider", "-p", "no:xdist", "--tb=line"],
            cwd=tmp, env=env, capture_output=True, text=True, timeout=300, check=False,
        )
    output = result.stdout + result.stderr
    passed = re.search(r"(\d+) passed", output)
    failed = re.search(r"(\d+) failed", output)
    return int(passed.group(1)) if passed else 0, int(failed.group(1)) if failed else 0, output


FRA_TARGETS = ("fra_1", "fra_49", "fra_64", "fra_159", "fra_179")


@pytest.mark.parametrize("card", FRA_TARGETS)
@pytest.mark.parametrize("variant", ["offer_then_reject", "card_then_face", "card_then_face_all_sources",
                                     "exiled_source_first",
                                     "consumed_face_first"])
def test_suite_accepts_every_valid_presentation(card: str, variant: str) -> None:
    suffix = {"offer_then_reject": OFFER_THEN_REJECT, "card_then_face": CARD_THEN_FACE,
              "card_then_face_all_sources": CARD_THEN_FACE_ALL_SOURCES,
              "consumed_face_first": CONSUMED_FACE_FIRST,
              "exiled_source_first": EXILED_SOURCE_FIRST}[variant]
    passed, failed, output = run_suite(card, suffix)
    assert passed and not failed, output[-4000:]


def test_hall_suite_accepts_a_copied_halls_removed_ability_rejected() -> None:
    passed, failed, output = run_suite("fra_179", HALL_REMOVED_ABILITY_FIRST)
    assert passed and not failed, output[-4000:]


@pytest.mark.parametrize("card,suffix", [
    ("fra_1", OFFER_THEN_REJECT + CASTS_ANYTHING_IN_EXILE),
    ("fra_49", PREPARED_AFTER_CASTING),
    ("fra_64", LOYALTY_EVERY_TIME),
])
def test_suite_catches_an_illegal_action_taking_effect(card: str, suffix: str) -> None:
    passed, failed, output = run_suite(card, suffix)
    assert failed, output[-4000:]
