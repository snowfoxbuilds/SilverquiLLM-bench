"""Reference test for FDN 189 — Axgard Cavalry.

Demonstrates a **targeted activated ability** (Phase D pattern 2) with a
``{T}`` cost and an until-end-of-turn keyword grant. The target creature is
chosen at activation via a Player Query (answered by an Intent), captured on
the stack, and granted haste through an until-EOT continuous effect that is
re-applied on every ``apply_all()`` pass.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_189.card_impl import AxgardCavalry
from engine.abilities import AbilityError
from engine.card import Creature
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import activate_card_ability, create_game, resolve_stack, set_board_state


def _bear(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _activate_targeting(game, player, source, target):
    inst = game.refs.instance_id(target, Zone.BATTLEFIELD.value)
    player.start_intent("axgard", Intent(
        pattern=GameRef(card=frozenset({("name", source.name)})),
        preferences=(Decision.obj(instance=inst),),
    ))
    try:
        activate_card_ability(game, player, source)
    finally:
        player.end_intent("axgard")


class TestAxgardCavalryProperties:
    def test_static_data(self):
        card = AxgardCavalry(owner=None)
        assert card.name == "Axgard Cavalry"
        assert card.mana_cost == ManaCost.parse("{1}{R}")
        assert (card.base_power, card.base_toughness) == (2, 2)
        assert {"Dwarf", "Berserker"} <= card.subtypes

    def test_has_one_targeted_ability(self):
        abilities = AxgardCavalry(owner=None).get_activated_abilities()
        assert len(abilities) == 1
        assert abilities[0].targeting is not None
        assert abilities[0].can_activate is not None


class TestAxgardCavalryAbility:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        axgard = AxgardCavalry(owner=p1, controller=p1)
        axgard.summoning_sick = False                 # able to pay {T}
        newcomer = _bear(p1, "Newcomer")
        newcomer.summoning_sick = True                # would-be attacker
        set_board_state(game, 0, battlefield=[axgard, newcomer])
        return game, p1, p2, axgard, newcomer

    def test_target_gains_haste_after_resolution(self):
        game, p1, p2, axgard, newcomer = self._setup()
        assert Keyword.HASTE not in newcomer.keywords
        _activate_targeting(game, p1, axgard, newcomer)
        resolve_stack(game)
        game.effect_manager.apply_all(game)           # re-derive continuous effects
        assert Keyword.HASTE in newcomer.keywords

    def test_tap_cost_is_paid(self):
        game, p1, p2, axgard, newcomer = self._setup()
        _activate_targeting(game, p1, axgard, newcomer)
        assert axgard.is_tapped is True

    def test_target_captured_on_stack(self):
        game, p1, p2, axgard, newcomer = self._setup()
        _activate_targeting(game, p1, axgard, newcomer)
        top = game.stack.peek()
        assert top.targets == [newcomer]

    def test_tapped_source_rejected_before_cost(self):
        """Legality invariant (can_activate): a ``{T}`` ability cannot be
        activated when the source is already tapped — rejected, nothing spent."""
        game, p1, p2, axgard, newcomer = self._setup()
        axgard.is_tapped = True
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, axgard)

    def test_summoning_sick_source_rejected_before_cost(self):
        """Legality invariant: a summoning-sick source without haste cannot pay
        the ``{T}`` cost (rule 302.6)."""
        game, p1, p2, axgard, newcomer = self._setup()
        axgard.summoning_sick = True
        assert Keyword.HASTE not in axgard.keywords
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, axgard)
        assert axgard.is_tapped is False
