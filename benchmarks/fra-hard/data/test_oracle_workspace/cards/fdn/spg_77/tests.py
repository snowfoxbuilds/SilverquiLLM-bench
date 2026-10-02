"""Reference test for SPG 77 — Embercleave.

Legendary Equipment with Flash. Costs {1} less per attacking creature you
control. ETB: attach to a creature you control (Player Query). Static:
equipped creature gets +1/+1 and has double strike and trample. See
fdn_129/tests.py for the canonical Equipment test shape.
"""

from __future__ import annotations

from cards.fdn.spg_77.card_impl import Embercleave
from engine.card import Creature, Equipment
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


def _bear(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


class TestEmbercleaveProperties:
    def test_static_data(self):
        cleave = Embercleave(owner=None)
        assert cleave.name == "Embercleave"
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
        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        cleave = Embercleave(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, cleave])
        inst = game.refs.instance_id(bear, Zone.BATTLEFIELD.value)
        p1.start_intent("cleave", Intent(
            pattern=GameRef(card=frozenset({("name", "Embercleave")})),
            preferences=(Decision.obj(instance=inst),),
        ))
        cleave.on_resolve(game)
        p1.end_intent("cleave")
        game.effect_manager.apply_all(game)
        assert cleave.attached_to is bear
        assert bear.power == 3
