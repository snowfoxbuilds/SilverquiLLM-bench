"""Reference test for FDN 195 — Fanatical Firebrand.

Demonstrates a **targeted activated ability** (Phase D pattern 2) with an
``{T}, Sacrifice`` cost and an "any target" option set (players and
creatures/planeswalkers). The target is chosen at activation via a Player
Query (answered by an Intent), captured on the stack, revalidated at
resolution, and dealt 1 damage.
"""

from __future__ import annotations

import pytest
from cards.fdn.fdn_195.card_impl import FanaticalFirebrand
from engine.abilities import AbilityError
from engine.card import Creature
from engine.decisions import Decision, GameRef
from test_utils import Intent
from engine.types import Keyword, ManaCost, Zone
from engine.zones import move_to_zone
from test_utils import (
    activate_card_ability,
    resolve_stack,
    set_board_state,
)
from test_utils import (
    scenario_game as create_game,
)


def _bear(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _names(zone):
    return [card.name for card in zone.get_all()]


def _on_battlefield(game, obj):
    return any(game.get_battlefield(p).contains(obj) for p in game.players)


def _activate_targeting(game, player, source, target, *, target_zone=Zone.BATTLEFIELD.value):
    inst = game.refs.instance_id(target, target_zone)
    player.start_intent(
        "brand",
        Intent(
            pattern=GameRef(card=frozenset({("name", source.name)})),
            preferences=(Decision.obj(instance=inst),),
        ),
    )
    try:
        activate_card_ability(game, player, source)
    finally:
        player.end_intent("brand")


class TestFanaticalFirebrandProperties:
    def test_static_data(self):
        card = FanaticalFirebrand(owner=None)
        assert card.name == "Fanatical Firebrand"
        assert card.mana_cost == ManaCost.parse("{R}")
        assert (card.base_power, card.base_toughness) == (1, 1)
        assert {"Goblin", "Pirate"} <= card.subtypes
        assert Keyword.HASTE in card.keywords


class TestFanaticalFirebrandAbility:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        brand = FanaticalFirebrand(owner=p1, controller=p1)
        target = _bear(p2, "Their Bear")
        set_board_state(game, 0, battlefield=[brand], life=20)
        set_board_state(game, 1, battlefield=[target], life=20)
        return game, p1, p2, brand, target

    def test_deals_damage_to_target_creature(self):
        game, p1, _p2, brand, target = self._setup()
        _activate_targeting(game, p1, brand, target)
        resolve_stack(game)
        assert target.damage_marked == 1
        assert not _on_battlefield(game, brand)  # sacrificed as cost

    def test_deals_damage_to_a_player(self):
        """Option-set invariant: "any target" includes players."""
        game, p1, p2, brand, _target = self._setup()
        _activate_targeting(game, p1, brand, p2)
        resolve_stack(game)
        assert p2.life == 19

    def test_cost_taps_and_sacrifices(self):
        game, p1, _p2, brand, target = self._setup()
        # {T} is part of the cost: a tapped Firebrand cannot pay it.
        brand.is_tapped = True
        with pytest.raises(AbilityError):
            _activate_targeting(game, p1, brand, target)
        assert brand.name in _names(game.get_battlefield(p1))
        brand.is_tapped = False
        _activate_targeting(game, p1, brand, target)
        # Status is not read off the sacrificed card: it is a new object (CR 400.7).
        assert brand.name not in _names(game.get_battlefield(p1))
        assert brand.name in _names(game.get_graveyard(p1))
        resolve_stack(game)
        assert target.damage_marked == 1

    def test_target_captured_on_stack(self):
        game, p1, _p2, brand, target = self._setup()
        _activate_targeting(game, p1, brand, target)
        assert game.stack.peek().targets == [target]

    def test_source_off_battlefield_rejected_before_cost(self):
        """Legality invariant (can_activate): activating while the source is
        not on the battlefield is rejected before any cost is paid."""
        game, p1, _p2, brand, _target = self._setup()
        move_to_zone(game, brand, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, brand)
