"""Tests for SOS 156 — Oracle's Restoration."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_156.card_impl import OraclesRestoration
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestOraclesRestorationProperties:
    """Static card data should match the SOS 156 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(OraclesRestoration(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = OraclesRestoration(owner=None)

        assert card.name == "Oracle's Restoration"
        assert card.mana_cost == ManaCost.parse("{G}")


class TestOraclesRestorationTargeting:
    """Oracle's Restoration should target a creature you control."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = OraclesRestoration(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_only_a_creature_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        req = OraclesRestoration(owner=p1, controller=p1).get_targets(game)[0]

        friendly_creature = Creature(
            name="Helpful Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opposing_creature = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        non_creature = CardImpl(name="Campus Notes", owner=p1, controller=p1)

        assert req.filter_fn(friendly_creature) is True
        assert req.filter_fn(opposing_creature) is False
        assert req.filter_fn(non_creature) is False


class TestOraclesRestorationResolution:
    """Oracle's Restoration should buff your creature, draw, and gain life."""

    def test_target_gets_plus_one_plus_one_until_end_of_turn_and_you_draw_and_gain_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Restored Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        drawn = CardImpl(name="Fresh Notes", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[target])
        game.get_library(p1).add(drawn)

        spell = OraclesRestoration(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.power == 3
        assert target.toughness == 3
        assert game.get_hand(p1).contains(drawn)
        assert p1.life == 21

    def test_temporary_bonus_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Restored Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        drawn = CardImpl(name="Fresh Notes", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[target])
        game.get_library(p1).add(drawn)

        spell = OraclesRestoration(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.power == 3
        assert target.toughness == 3

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert target.power == 2
        assert target.toughness == 2
        assert game.get_hand(p1).contains(drawn)
        assert p1.life == 21

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Restored Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        drawn = CardImpl(name="Fresh Notes", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[target])
        game.get_library(p1).add(drawn)

        OraclesRestoration(owner=p1, controller=p1).on_resolve(game)

        assert target.power == 2
        assert target.toughness == 2
        assert not game.get_hand(p1).contains(drawn)
        assert p1.life == 20
