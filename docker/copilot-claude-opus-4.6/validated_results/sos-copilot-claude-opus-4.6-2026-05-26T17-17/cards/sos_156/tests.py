"""Tests for SOS 156 — Oracle's Restoration."""

from __future__ import annotations

from cards.sos.sos_156.card_impl import OraclesRestoration
from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestOraclesRestorationProperties:
    """Static card data should match the SOS 156 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(OraclesRestoration(owner=None), Sorcery)

    def test_name(self) -> None:
        assert OraclesRestoration(owner=None).name == "Oracle's Restoration"

    def test_mana_cost(self) -> None:
        assert OraclesRestoration(owner=None).mana_cost == ManaCost.parse("{G}")


class TestOraclesRestorationTargeting:
    """get_targets() should require a creature you control."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = OraclesRestoration(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = OraclesRestoration(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD


class TestOraclesRestorationResolution:
    """on_resolve applies +1/+1 until end of turn, draws a card, gains 1 life."""

    def test_target_gets_plus_one_plus_one(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bear = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        set_board_state(game, 0, battlefield=[bear])

        spell = OraclesRestoration(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        # +1/+1 until end of turn
        assert bear.power == 3
        assert bear.toughness == 3

    def test_controller_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bear = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        # Put a card in library so draw can succeed
        filler = Creature(name="Filler", owner=p1, controller=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[bear], library=[filler])

        hand_before = len(game.get_hand(p1).get_all())
        spell = OraclesRestoration(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == hand_before + 1

    def test_controller_gains_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bear = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        set_board_state(game, 0, battlefield=[bear], life=20)

        spell = OraclesRestoration(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert p1.life == 21

    def test_no_target_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = OraclesRestoration(owner=p1, controller=p1)
        # No chosen_targets — should not raise
        spell.on_resolve(game)
