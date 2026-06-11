"""Tests for SOS 89 — Masterful Flourish."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_89.card_impl import MasterfulFlourish
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestMasterfulFlourishProperties:
    """Static card data should match the SOS 89 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(MasterfulFlourish(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = MasterfulFlourish(owner=None)
        assert card.name == "Masterful Flourish"
        assert card.mana_cost == ManaCost.parse("{B}")


class TestMasterfulFlourishTargeting:
    """Masterful Flourish should target a creature you control."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = MasterfulFlourish(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_only_a_creature_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        req = MasterfulFlourish(owner=p1, controller=p1).get_targets(game)[0]

        friendly_creature = Creature(
            name="Helpful Assistant",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opposing_creature = Creature(
            name="Opposing Assistant",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        non_creature = CardImpl(name="Lecture Notes", owner=p1, controller=p1)

        assert req.filter_fn(friendly_creature) is True
        assert req.filter_fn(opposing_creature) is False
        assert req.filter_fn(non_creature) is False


class TestMasterfulFlourishResolution:
    """Masterful Flourish should grant power and indestructible until end of turn."""

    def test_target_gets_plus_one_power_and_indestructible(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Careful Assistant",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(target)
        card = MasterfulFlourish(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.on_resolve(game)

        assert target.power == 3
        assert target.toughness == 2
        assert Keyword.INDESTRUCTIBLE in target.keywords

    def test_granted_indestructible_prevents_destroy_effects(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Careful Assistant",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(target)
        card = MasterfulFlourish(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.on_resolve(game)
        destroy(game, target)

        assert game.get_battlefield(p1).contains(target)
        assert not game.get_graveyard(p1).contains(target)

    def test_temporary_bonus_and_indestructible_expire_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Careful Assistant",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(target)
        card = MasterfulFlourish(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.on_resolve(game)
        assert target.power == 3
        assert Keyword.INDESTRUCTIBLE in target.keywords

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert target.power == 2
        assert target.toughness == 2
        assert Keyword.INDESTRUCTIBLE not in target.keywords
