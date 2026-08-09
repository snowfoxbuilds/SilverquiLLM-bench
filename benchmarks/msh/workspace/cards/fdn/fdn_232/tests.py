"""Reference test for FDN 232 — Scavenging Ooze.

Demonstrates a **resolution-time non-targeted choice** (Phase D pattern 3):
the graveyard card is chosen inside the effect via ``choose_object`` (answered
by an Intent that stays open through resolution), not through the activation
targeting channel. If the exiled card was a creature card, the Ooze grows and
its controller gains life.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_232.card_impl import ScavengingOoze
from engine.abilities import AbilityError
from engine.card import Creature, Enchantment
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import CardType, ManaCost, ManaType, Zone
from engine.zones import move_to_zone
from test_utils import activate_card_ability, create_game, resolve_stack, set_board_state


def _creature_card(p, name="Grizzly"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _activate_and_resolve(game, player, source, chosen_card):
    """Pattern 3: the intent must stay open through resolution, since the
    graveyard choice happens inside the effect, not at activation."""
    inst = game.refs.instance_id(chosen_card, Zone.GRAVEYARD.value)
    player.start_intent("ooze", Intent(
        pattern=GameRef(card=frozenset({("name", source.name)})),
        preferences=(Decision.obj(instance=inst),),
    ))
    try:
        activate_card_ability(game, player, source)
        resolve_stack(game)
    finally:
        player.end_intent("ooze")


class TestScavengingOozeProperties:
    def test_static_data(self):
        card = ScavengingOoze(owner=None)
        assert card.name == "Scavenging Ooze"
        assert card.mana_cost == ManaCost.parse("{1}{G}")
        assert (card.base_power, card.base_toughness) == (2, 2)
        assert "Ooze" in card.subtypes

    def test_ability_is_not_targeted(self):
        """Pattern 3: no activation-time targeting hook — the graveyard card is
        chosen at resolution."""
        abilities = ScavengingOoze(owner=None).get_activated_abilities()
        assert len(abilities) == 1
        assert abilities[0].targeting is None
        assert abilities[0].can_activate is not None


class TestScavengingOozeAbility:
    def _setup(self, gy_card):
        game = create_game()
        p1, p2 = game.players
        ooze = ScavengingOoze(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ooze], mana={ManaType.GREEN: 1}, life=20)
        set_board_state(game, 1, graveyard=[gy_card])
        return game, p1, p2, ooze

    def test_exiling_creature_card_grows_ooze_and_gains_life(self):
        creature_card = _creature_card(None, "Fallen Bear")
        game, p1, p2, ooze = self._setup(creature_card)
        _activate_and_resolve(game, p1, ooze, creature_card)
        assert not game.get_graveyard(p2).contains(creature_card)   # exiled
        assert CardType.CREATURE in creature_card.card_types
        assert ooze.plus_one_counters == 1
        assert p1.life == 21

    def test_exiling_noncreature_card_only_exiles(self):
        aura = Enchantment(name="Old Aura", owner=None)
        game, p1, p2, ooze = self._setup(aura)
        _activate_and_resolve(game, p1, ooze, aura)
        assert not game.get_graveyard(p2).contains(aura)            # exiled
        assert ooze.plus_one_counters == 0                          # not a creature
        assert p1.life == 20                                        # no life gain

    def test_mana_cost_is_paid(self):
        creature_card = _creature_card(None, "Fallen Bear")
        game, p1, p2, ooze = self._setup(creature_card)
        _activate_and_resolve(game, p1, ooze, creature_card)
        assert p1.mana_pool.total() == 0                            # {G} paid

    def test_can_exile_from_own_graveyard(self):
        """Option-set invariant: any graveyard's cards are choosable, including
        the controller's own."""
        game = create_game()
        p1, p2 = game.players
        ooze = ScavengingOoze(owner=p1, controller=p1)
        my_card = _creature_card(None, "My Fallen")
        set_board_state(game, 0, battlefield=[ooze], graveyard=[my_card],
                        mana={ManaType.GREEN: 1}, life=20)
        _activate_and_resolve(game, p1, ooze, my_card)
        assert not game.get_graveyard(p1).contains(my_card)
        assert ooze.plus_one_counters == 1

    def test_empty_graveyards_rejected_before_cost(self):
        """Legality invariant (can_activate): with no card in any graveyard the
        ability cannot be activated (mirrors "target card from a graveyard")."""
        game = create_game()
        p1, p2 = game.players
        ooze = ScavengingOoze(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ooze], mana={ManaType.GREEN: 1})
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, ooze)
        assert p1.mana_pool.total() == 1                            # no mana spent
