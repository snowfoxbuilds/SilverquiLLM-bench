"""Reference test for FDN 95 — Sower of Chaos.

Canonical exemplar for a **targeted activated ability** on a creature (Phase D):
the target is chosen at activation via a Player Query (answered by an Intent),
captured on the stack object, revalidated at resolution, and applied as an
until-end-of-turn continuous effect. Other targeted-activated-ability card tests
follow this shape.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_95.card_impl import SowerOfChaos
from engine.abilities import AbilityError
from engine.card import Creature
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from engine.zones import move_to_zone
from test_utils import activate_card_ability, create_game, resolve_stack, set_board_state


def _bear(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _activate_targeting(game, player, source, target):
    """Drive Sower's ability through the real activate → stack → resolve path,
    targeting *target* (chosen at activation via an Intent on *player*)."""
    inst = game.refs.instance_id(target, Zone.BATTLEFIELD.value)
    player.start_intent("sower", Intent(
        pattern=GameRef(card=frozenset({("name", source.name)})),
        preferences=(Decision.obj(instance=inst),),
    ))
    try:
        activate_card_ability(game, player, source)
    finally:
        player.end_intent("sower")


class TestSowerOfChaosProperties:
    def test_static_data(self):
        sower = SowerOfChaos(owner=None)
        assert sower.name == "Sower of Chaos"
        assert sower.mana_cost == ManaCost.parse("{3}{R}")
        assert (sower.base_power, sower.base_toughness) == (4, 3)
        assert "Devil" in sower.subtypes

    def test_has_one_activated_ability(self):
        sower = SowerOfChaos(owner=None)
        abilities = sower.get_activated_abilities()
        assert len(abilities) == 1
        assert abilities[0].targeting is not None


class TestSowerOfChaosAbility:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        sower = SowerOfChaos(owner=p1, controller=p1)
        their_bear = _bear(p2, "Their Bear")
        set_board_state(game, 0, battlefield=[sower], mana={ManaType.RED: 3})
        set_board_state(game, 1, battlefield=[their_bear])
        game.phase = Phase.PRECOMBAT_MAIN
        return game, p1, p2, sower, their_bear

    def test_target_cant_block_after_resolution(self):
        game, p1, p2, sower, their_bear = self._setup()
        _activate_targeting(game, p1, sower, their_bear)
        assert not game.stack.is_empty()          # pushed to the stack
        resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert their_bear._cant_block is True

    def test_cost_is_paid(self):
        game, p1, p2, sower, their_bear = self._setup()
        _activate_targeting(game, p1, sower, their_bear)
        assert p1.mana_pool.total() == 0          # {2}{R} paid

    def test_targets_creature_captured_on_stack(self):
        game, p1, p2, sower, their_bear = self._setup()
        _activate_targeting(game, p1, sower, their_bear)
        top = game.stack.peek()
        assert top.targets == [their_bear]
        assert top.controller is p1

    def test_source_off_battlefield_rejected_before_cost(self):
        """Legality invariant (can_activate): activating while the source is not
        on the battlefield is rejected before any cost is paid."""
        game = create_game()
        p1 = game.players[0]
        sower = SowerOfChaos(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[sower], mana={ManaType.RED: 3})
        move_to_zone(game, sower, Zone.BATTLEFIELD, Zone.GRAVEYARD)  # source leaves
        game.phase = Phase.PRECOMBAT_MAIN
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, sower)
        assert p1.mana_pool.total() == 3            # no mana spent

    def test_can_target_any_creature_including_own(self):
        game, p1, p2, sower, their_bear = self._setup()
        # Sower can target itself (any creature is legal).
        _activate_targeting(game, p1, sower, sower)
        resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert sower._cant_block is True
