"""Reference test for FDN 31 — Bigfin Bouncer.

Pattern 1 — targeted ETB on a creature spell. The bounce target is a real
``TargetRequirement`` (creature an opponent controls) chosen at cast via an
Intent, captured on the stack, revalidated at resolution, and applied before
the creature itself enters. Targeting is driven the intent-style way through
``cast_spell(targets=...)`` — never a test-only resolve backdoor.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_31.card_impl import BigfinBouncer
from engine.card import Creature
from engine.types import ManaCost, ManaType, TargetRequirement, Zone
from test_utils import TestSetupError as _CastError
from test_utils import cast_spell, create_game, set_board_state


def _bear(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


class TestBigfinBouncerProperties:
    def test_static_data(self):
        c = BigfinBouncer(owner=None)
        assert c.name == "Bigfin Bouncer"
        assert c.mana_cost == ManaCost.parse("{3}{U}")
        assert (c.base_power, c.base_toughness) == (3, 2)
        assert {"Shark", "Pirate"} <= c.subtypes

    def test_get_targets_is_a_requirement_not_objects(self):
        c = BigfinBouncer(owner=None, controller=None)
        specs = c.get_targets(create_game())
        assert len(specs) == 1
        assert isinstance(specs[0], TargetRequirement)
        assert specs[0].zone == Zone.BATTLEFIELD
        assert specs[0].optional is False


class TestBigfinBouncerBounce:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        bigfin = BigfinBouncer(owner=p1, controller=p1)
        their_bear = _bear(p2, "Their Bear")
        set_board_state(game, 0, hand=[bigfin], mana={ManaType.BLUE: 4})
        set_board_state(game, 1, battlefield=[their_bear])
        return game, p1, p2, bigfin, their_bear

    def test_bounces_target_to_owner_hand(self):
        game, p1, p2, bigfin, their_bear = self._setup()
        cast_spell(game, 0, "Bigfin Bouncer", targets=[their_bear])
        # Target left the battlefield and returned to its owner's hand.
        assert not game.get_battlefield(p2).contains(their_bear)
        assert game.get_hand(p2).contains(their_bear)
        # Bigfin itself entered the caster's battlefield afterward.
        assert game.get_battlefield(p1).contains(bigfin)

    def test_cost_is_paid(self):
        game, p1, p2, bigfin, their_bear = self._setup()
        cast_spell(game, 0, "Bigfin Bouncer", targets=[their_bear])
        assert p1.mana_pool.total() == 0

    def test_filter_targets_only_opponent_creatures(self):
        """Legality invariant: the filter accepts an opponent's creature and
        rejects one the caster controls."""
        game, p1, p2, bigfin, their_bear = self._setup()
        my_bear = _bear(p1, "My Bear")
        set_board_state(game, 0, battlefield=[my_bear], hand=[bigfin],
                        mana={ManaType.BLUE: 4})
        spec = bigfin.get_targets(game)[0]
        assert spec.filter_fn(their_bear) is True
        assert spec.filter_fn(my_bear) is False

    def test_no_legal_target_makes_spell_uncastable(self):
        """Required target with no opponent creature → rejected at cast."""
        game = create_game()
        p1, p2 = game.players
        bigfin = BigfinBouncer(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[bigfin], mana={ManaType.BLUE: 4})
        with pytest.raises(_CastError):
            cast_spell(game, 0, "Bigfin Bouncer")
