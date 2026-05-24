"""Audited tests for FDN 203 — Involuntary Employment."""

from __future__ import annotations

from card_impl import InvoluntaryEmployment
from engine.card import CardImpl, Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestInvoluntaryEmploymentBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = InvoluntaryEmployment(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = InvoluntaryEmployment(owner=None)
        assert card.name == "Involuntary Employment"

    def test_mana_cost(self) -> None:
        card = InvoluntaryEmployment(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{R}")


class TestInvoluntaryEmploymentResolve:
    """Gain control, untap, grant haste, create Treasure."""

    def test_gains_control_of_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(creature)
        spell = InvoluntaryEmployment(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        assert creature.controller is p1

    def test_untaps_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        creature.is_tapped = True
        game.get_battlefield(p2).add(creature)
        spell = InvoluntaryEmployment(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        assert creature.is_tapped is False

    def test_creates_treasure_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(creature)
        bf_before = len(game.get_battlefield(p1).get_all())
        spell = InvoluntaryEmployment(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        bf_after = len(game.get_battlefield(p1).get_all())
        assert bf_after >= bf_before + 1  # At least 1 treasure created

    def test_fizzles_if_no_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = InvoluntaryEmployment(owner=p1, controller=p1)
        spell.chosen_targets = [None]
        spell.on_resolve(game)  # Should not raise
