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
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.stack import resolve_top_of_stack
from engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from test_utils import TestSetupError as _CastError
from test_utils import cast_spell, create_game, set_board_state


def _bear(p, name="Bear", toughness=2):
    return Creature(name=name, base_power=2, base_toughness=toughness,
                    owner=p, controller=p)


def _cast_no_resolve(game, player_index, card, targets):
    """Cast *card* choosing *targets* but leave it on the stack (no resolve).

    Mirrors ``test_utils.cast_spell`` but stops before resolution so a test can
    mutate the target and then resolve manually to exercise resolution-time
    target revalidation.
    """
    player = game.players[player_index]
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    prefs = tuple(
        Decision.obj(instance=game.refs.instance_id(t, Zone.BATTLEFIELD.value))
        for t in targets
    )
    player.start_intent("cast", Intent(
        pattern=GameRef(card=frozenset({("name", card.name)})),
        preferences=prefs,
    ))
    try:
        engine_cast_spell(game, player, card)
    finally:
        player.end_intent("cast")


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

    def test_target_removed_from_combat_before_resolution_does_nothing(self):
        """Resolution-time revalidation (rule 608.2b): a creature that leaves
        combat before Condemn resolves is no longer a legal 'attacking creature'
        target, so Condemn does nothing — it stays on the battlefield and its
        controller gains no life."""
        game, p1, p2, condemn, attacker = self._setup(toughness=5)
        _cast_no_resolve(game, 0, condemn, [attacker])
        # The attacker is removed from combat while Condemn is on the stack.
        attacker.is_attacking = False
        resolve_top_of_stack(game)
        assert game.get_battlefield(p2).contains(attacker)   # not bottomed
        assert not p2.zones[Zone.LIBRARY].contains(attacker)
        assert p2.life == 20                                  # no life gained

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
