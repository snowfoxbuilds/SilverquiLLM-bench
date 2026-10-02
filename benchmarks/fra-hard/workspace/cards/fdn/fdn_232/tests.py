"""Reference test for FDN 232 — Scavenging Ooze.

A **targeted activated ability whose target lives in a graveyard**: the card is
chosen at activation (before {G} is paid), captured on the stack object, and
revalidated against its graveyard stint at resolution. A target that leaves the
graveyard is not replaced, and no other graveyard card can be selected in its
place — the creature reward lands only when the originally-targeted legal card is
actually exiled.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_232.card_impl import ScavengingOoze
from engine.abilities import AbilityError
from engine.card import Creature, Instant
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import ManaCost, ManaType, Zone
from engine.zones import move_to_zone
from test_utils import (
    activate_card_ability,
    create_game,
    resolve_stack,
    set_board_state,
)


def _creature_card(p, name="Dead Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _noncreature_card(p, name="Dead Bolt"):
    return Instant(name=name, owner=p, controller=p)


def _activate(game, player, ooze, target):
    """Activate Ooze targeting *target* (a graveyard card) via an Intent."""
    inst = game.refs.instance_id(target, Zone.GRAVEYARD.value)
    player.start_intent("ooze", Intent(
        pattern=GameRef(card=frozenset({("name", ooze.name)})),
        preferences=(Decision.obj(instance=inst),),
    ))
    try:
        activate_card_ability(game, player, ooze)
    finally:
        player.end_intent("ooze")


class TestScavengingOozeProperties:
    def test_static_data(self):
        ooze = ScavengingOoze(owner=None)
        assert ooze.name == "Scavenging Ooze"
        assert ooze.mana_cost == ManaCost.parse("{1}{G}")
        assert (ooze.base_power, ooze.base_toughness) == (2, 2)

    def test_has_targeted_ability(self):
        ooze = ScavengingOoze(owner=None)
        abilities = ooze.get_activated_abilities()
        assert len(abilities) == 1
        assert abilities[0].targeting is not None


class TestScavengingOozeAbility:
    def _setup(self, gy_cards):
        game = create_game()
        p1, p2 = game.players
        ooze = ScavengingOoze(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ooze], mana={ManaType.GREEN: 3})
        set_board_state(game, 1, graveyard=gy_cards)
        return game, p1, p2, ooze

    def test_target_fixed_at_activation_on_stack(self):
        target = _creature_card(None)
        game, p1, p2, ooze = self._setup([target])
        _activate(game, p1, ooze, target)
        # Chosen at activation and captured on the stack — before resolution.
        top = game.stack.peek()
        assert top.targets == [target]
        # {G} was paid (targeting precedes cost payment, but a legal target and
        # mana were both present, so the cost was paid).
        assert p1.mana_pool.get(ManaType.GREEN) == 2

    def test_no_graveyard_card_rejects_before_cost(self):
        game, p1, p2, ooze = self._setup([])
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, ooze)
        assert p1.mana_pool.get(ManaType.GREEN) == 3  # no {G} spent

    def test_creature_card_target_gives_reward(self):
        target = _creature_card(None)
        game, p1, p2, ooze = self._setup([target])
        life_before = p1.life
        _activate(game, p1, ooze, target)
        resolve_stack(game)
        # Target exiled, +1/+1 counter on Ooze, controller gained 1 life.
        assert not game.get_graveyard(p2).contains(target)
        assert game.get_exile(p2).contains(target)
        assert ooze.plus_one_counters == 1
        assert p1.life == life_before + 1

    def test_noncreature_card_target_no_reward(self):
        target = _noncreature_card(None)
        game, p1, p2, ooze = self._setup([target])
        life_before = p1.life
        _activate(game, p1, ooze, target)
        resolve_stack(game)
        assert game.get_exile(p2).contains(target)  # exiled
        assert ooze.plus_one_counters == 0           # but no reward
        assert p1.life == life_before

    def test_target_removed_in_response_not_reselected(self):
        """The captured card leaves the graveyard before resolution; the ability
        does not choose another card and applies no reward."""
        target = _creature_card(None, "Target Bear")
        other = _creature_card(None, "Other Bear")
        game, p1, p2, ooze = self._setup([target, other])
        life_before = p1.life
        _activate(game, p1, ooze, target)
        # Remove the captured target from the graveyard, in response.
        move_to_zone(game, target, Zone.GRAVEYARD, Zone.HAND)
        resolve_stack(game)
        # No other graveyard card is exiled; no counter, no life gain.
        assert game.get_graveyard(p2).contains(other)
        assert not game.get_exile(p2).contains(other)
        assert ooze.plus_one_counters == 0
        assert p1.life == life_before

    def test_card_added_after_activation_not_selectable(self):
        """A card added to a graveyard after activation cannot become the
        target; only the originally-captured card is exiled."""
        target = _creature_card(None, "Original")
        game, p1, p2, ooze = self._setup([target])
        _activate(game, p1, ooze, target)
        # A fresh creature card appears in a graveyard after the target was fixed.
        latecomer = _creature_card(p2, "Latecomer")
        game.get_graveyard(p2).add(latecomer)
        latecomer.instance_id = game.refs.instance_id(latecomer, Zone.GRAVEYARD.value)
        resolve_stack(game)
        # The captured target is exiled; the latecomer is untouched.
        assert game.get_exile(p2).contains(target)
        assert game.get_graveyard(p2).contains(latecomer)
        assert not game.get_exile(p2).contains(latecomer)
