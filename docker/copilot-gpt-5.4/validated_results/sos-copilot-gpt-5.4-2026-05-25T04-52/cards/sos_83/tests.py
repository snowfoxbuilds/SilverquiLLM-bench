"""Tests for SOS 83 — Foolish Fate."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_83.card_impl import FoolishFate
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestFoolishFateProperties:
    """Static card data should match the SOS 83 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(FoolishFate(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = FoolishFate(owner=None)
        assert card.name == "Foolish Fate"
        assert card.mana_cost == ManaCost.parse("{2}{B}")


class TestFoolishFateTargeting:
    """Foolish Fate should target a creature on the battlefield."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = FoolishFate(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = FoolishFate(owner=None).get_targets(game)[0]
        creature = Creature(name="Study Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Lecture Notes")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestFoolishFateResolution:
    """Foolish Fate should destroy the target and reward life gain."""

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = FoolishFate(owner=p1, controller=p1)

        spell.on_resolve(game)

        assert game.get_graveyard(p1).get_all() == []
        assert game.get_graveyard(p2).get_all() == []

    def test_destroys_the_target_creature_without_life_loss_if_you_did_not_gain_life_this_turn(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(target)

        spell = FoolishFate(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert game.get_graveyard(p2).contains(target)
        assert p2.life == 20

    def test_if_you_gained_life_this_turn_the_destroyed_creatures_controller_loses_three_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(target)
        p1.life_gained_this_turn = 1

        spell = FoolishFate(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert game.get_graveyard(p2).contains(target)
        assert p2.life == 17
