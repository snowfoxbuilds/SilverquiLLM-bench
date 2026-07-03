"""Tests for SOS 79 — Dissection Practice.

Instant for {B}. Three modal effects:
1. Target opponent loses 1 life and you gain 1 life.
2. Up to one target creature gets +1/+1 until end of turn.
3. Up to one target creature gets -1/-1 until end of turn.
"""

from __future__ import annotations

from cards.sos.sos_79.card_impl import DissectionPractice
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game


class TestDissectionPracticeProperties:
    """Static card data should match the SOS 79 spec."""

    def test_name(self) -> None:
        card = DissectionPractice(owner=None)
        assert card.name == "Dissection Practice"

    def test_mana_cost(self) -> None:
        card = DissectionPractice(owner=None)
        assert card.mana_cost == ManaCost.parse("{B}")

    def test_is_instant(self) -> None:
        card = DissectionPractice(owner=None)
        assert isinstance(card, Instant)


class TestDissectionPracticeResolution:
    """All three effects apply on resolution."""

    def test_opponent_loses_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = DissectionPractice(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        life_before = p2.life
        spell.on_resolve(game)
        assert p2.life == life_before - 1

    def test_controller_gains_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = DissectionPractice(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        life_before = p1.life
        spell.on_resolve(game)
        assert p1.life == life_before + 1

    def test_target_creature_gets_plus_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)
        spell = DissectionPractice(owner=p1, controller=p1)
        # Targets: opponent, creature to buff, creature to debuff (None)
        spell.chosen_targets = [p2, bear, None]
        spell.on_resolve(game)
        assert bear.power == 3
        assert bear.toughness == 3

    def test_target_creature_gets_minus_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        enemy = Creature(name="Enemy Bear", owner=p2, controller=p2,
                         base_power=2, base_toughness=2)
        enemy.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(enemy)
        spell = DissectionPractice(owner=p1, controller=p1)
        # Targets: opponent, creature to buff (None), creature to debuff
        spell.chosen_targets = [p2, None, enemy]
        spell.on_resolve(game)
        assert enemy.power == 1
        assert enemy.toughness == 1

    def test_all_three_effects_at_once(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ally = Creature(name="Ally", owner=p1, controller=p1,
                        base_power=1, base_toughness=1)
        ally.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(ally)
        enemy = Creature(name="Enemy", owner=p2, controller=p2,
                         base_power=3, base_toughness=3)
        enemy.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(enemy)
        spell = DissectionPractice(owner=p1, controller=p1)
        spell.chosen_targets = [p2, ally, enemy]
        p1_life_before = p1.life
        p2_life_before = p2.life
        spell.on_resolve(game)
        assert p2.life == p2_life_before - 1
        assert p1.life == p1_life_before + 1
        assert ally.power == 2
        assert ally.toughness == 2
        assert enemy.power == 2
        assert enemy.toughness == 2
