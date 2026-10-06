"""Known-Best checks moved out of fdn_126's FDN Audited Tests: #169: the only artifact with counters is Ravenous Amulet, which pays its sacrifice on resolution, and Fake Your Own Death leaves a visible cleanup trigger and fires again,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_126.card_impl import (
    ZimoneParadoxSculptor,
    ZimoneParadoxSculptorAbility1,
    ZimoneParadoxSculptorAbility2,
)
from engine.card import Artifact, Creature
from engine.decisions import Decision, GameRef
from engine.game import add_counter
from engine.types import ManaType, Zone
from engine.zones import move_to_zone
from test_utils import (
    Intent,
    activate_card_ability,
    create_game,
    resolve_stack,
    set_board_state,
)

TRIGGER, DOUBLE = ZimoneParadoxSculptorAbility1, ZimoneParadoxSculptorAbility2

def _creature(p, name):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _named(objects, name):
    (match,) = [obj for obj in objects if obj.name == name]
    return match


def _pref(game, obj):
    return Decision.obj(instance=game.refs.instance_id(obj, Zone.BATTLEFIELD.value))


def _activate_double(game, player, zimone, targets):
    prefs = tuple(_pref(game, t) for t in targets)
    player.start_intent(
        "z",
        Intent(
            pattern=GameRef(card=frozenset({("printed", ZimoneParadoxSculptor)})),
            preferences=prefs,
        ),
    )
    try:
        activate_card_ability(game, player, zimone)
    finally:
        player.end_intent("z")


class TestZimoneDoubleAbility:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        z = ZimoneParadoxSculptor(owner=p1, controller=p1)
        a = _creature(p1, "Ally A")
        b = _creature(p1, "Ally B")
        set_board_state(game, 0, battlefield=[z, a, b], mana={ManaType.GREEN: 1, ManaType.BLUE: 1})
        add_counter(game, a, "+1/+1", 2)
        add_counter(game, b, "+1/+1", 3)
        return game, p1, p2, z, a, b

    def test_can_target_artifact_you_control(self):
        game, p1, _p2, z, _a, _b = self._setup()
        art = Artifact(name="Trinket", owner=p1, controller=p1)
        game.get_battlefield(p1).add(art)
        art.instance_id = game.refs.instance_id(art, Zone.BATTLEFIELD.value)
        add_counter(game, art, "charge", 2)
        _activate_double(game, p1, z, [art])
        resolve_stack(game)
        assert art.counters.get("charge") == 4

    def test_leave_and_return_target_rejected(self):
        """A target that leaves and returns is a new object (new stint) and is
        rejected by stint validation — its counters are not doubled."""
        game, p1, _p2, z, a, _b = self._setup()
        _activate_double(game, p1, z, [a])
        move_to_zone(game, a, Zone.BATTLEFIELD, Zone.EXILE)
        exiled = _named(p1.zones[Zone.EXILE].get_all(), "Ally A")
        move_to_zone(game, exiled, Zone.EXILE, Zone.BATTLEFIELD)
        returned = _named(game.get_battlefield(p1).get_all(), "Ally A")
        # Whatever counters survive the zone change (CR 400.7), the returned
        # object holds some now; doubling would change them.
        add_counter(game, returned, "+1/+1", 3)
        before = returned.plus_one_counters
        resolve_stack(game)
        # The returned object is p1-controlled and a creature, so only stint
        # validation can reject it: its counters are left undoubled.
        assert returned.plus_one_counters == before
