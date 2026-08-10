"""Reference test for FDN 62 — Hungry Ghoul.

The "Sacrifice another creature" cost is chosen when the cost is paid, via a
Player Query answered by an Intent (not a dead ``_sacrifice_target`` backdoor).
This is the pattern for a non-mana cost that names a permanent.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_62.card_impl import HungryGhoul
from engine.abilities import AbilityError
from engine.card import Creature
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import activate_card_ability, create_game, resolve_stack, set_board_state


def _bear(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _activate_sacrificing(game, player, ghoul, sac_creature):
    """Activate Hungry Ghoul, choosing *sac_creature* as the sacrifice via an
    Intent that answers the cost's 'choose another creature' Player Query."""
    inst = game.refs.instance_id(sac_creature, Zone.BATTLEFIELD.value)
    player.start_intent("ghoul", Intent(
        pattern=GameRef(card=frozenset({("name", "Hungry Ghoul")})),
        preferences=(Decision.obj(instance=inst),),
    ))
    try:
        activate_card_ability(game, player, ghoul)
    finally:
        player.end_intent("ghoul")


class TestHungryGhoulProperties:
    def test_static_data(self):
        ghoul = HungryGhoul(owner=None)
        assert ghoul.name == "Hungry Ghoul"
        assert ghoul.mana_cost == ManaCost.parse("{1}{B}")
        assert (ghoul.base_power, ghoul.base_toughness) == (2, 2)


class TestHungryGhoulSacrifice:
    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        ghoul = HungryGhoul(owner=p1, controller=p1)
        fodder = _bear(p1, "Fodder")
        set_board_state(game, 0, battlefield=[ghoul, fodder],
                        mana={ManaType.BLACK: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        return game, p1, ghoul, fodder

    def test_sacrifice_pays_cost_and_adds_counter(self):
        game, p1, ghoul, fodder = self._setup()
        _activate_sacrificing(game, p1, ghoul, fodder)
        assert not game.stack.is_empty()               # ability on the stack
        assert not game.get_battlefield(p1).contains(fodder)   # fodder sacrificed
        assert p1.mana_pool.total() == 0               # {1} paid
        resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert ghoul.plus_one_counters == 1            # +1/+1 counter added

    def test_no_other_creature_cannot_pay(self):
        """With no *other* creature to sacrifice, the cost cannot be paid and the
        activation is rejected (Ghoul cannot sacrifice itself)."""
        game = create_game()
        p1 = game.players[0]
        ghoul = HungryGhoul(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ghoul], mana={ManaType.BLACK: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, ghoul)
        assert p1.mana_pool.total() == 1               # no mana spent
        assert game.get_battlefield(p1).contains(ghoul)

    def test_opponent_creature_not_a_valid_sacrifice(self):
        """The sacrifice must be a creature *you* control — an opponent's
        creature is not in the option set, so with only that creature the cost
        cannot be paid."""
        game = create_game()
        p1, p2 = game.players
        ghoul = HungryGhoul(owner=p1, controller=p1)
        theirs = _bear(p2, "Theirs")
        set_board_state(game, 0, battlefield=[ghoul], mana={ManaType.BLACK: 1})
        set_board_state(game, 1, battlefield=[theirs])
        game.phase = Phase.PRECOMBAT_MAIN
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, ghoul)
        assert p1.mana_pool.total() == 1
        assert game.get_battlefield(p2).contains(theirs)   # not sacrificed
