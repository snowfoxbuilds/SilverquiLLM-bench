"""Reference test for FDN 86 — Fiery Annihilation.

A spell with a **dependent** optional target: "Exile up to one target Equipment
attached to *that creature*" — the Equipment target is legal only when attached
to the creature chosen for the first (required) target of the *same* cast.
Equipment on a different creature is never offered, the relationship is
revalidated at resolution, and the two targets resolve independently when only
one remains legal.
"""

from __future__ import annotations

from cards.fdn.fdn_86.card_impl import FieryAnnihilation
from engine.card import Creature, Equipment
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.stack import resolve_top_of_stack
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


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
    player.start_intent("cast", Intent(
        pattern=GameRef(card=frozenset({("name", card.name)})),
        preferences=prefs,
    ))
    try:
        engine_cast_spell(game, player, card)
    finally:
        player.end_intent("cast")


class TestFieryAnnihilationTargets:
    def _board(self):
        game = create_game()
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

    def test_dependent_filter_only_accepts_equipment_on_chosen_creature(self):
        """The second query's option set excludes Equipment on the *other*
        creature — only Equipment attached to the chosen creature is legal."""
        game, p1, p2, spell, c1, c2, eq1, eq2 = self._board()
        specs = spell.get_targets(game)
        equip_filter = specs[1].filter_fn
        # Chosen creature is c1: only eq1 (attached to c1) qualifies.
        assert equip_filter(eq1, [c1]) is True
        assert equip_filter(eq2, [c1]) is False
        # Chosen creature is c2: now only eq2 qualifies.
        assert equip_filter(eq2, [c2]) is True
        assert equip_filter(eq1, [c2]) is False

    def test_other_creatures_equipment_not_selected(self):
        """Preferring the other creature's Equipment cannot exile it — it is
        never a legal option, so nothing is exiled beyond the damage."""
        game, p1, p2, spell, c1, c2, eq1, eq2 = self._board()
        # Target c1 but try to pick eq2 (attached to c2): not offered → declined.
        _cast_no_resolve(game, p1, spell, [c1, eq2])
        resolve_top_of_stack(game)
        assert game.get_battlefield(p2).contains(eq2)   # not exiled
        assert not game.get_exile(p2).contains(eq2)
        assert c1.damage_marked == 5

    def test_chosen_equipment_exiled(self):
        game, p1, p2, spell, c1, c2, eq1, eq2 = self._board()
        _cast_no_resolve(game, p1, spell, [c1, eq1])
        resolve_top_of_stack(game)
        assert game.get_exile(p2).contains(eq1)         # exiled
        assert c1.damage_marked == 5

    def test_chosen_equipment_detached_before_resolution_not_exiled(self):
        """The chosen Equipment moves off the creature before resolution: it is
        no longer legal and is not exiled, but the creature target still takes 5
        (independent resolution)."""
        game, p1, p2, spell, c1, c2, eq1, eq2 = self._board()
        _cast_no_resolve(game, p1, spell, [c1, eq1])
        eq1.attached_to = None                          # detached in response
        resolve_top_of_stack(game)
        assert game.get_battlefield(p2).contains(eq1)   # not exiled
        assert not game.get_exile(p2).contains(eq1)
        assert c1.damage_marked == 5                    # creature still resolves

    def test_chosen_equipment_reattached_before_resolution_not_exiled(self):
        """The chosen Equipment reattaches to a different creature before
        resolution: no longer attached to *that creature*, so not exiled."""
        game, p1, p2, spell, c1, c2, eq1, eq2 = self._board()
        _cast_no_resolve(game, p1, spell, [c1, eq1])
        eq1.attached_to = c2                            # reattached elsewhere
        resolve_top_of_stack(game)
        assert game.get_battlefield(p2).contains(eq1)   # not exiled
        assert c1.damage_marked == 5

    def test_zero_equipment_remains_legal(self):
        """No Equipment on the board: the spell is castable and exiles nothing,
        only dealing damage (the optional target is skipped)."""
        game = create_game()
        p1, p2 = game.players
        c1 = _creature(p2, "Lonely Creature")
        spell = FieryAnnihilation(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.RED: 1, ManaType.COLORLESS: 2})
        set_board_state(game, 1, battlefield=[c1])
        _cast_no_resolve(game, p1, spell, [c1])
        resolve_top_of_stack(game)
        assert c1.damage_marked == 5
