"""Tests for SOS 104 — Wander Off."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_104.card_impl import WanderOff
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestWanderOffProperties:
    """Static card data should match the SOS 104 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(WanderOff(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = WanderOff(owner=None)

        assert card.name == "Wander Off"
        assert card.mana_cost == ManaCost.parse("{3}{B}")


class TestWanderOffTargeting:
    """Wander Off should target a creature on the battlefield."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = WanderOff(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = WanderOff(owner=None).get_targets(game)[0]
        creature = Creature(name="Study Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Lecture Notes")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestWanderOffResolution:
    """Wander Off should exile the targeted creature."""

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = WanderOff(owner=p1, controller=p1)
        reqs = spell.get_targets(game)

        assert len(reqs) == 1

        spell.on_resolve(game)

        assert game.get_exile(p1).get_all() == []
        assert game.get_exile(p2).get_all() == []

    def test_exiles_the_target_creature(self) -> None:
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

        spell = WanderOff(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert game.get_exile(p2).contains(target)
        assert not game.get_battlefield(p2).contains(target)
        assert not game.get_graveyard(p2).contains(target)
