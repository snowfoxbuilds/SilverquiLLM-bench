"""Known-Best checks moved out of fdn_86's FDN Audited Tests: no FDN card moves, unattaches or flickers an Equipment at instant speed,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_86.card_impl import FieryAnnihilation
from engine.card import Creature, Equipment, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.stack import resolve_top_of_stack
from engine.types import ManaCost, ManaType, Zone
from engine.zones import move_to_zone
from test_utils import Intent, set_board_state
from test_utils import create_game as legacy_game

_SPELL_MANA = {ManaType.RED: 1, ManaType.COLORLESS: 2}


# Legacy setup for the attachment-change tests below.
def _creature(p, name, toughness=6):
    return Creature(name=name, base_power=2, base_toughness=toughness, owner=p, controller=p)


def _equipment(p, name):
    eq = Equipment(name=name, owner=p, controller=p, equip_cost=ManaCost.parse("{1}"))
    return eq


def _pref(game, obj):
    return Decision.obj(instance=game.refs.instance_id(obj, Zone.BATTLEFIELD.value))


def _cast_no_resolve(game, player, card, targets):
    """Cast *card* choosing *targets* via an Intent, WITHOUT resolving — leaves
    the spell on the stack so the test can alter the board before resolution."""
    prefs = tuple(_pref(game, t) for t in targets)
    player.start_intent(
        "cast",
        Intent(
            pattern=GameRef(card=frozenset({("printed", printed_class(card))})),
            preferences=prefs,
        ),
    )
    try:
        engine_cast_spell(game, player, card)
    finally:
        player.end_intent("cast")


class TestFieryAnnihilationAttachmentChanges:
    """No card moves an Equipment at instant speed, so these tests still
    change the attachment, or the Equipment's zone, directly."""

    def _board(self):
        game = legacy_game()
        p1, p2 = game.players
        c1 = _creature(p2, "Creature One")
        c2 = _creature(p2, "Creature Two")
        eq1 = _equipment(p2, "Sword One")
        eq2 = _equipment(p2, "Sword Two")
        eq1.attached_to = c1
        eq2.attached_to = c2
        spell = FieryAnnihilation(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.RED: 1, ManaType.COLORLESS: 2})
        set_board_state(game, 1, battlefield=[c1, c2, eq1, eq2])
        return game, p1, p2, spell, c1, c2, eq1, eq2

    def test_chosen_equipment_detached_before_resolution_not_exiled(self):
        """The chosen Equipment moves off the creature before resolution: it is
        no longer legal and is not exiled, but the creature target still takes 5
        (independent resolution)."""
        game, p1, p2, spell, c1, _c2, eq1, _eq2 = self._board()
        _cast_no_resolve(game, p1, spell, [c1, eq1])
        eq1.attached_to = None  # detached in response
        resolve_top_of_stack(game)
        assert game.get_battlefield(p2).contains(eq1)  # not exiled
        assert not game.get_exile(p2).contains(eq1)
        assert c1.damage_marked == 5  # creature still resolves

    def test_chosen_equipment_reattached_before_resolution_not_exiled(self):
        """The chosen Equipment reattaches to a different creature before
        resolution: no longer attached to *that creature*, so not exiled."""
        game, p1, p2, spell, c1, c2, eq1, _eq2 = self._board()
        _cast_no_resolve(game, p1, spell, [c1, eq1])
        eq1.attached_to = c2  # reattached elsewhere
        resolve_top_of_stack(game)
        assert game.get_battlefield(p2).contains(eq1)  # not exiled
        assert c1.damage_marked == 5

    def test_equipment_leaves_and_returns_not_exiled(self):
        """The chosen Equipment leaves the battlefield and returns (a new object
        in the same Python instance), re-attached to the creature. Its predicate
        (attached to that creature) would pass, but the spell's captured
        zone-stint rejects the returned object — it is not exiled. The creature
        target (unchanged stint) still takes 5."""
        game, p1, p2, spell, c1, _c2, eq1, _eq2 = self._board()
        _cast_no_resolve(game, p1, spell, [c1, eq1])
        move_to_zone(game, eq1, Zone.BATTLEFIELD, Zone.EXILE)
        move_to_zone(game, eq1, Zone.EXILE, Zone.BATTLEFIELD)  # new stint
        eq1.attached_to = c1  # predicate would pass
        resolve_top_of_stack(game)
        assert game.get_battlefield(p2).contains(eq1)  # NOT exiled (stint)
        assert not game.get_exile(p2).contains(eq1)
        assert c1.damage_marked == 5  # creature still resolves
