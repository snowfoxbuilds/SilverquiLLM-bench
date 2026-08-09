"""Reference test for SPG 74 — Condemn.

Pattern 1 — targeted spell. Condemn requires a real ``TargetRequirement``
whose legal set is *attacking creatures* (the engine's ``is_attacking`` combat
flag). The target is chosen at cast intent-style via ``cast_spell(targets=...)``,
revalidated at resolution, put on the bottom of its owner's library, and its
controller gains life equal to its toughness.
"""

from __future__ import annotations

import pytest

from cards.fdn.spg_74.card_impl import Condemn
from engine.card import Creature
from engine.types import ManaCost, ManaType, TargetRequirement, Zone
from test_utils import TestSetupError as _CastError
from test_utils import cast_spell, create_game, set_board_state


def _bear(p, name="Bear", toughness=2):
    return Creature(name=name, base_power=2, base_toughness=toughness,
                    owner=p, controller=p)


class TestCondemnProperties:
    def test_static_data(self):
        c = Condemn(owner=None)
        assert c.name == "Condemn"
        assert c.mana_cost == ManaCost.parse("{W}")

    def test_get_targets_requirement_filters_attackers(self):
        game = create_game()
        p2 = game.players[1]
        attacker = _bear(p2, "Attacker")
        idle = _bear(p2, "Idle")
        attacker.is_attacking = True
        spec = Condemn(owner=None).get_targets(game)[0]
        assert isinstance(spec, TargetRequirement)
        assert spec.zone == Zone.BATTLEFIELD
        assert spec.optional is False
        assert spec.filter_fn(attacker) is True   # attacking creature: legal
        assert spec.filter_fn(idle) is False        # not attacking: illegal


class TestCondemnResolve:
    def _setup(self, toughness=2):
        game = create_game()
        p1, p2 = game.players
        condemn = Condemn(owner=p1, controller=p1)
        attacker = _bear(p2, "Their Attacker", toughness=toughness)
        set_board_state(game, 0, hand=[condemn], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[attacker], life=20)
        attacker.is_attacking = True
        return game, p1, p2, condemn, attacker

    def test_puts_attacker_on_bottom_of_library(self):
        game, p1, p2, condemn, attacker = self._setup()
        cast_spell(game, 0, "Condemn", targets=[attacker])
        assert not game.get_battlefield(p2).contains(attacker)
        library = p2.zones[Zone.LIBRARY]
        assert library.contains(attacker)
        # Bottom of library == position 0 of the internal list.
        assert library.get_all()[0] is attacker

    def test_controller_gains_life_equal_to_toughness(self):
        game, p1, p2, condemn, attacker = self._setup(toughness=5)
        cast_spell(game, 0, "Condemn", targets=[attacker])
        assert p2.life == 25  # 20 + toughness 5

    def test_cost_is_paid(self):
        game, p1, p2, condemn, attacker = self._setup()
        cast_spell(game, 0, "Condemn", targets=[attacker])
        assert p1.mana_pool.total() == 0

    def test_no_attacking_creature_makes_spell_uncastable(self):
        """Required target: a non-attacking creature is not a legal target, so
        with no attackers the spell cannot be cast."""
        game = create_game()
        p1, p2 = game.players
        condemn = Condemn(owner=p1, controller=p1)
        idle = _bear(p2, "Idle")  # on battlefield but not attacking
        set_board_state(game, 0, hand=[condemn], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[idle])
        with pytest.raises(_CastError):
            cast_spell(game, 0, "Condemn")
