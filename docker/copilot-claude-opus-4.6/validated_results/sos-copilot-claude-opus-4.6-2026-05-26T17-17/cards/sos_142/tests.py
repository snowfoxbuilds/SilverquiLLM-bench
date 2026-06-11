"""Tests for SOS 142 — Chelonian Tackle.

Chelonian Tackle is a {2}{G} Sorcery:
  Target creature you control gets +0/+10 until end of turn.
  Then it fights up to one target creature an opponent controls.
"""

from __future__ import annotations

from cards.sos.sos_142.card_impl import ChelonianTackle
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestChelonianTackleProperties:
    """Static card data should match spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(ChelonianTackle(owner=None), Sorcery)

    def test_name(self) -> None:
        assert ChelonianTackle(owner=None).name == "Chelonian Tackle"

    def test_mana_cost(self) -> None:
        assert ChelonianTackle(owner=None).mana_cost == ManaCost.parse("{2}{G}")


class TestChelonianTackleResolution:
    """Resolution: +0/+10 then fight."""

    def _setup_game(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        my_creature = Creature(
            name="My Turtle",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=3,
        )
        my_creature.card_types = {CardType.CREATURE}

        enemy = Creature(
            name="Enemy Beast",
            owner=p2,
            controller=p2,
            base_power=4,
            base_toughness=4,
        )
        enemy.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[my_creature])
        set_board_state(game, 1, battlefield=[enemy])
        return game, p1, p2, my_creature, enemy

    def test_toughness_buff_applied(self) -> None:
        """Target creature gets +0/+10."""
        game, p1, p2, my_creature, enemy = self._setup_game()

        spell = ChelonianTackle(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, enemy]
        spell.on_resolve(game)

        # Toughness should be 3 + 10 = 13
        assert my_creature.get_toughness() == 13

    def test_no_power_buff(self) -> None:
        """Power remains unchanged (+0)."""
        game, p1, p2, my_creature, enemy = self._setup_game()

        spell = ChelonianTackle(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, enemy]
        spell.on_resolve(game)

        assert my_creature.get_power() == 1

    def test_fight_deals_mutual_damage(self) -> None:
        """Fight: each deals damage equal to its power to the other."""
        game, p1, p2, my_creature, enemy = self._setup_game()

        spell = ChelonianTackle(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, enemy]
        spell.on_resolve(game)

        # My creature (power 1) deals 1 damage to enemy
        assert enemy.damage_dealt_to_it == 1
        # Enemy (power 4) deals 4 damage to my creature
        assert my_creature.damage_dealt_to_it == 4

    def test_creature_survives_with_toughness_buff(self) -> None:
        """With +10 toughness, creature survives the fight damage."""
        game, p1, p2, my_creature, enemy = self._setup_game()

        spell = ChelonianTackle(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, enemy]
        spell.on_resolve(game)

        # 13 toughness - 4 damage = still alive
        assert my_creature.get_toughness() - my_creature.damage_dealt_to_it > 0

    def test_no_opponent_target_no_fight(self) -> None:
        """'Up to one' means you can choose zero opponent targets (no fight)."""
        game = create_game()
        p1 = game.players[0]

        my_creature = Creature(
            name="My Turtle",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=3,
        )
        my_creature.card_types = {CardType.CREATURE}
        set_board_state(game, 0, battlefield=[my_creature])

        spell = ChelonianTackle(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature]
        spell.on_resolve(game)

        # Toughness buff still applies
        assert my_creature.get_toughness() == 13
        # No damage taken (no fight)
        assert my_creature.damage_dealt_to_it == 0
