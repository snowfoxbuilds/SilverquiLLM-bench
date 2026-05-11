"""Audited tests for Felling Blow (FDN collector number 105).

Collector number 105 is shared with Withering Curse (simple_spells_batch2).
A conftest override maps directory '105b' to FellingBlow for this batch.
The existing '105' directory covers Withering Curse.
"""

from __future__ import annotations

import pytest

from card_impl import FellingBlow

from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from tests.test_utils import create_game, set_board_state


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)


@pytest.mark.basic
class TestFellingBlowProperties:
    def test_is_sorcery(self):
        card = FellingBlow()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = FellingBlow()
        assert card.name == "Felling Blow"

    def test_mana_cost(self):
        card = FellingBlow()
        assert card.mana_cost == ManaCost.parse("{2}{G}")


@pytest.mark.ability
class TestFellingBlowResolution:
    def test_adds_plus_one_counter_to_own_creature(self):
        """Resolution adds a +1/+1 counter to your creature before fighting."""
        game = create_game()
        p1, p2 = game.players
        my_creature = _make_creature(name="Elf", power=2, toughness=2, owner=p1, controller=p1)
        opp_creature = _make_creature(name="Goblin", power=3, toughness=3, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[my_creature])
        set_board_state(game, 1, battlefield=[opp_creature])
        spell = FellingBlow(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, opp_creature]
        spell.on_resolve(game)
        # Must verify the +1/+1 counter was actually placed
        assert my_creature.counters.get("+1/+1", 0) >= 1

    def test_fights_with_pumped_power(self):
        """Opponent creature takes damage equal to your creature's pumped power (base + counter)."""
        game = create_game()
        p1, p2 = game.players
        my_creature = _make_creature(name="Elf", power=2, toughness=2, owner=p1, controller=p1)
        opp_creature = _make_creature(name="Goblin", power=3, toughness=3, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[my_creature])
        set_board_state(game, 1, battlefield=[opp_creature])
        spell = FellingBlow(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, opp_creature]
        spell.on_resolve(game)
        # After +1/+1 counter, my creature is 3/3; opponent takes exactly 3 damage
        assert opp_creature.damage_marked == 3

    def test_own_creature_takes_no_reciprocal_damage(self):
        """Felling Blow is one-way damage; your creature takes no damage."""
        game = create_game()
        p1, p2 = game.players
        my_creature = _make_creature(name="Elf", power=2, toughness=2, owner=p1, controller=p1)
        opp_creature = _make_creature(name="Goblin", power=3, toughness=3, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[my_creature])
        set_board_state(game, 1, battlefield=[opp_creature])
        spell = FellingBlow(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, opp_creature]
        spell.on_resolve(game)
        # One-way damage: source creature takes no damage and keeps +1/+1 counter
        assert my_creature.damage_marked == 0
        assert my_creature.counters.get("+1/+1", 0) >= 1

    def test_opponent_creature_takes_pumped_damage_large(self):
        """With 4-power creature, opponent takes 5 damage (4 base + 1 counter)."""
        game = create_game()
        p1, p2 = game.players
        my_creature = _make_creature(name="Elf", power=4, toughness=4, owner=p1, controller=p1)
        opp_creature = _make_creature(name="Goblin", power=1, toughness=8, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[my_creature])
        set_board_state(game, 1, battlefield=[opp_creature])
        spell = FellingBlow(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, opp_creature]
        spell.on_resolve(game)
        # My creature gets +1/+1 counter → 5 power; opponent takes exactly 5 damage
        assert opp_creature.damage_marked == 5


@pytest.mark.edge
class TestFellingBlowEdge:
    def test_no_targets_state_unchanged(self):
        """Empty targets does not crash and leaves game state unchanged."""
        game = create_game()
        p1, p2 = game.players
        my_creature = _make_creature(name="Elf", power=2, toughness=2, owner=p1, controller=p1)
        opp_creature = _make_creature(name="Goblin", power=3, toughness=3, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[my_creature])
        set_board_state(game, 1, battlefield=[opp_creature])
        spell = FellingBlow(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)
        # Battlefield membership unchanged
        assert my_creature in list(p1.zones[Zone.BATTLEFIELD].get_all())
        assert opp_creature in list(p2.zones[Zone.BATTLEFIELD].get_all())
        # No damage dealt
        assert my_creature.damage_marked == 0
        assert opp_creature.damage_marked == 0
        # No counters added (if counters attribute exists)
        if hasattr(my_creature, "counters"):
            assert my_creature.counters.get("+1/+1", 0) == 0
