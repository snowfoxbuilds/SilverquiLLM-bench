"""Tests for SOS 192 — Grapple with Death."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_192.card_impl import GrappleWithDeath
from benchmarks.sos.workspace.engine.card import Artifact, Creature, Enchantment, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestGrappleWithDeathProperties:
    """Static card data should match the SOS 192 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(GrappleWithDeath(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = GrappleWithDeath(owner=None)

        assert card.name == "Grapple with Death"
        assert card.mana_cost == ManaCost.parse("{1}{B}{G}")


class TestGrappleWithDeathTargeting:
    """Grapple with Death should target an artifact or creature on the battlefield."""

    def test_returns_a_single_battlefield_target_requirement_for_artifacts_or_creatures(self) -> None:
        game = create_game()
        reqs = GrappleWithDeath(owner=None).get_targets(game)
        artifact = Artifact(name="Training Relic")
        creature = Creature(name="Training Bear", base_power=2, base_toughness=2)
        enchantment = Enchantment(name="Lecture Hall Banner")

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[0].filter_fn(artifact) is True
        assert reqs[0].filter_fn(creature) is True
        assert reqs[0].filter_fn(enchantment) is False


class TestGrappleWithDeathResolution:
    """Grapple with Death should destroy its target and gain life."""

    def test_on_resolve_destroys_the_chosen_artifact_and_gains_one_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Artifact(name="Opponent Relic", owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        spell = GrappleWithDeath(owner=p1, controller=p1)
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert not game.get_battlefield(p2).contains(target)
        assert game.get_graveyard(p2).contains(target)
        assert p1.life == 21
