"""Audited tests for FDN 12 — Felidar Savior."""

from __future__ import annotations

from card_impl import FelidarSavior
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestFelidarSaviorBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = FelidarSavior(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = FelidarSavior(owner=None)
        assert card.name == "Felidar Savior"

    def test_mana_cost(self) -> None:
        card = FelidarSavior(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{W}")

    def test_power_toughness(self) -> None:
        card = FelidarSavior(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3

    def test_has_lifelink(self) -> None:
        card = FelidarSavior(owner=None)
        assert Keyword.LIFELINK in card.keywords

    def test_subtypes(self) -> None:
        card = FelidarSavior(owner=None)
        assert "Cat" in card.subtypes
        assert "Beast" in card.subtypes


class TestFelidarSaviorETB:
    """ETB puts +1/+1 counter on up to two other target creatures."""

    def _setup_etb(self, num_targets=2):
        game = create_game()
        p1 = game.players[0]
        felidar = FelidarSavior(owner=p1, controller=p1)
        targets = []
        bf = game.get_battlefield(p1)
        bf.add(felidar)
        for i in range(num_targets):
            c = Creature(
                name=f"Ally{i}", base_power=2, base_toughness=2,
                owner=p1, controller=p1,
            )
            bf.add(c)
            targets.append(c)
        felidar.chosen_targets = targets
        felidar.on_resolve(game)
        return game, felidar, targets, p1

    def test_etb_adds_counter_to_two_targets(self) -> None:
        game, felidar, targets, p1 = self._setup_etb(2)
        assert targets[0].plus_one_counters >= 1
        assert targets[1].plus_one_counters >= 1

    def test_etb_adds_counter_to_one_target(self) -> None:
        game, felidar, targets, p1 = self._setup_etb(1)
        assert targets[0].plus_one_counters >= 1

    def test_etb_no_targets_does_not_crash(self) -> None:
        game = create_game()
        p1 = game.players[0]
        felidar = FelidarSavior(owner=p1, controller=p1)
        game.get_battlefield(p1).add(felidar)
        felidar.chosen_targets = []
        felidar.on_resolve(game)  # Should not raise

    def test_etb_does_not_counter_itself(self) -> None:
        game = create_game()
        p1 = game.players[0]
        felidar = FelidarSavior(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(felidar)
        felidar.chosen_targets = [felidar]
        felidar.on_resolve(game)
        assert felidar.plus_one_counters == 0
