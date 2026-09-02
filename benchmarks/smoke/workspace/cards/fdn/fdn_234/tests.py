"""Reference test for FDN 234 — Vivien Reid.

Demonstrates **Pattern 4 — loyalty ability with targeting** (Phase D) for a
**required** loyalty target with a type/keyword-restricted option set:

* ``−3`` — "Destroy target artifact, enchantment, or creature with flying." The
  ``targeting`` hook offers only permanents matching that filter and returns
  ``None`` (ability cannot be activated, no loyalty spent) when none exist. The
  target is captured at activation, revalidated at resolution, then destroyed.
* ``+1`` (look at top four) and ``−8`` (emblem) are untargeted.

The target is chosen at activation via a Player Query answered by an Intent
(pattern = the walker's name) — never re-selected at resolution.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_234.card_impl import VivienReid
from engine.abilities import AbilityError, clear_loyalty_tracking
from engine.card import Artifact, Creature, Enchantment
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import CardType, Keyword, ManaCost, Phase, Supertype, Zone
from test_utils import (
    activate_loyalty_ability,
    create_game,
    resolve_stack,
    set_board_state,
)


@pytest.fixture(autouse=True)
def _reset_loyalty_tracker():
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


def _flyer(p, name="Flyer"):
    return Creature(
        name=name, base_power=1, base_toughness=1,
        keywords=Keyword.FLYING, owner=p, controller=p,
    )


def _ground(p, name="Groundling"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _artifact(p, name="Trinket"):
    return Artifact(name=name, owner=p, controller=p)


def _enchantment(p, name="Curse"):
    return Enchantment(name=name, owner=p, controller=p)


def _activate_targeting(game, player, walker, index, target):
    player.start_intent("vivien", Intent(
        pattern=GameRef(card=frozenset({("name", walker.name)})),
        preferences=(Decision.obj(instance=target.instance_id),),
    ))
    try:
        activate_loyalty_ability(game, player, walker, index)
    finally:
        player.end_intent("vivien")


def _in_graveyard(game, player, obj):
    return player.zones[Zone.GRAVEYARD].contains(obj)


class TestVivienProperties:
    def test_static_data(self):
        vivien = VivienReid(owner=None)
        assert vivien.name == "Vivien Reid"
        assert vivien.mana_cost == ManaCost.parse("{3}{G}{G}")
        assert vivien.starting_loyalty == 5
        assert Supertype.LEGENDARY in vivien.supertypes
        assert "Vivien" in vivien.subtypes

    def test_only_minus_three_is_targeted(self):
        vivien = VivienReid(owner=None)
        abilities = vivien.get_loyalty_abilities()
        assert len(abilities) == 3
        assert abilities[0].targeting is None       # +1
        assert abilities[1].targeting is not None   # −3
        assert abilities[2].targeting is None       # −8
        assert [a.loyalty_cost for a in abilities] == [1, -3, -8]


class TestVivienMinusThree:
    def _setup(self, extra=None):
        game = create_game()
        p1, p2 = game.players
        vivien = VivienReid(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[vivien])
        if extra is not None:
            set_board_state(game, 1, battlefield=extra)
        game.phase = Phase.PRECOMBAT_MAIN
        return game, p1, p2, vivien

    def test_destroys_flying_creature(self):
        flyer = None
        game, p1, p2, vivien = self._setup()
        flyer = _flyer(p2, "Their Flyer")
        set_board_state(game, 1, battlefield=[flyer])
        _activate_targeting(game, p1, vivien, 1, flyer)
        assert vivien.loyalty == 2                    # 5 − 3
        top = game.stack.peek()
        assert top.targets == [flyer]
        resolve_stack(game)
        assert _in_graveyard(game, p2, flyer)
        assert not game.get_battlefield(p2).contains(flyer)

    def test_destroys_artifact(self):
        game, p1, p2, vivien = self._setup()
        trinket = _artifact(p2, "Their Trinket")
        set_board_state(game, 1, battlefield=[trinket])
        _activate_targeting(game, p1, vivien, 1, trinket)
        resolve_stack(game)
        assert _in_graveyard(game, p2, trinket)

    def test_destroys_enchantment(self):
        game, p1, p2, vivien = self._setup()
        curse = _enchantment(p2, "Their Curse")
        set_board_state(game, 1, battlefield=[curse])
        _activate_targeting(game, p1, vivien, 1, curse)
        resolve_stack(game)
        assert _in_graveyard(game, p2, curse)

    def test_ground_creature_is_not_a_legal_target(self):
        """A non-flying creature (and nothing else legal) → targeting returns
        None → ability cannot be activated, no loyalty spent."""
        game, p1, p2, vivien = self._setup()
        set_board_state(game, 1, battlefield=[_ground(p2, "Their Groundling")])
        game.phase = Phase.PRECOMBAT_MAIN
        with pytest.raises(AbilityError):
            activate_loyalty_ability(game, p1, vivien, 1)
        assert vivien.loyalty == 5                     # unchanged

    def test_no_legal_target_rejected_before_cost(self):
        game, p1, p2, vivien = self._setup()   # nothing but the walker
        with pytest.raises(AbilityError):
            activate_loyalty_ability(game, p1, vivien, 1)
        assert vivien.loyalty == 5


class TestVivienUntargeted:
    def test_plus_one_activates_and_resolves(self):
        game = create_game()
        p1, p2 = game.players
        vivien = VivienReid(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[vivien])
        game.phase = Phase.PRECOMBAT_MAIN
        activate_loyalty_ability(game, p1, vivien, 0)   # +1, untargeted
        assert vivien.loyalty == 6
        resolve_stack(game)                             # empty library → no-op
