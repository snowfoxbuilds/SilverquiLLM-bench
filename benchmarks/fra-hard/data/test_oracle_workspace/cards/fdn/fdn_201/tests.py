"""Reference test for FDN 201 — Heartfire Immolator.

Demonstrates a **targeted activated ability** (Phase D pattern 2) whose cost
sacrifices the source and snapshots its power (last-known information) before
it leaves the battlefield. The "target creature or planeswalker" is chosen at
activation via a Player Query (answered by an Intent), captured on the stack,
revalidated at resolution, and dealt damage equal to the snapshotted power.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_201.card_impl import HeartfireImmolator
from engine.abilities import AbilityError
from engine.card import Creature, Planeswalker
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import Keyword, ManaCost, ManaType, Zone
from engine.zones import move_to_zone
from test_utils import activate_card_ability, create_game, resolve_stack, set_board_state


def _bear(p, name="Bear", power=2):
    return Creature(name=name, base_power=power, base_toughness=3, owner=p, controller=p)


def _on_battlefield(game, obj):
    return any(game.get_battlefield(p).contains(obj) for p in game.players)


def _activate_targeting(game, player, source, target):
    inst = game.refs.instance_id(target, Zone.BATTLEFIELD.value)
    player.start_intent("immo", Intent(
        pattern=GameRef(card=frozenset({("name", source.name)})),
        preferences=(Decision.obj(instance=inst),),
    ))
    try:
        activate_card_ability(game, player, source)
    finally:
        player.end_intent("immo")


class TestHeartfireImmolatorProperties:
    def test_static_data(self):
        card = HeartfireImmolator(owner=None)
        assert card.name == "Heartfire Immolator"
        assert card.mana_cost == ManaCost.parse("{1}{R}")
        assert (card.base_power, card.base_toughness) == (2, 2)
        assert {"Human", "Wizard"} <= card.subtypes
        assert Keyword.PROWESS in card.keywords

    def test_has_one_targeted_ability(self):
        abilities = HeartfireImmolator(owner=None).get_activated_abilities()
        assert len(abilities) == 1
        assert abilities[0].targeting is not None


class TestHeartfireImmolatorAbility:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        immo = HeartfireImmolator(owner=p1, controller=p1)
        target = _bear(p2, "Their Bear")
        set_board_state(game, 0, battlefield=[immo], mana={ManaType.RED: 1})
        set_board_state(game, 1, battlefield=[target])
        return game, p1, p2, immo, target

    def test_deals_damage_equal_to_power(self):
        game, p1, p2, immo, target = self._setup()
        _activate_targeting(game, p1, immo, target)
        resolve_stack(game)
        assert target.damage_marked == 2                 # power 2
        assert not _on_battlefield(game, immo)           # sacrificed
        assert p1.mana_pool.total() == 0                 # {R} paid

    def test_damage_uses_power_snapshot_at_activation(self):
        """The snapshot captures power before the sacrifice, so a pumped power
        is reflected even though the source is gone at resolution."""
        game, p1, p2, immo, target = self._setup()
        immo.modified_power = 5                           # e.g. prowess pump
        _activate_targeting(game, p1, immo, target)
        resolve_stack(game)
        assert target.damage_marked == 5

    def test_target_captured_on_stack(self):
        game, p1, p2, immo, target = self._setup()
        _activate_targeting(game, p1, immo, target)
        assert game.stack.peek().targets == [target]

    def test_planeswalker_is_a_legal_target(self):
        """Option-set invariant: a planeswalker is a legal target (creature or
        planeswalker), captured on the stack at activation."""
        game = create_game()
        p1, p2 = game.players
        immo = HeartfireImmolator(owner=p1, controller=p1)
        walker = Planeswalker(name="Chandra", owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[immo], mana={ManaType.RED: 1})
        set_board_state(game, 1, battlefield=[walker])
        _activate_targeting(game, p1, immo, walker)
        assert game.stack.peek().targets == [walker]

    def test_source_off_battlefield_rejected_before_cost(self):
        """Legality invariant (can_activate)."""
        game, p1, p2, immo, target = self._setup()
        move_to_zone(game, immo, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, immo)
        assert p1.mana_pool.total() == 1                 # no mana spent
