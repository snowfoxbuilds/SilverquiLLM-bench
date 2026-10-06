"""Reference test for SPG 77 — Embercleave.

Legendary Equipment with Flash. Costs {1} less per attacking creature you
control. ETB: attach to a creature you control (Player Query). Static:
equipped creature gets +1/+1 and has double strike and trample. See
fdn_129/tests.py for the canonical Equipment test shape.
"""

from __future__ import annotations

from cards.fdn.spg_77.card_impl import Embercleave
from engine.card import Creature, Equipment, printed_class
from engine.decisions import Decision, GameRef
from test_utils import Intent
from engine.types import Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


def _bear(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


class TestEmbercleaveProperties:
    def test_static_data(self):
        cleave = Embercleave(owner=None)
        assert printed_class(cleave) is Embercleave
        assert cleave.mana_cost == ManaCost.parse("{4}{R}{R}")
        assert cleave.equip_cost == ManaCost.parse("{3}")
        assert Supertype.LEGENDARY in cleave.supertypes
        assert Keyword.FLASH in cleave.keywords
        assert isinstance(cleave, Equipment) and cleave.is_equipment is True


class TestEmbercleaveBehaviour:
    def test_cost_reduction_per_attacking_creature(self):
        game = create_game()
        p1 = game.players[0]
        a, b = _bear(p1, "A"), _bear(p1, "B")
        a.is_attacking = True
        b.is_attacking = True
        cleave = Embercleave(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[a, b])
        assert cleave.cost_reduction(game) == 2

    def test_static_buff(self):
        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        cleave = Embercleave(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, cleave])
        cleave.equip(bear, game)
        assert (bear.power, bear.toughness) == (3, 3)
        assert Keyword.DOUBLE_STRIKE in bear.keywords
        assert Keyword.TRAMPLE in bear.keywords

    def test_etb_attaches_to_chosen_creature(self):
        """Its enters ability is a triggered ability: Embercleave enters, the
        trigger goes on the stack choosing the creature (rule 603.3d), and
        attaches it as it resolves."""
        from engine.stack import resolve_top_of_stack
        from engine.state_based_actions import resolve_state_based_actions
        from engine.zones import move_to_zone

        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        cleave = Embercleave(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear], hand=[cleave])
        inst = game.refs.instance_id(bear, Zone.BATTLEFIELD.value)
        p1.start_intent("cleave", Intent(pattern=GameRef(), preferences=(Decision.obj(instance=inst),)))
        try:
            move_to_zone(game, cleave, Zone.HAND, Zone.BATTLEFIELD)
            resolve_state_based_actions(game)
        finally:
            p1.end_intent("cleave")
        assert cleave.attached_to is None  # not yet: the trigger is on the stack
        (trigger,) = game.stack.objects()
        assert trigger.targets == [bear]
        resolve_top_of_stack(game)
        game.effect_manager.apply_all(game)
        assert cleave.attached_to is bear
        assert bear.power == 3