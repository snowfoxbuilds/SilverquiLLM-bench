"""Reference test for FDN 129 — Leyline Axe.

Canonical exemplar for the Equipment primitive: properties, the attach →
buff → detach → un-buff lifecycle, SBA unattach when the creature leaves, and
the equip ability's option-set invariant (equip only targets a creature you
control). Other equipment tests follow this shape.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_129.card_impl import LeylineAxe
from engine.abilities import AbilityError
from engine.card import Creature, Equipment
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.state_based_actions import check_state_based_actions
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone
from engine.zones import move_to_zone
from test_utils import activate_card_ability, create_game, resolve_stack, set_board_state


def _bear(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


class TestLeylineAxeProperties:
    def test_static_data(self):
        axe = LeylineAxe(owner=None)
        assert axe.name == "Leyline Axe"
        assert axe.mana_cost == ManaCost.parse("{4}")
        assert axe.equip_cost == ManaCost.parse("{3}")

    def test_is_equipment(self):
        axe = LeylineAxe(owner=None)
        assert isinstance(axe, Equipment)
        assert axe.is_equipment is True
        assert "Equipment" in axe.subtypes


class TestLeylineAxeLifecycle:
    def test_attach_buffs_then_detach_removes(self):
        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        axe = LeylineAxe(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, axe])

        axe.equip(bear, game)
        assert axe.attached_to is bear
        assert (bear.power, bear.toughness) == (3, 3)
        assert Keyword.DOUBLE_STRIKE in bear.keywords
        assert Keyword.TRAMPLE in bear.keywords

        axe.detach(game)
        assert axe.attached_to is None
        assert (bear.power, bear.toughness) == (2, 2)
        assert Keyword.DOUBLE_STRIKE not in bear.keywords

    def test_buff_moves_when_re_equipped(self):
        game = create_game()
        p1 = game.players[0]
        a, b = _bear(p1, "A"), _bear(p1, "B")
        axe = LeylineAxe(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[a, b, axe])
        axe.equip(a, game)
        assert (a.power, b.power) == (3, 2)
        axe.equip(b, game)  # moves off A onto B
        assert (a.power, b.power) == (2, 3)

    def test_sba_unattaches_when_creature_dies(self):
        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        axe = LeylineAxe(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, axe])
        axe.equip(bear, game)
        move_to_zone(game, bear, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        check_state_based_actions(game)
        assert axe.attached_to is None


class TestLeylineAxeEquipAbility:
    """The equip ability driven through the real activate → stack → resolve
    path (targets chosen at activation, revalidated at resolution)."""

    def test_equip_only_at_sorcery_speed(self):
        # Direct cost-timing check: outside a main phase the equip cost is
        # unpayable, so activation cannot proceed (and spends nothing).
        game = create_game()
        p1 = game.players[0]
        axe = LeylineAxe(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[axe], mana={ManaType.COLORLESS: 3})
        ability = axe.get_activated_abilities()[0]
        game.phase = Phase.COMBAT
        assert ability.cost(game, axe) is False

    def test_equip_no_legal_target_spends_no_mana(self):
        """Zero creatures you control: activation is rejected before cost, so no
        mana is spent and nothing is put on the stack."""
        game = create_game()
        p1, p2 = game.players
        theirs = _bear(p2, "Theirs")  # opponent's creature is not a legal target
        axe = LeylineAxe(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[axe], mana={ManaType.COLORLESS: 3})
        set_board_state(game, 1, battlefield=[theirs])
        game.phase = Phase.PRECOMBAT_MAIN
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, axe)
        assert p1.mana_pool.total() == 3
        assert axe.attached_to is None
        assert game.stack.is_empty()

    def test_equip_ability_attaches_to_chosen_creature(self):
        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        axe = LeylineAxe(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, axe], mana={ManaType.COLORLESS: 3})
        game.phase = Phase.PRECOMBAT_MAIN
        inst = game.refs.instance_id(bear, Zone.BATTLEFIELD.value)
        p1.start_intent("equip", Intent(
            pattern=GameRef(card=frozenset({("name", "Leyline Axe")})),
            preferences=(Decision.obj(instance=inst),),
        ))
        activate_card_ability(game, p1, axe)  # chooses target now, pays {3}
        p1.end_intent("equip")
        assert axe.attached_to is None          # chosen, but not yet resolved
        assert p1.mana_pool.total() == 0        # cost paid at activation
        resolve_stack(game)
        assert axe.attached_to is bear
        assert bear.power == 3
