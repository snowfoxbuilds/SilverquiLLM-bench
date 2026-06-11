"""Tests for SOS 22 — Interjection."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_22.card_impl import Interjection
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestInterjectionProperties:
    """Static card data should match the SOS 22 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(Interjection(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = Interjection(owner=None)
        assert card.name == "Interjection"
        assert card.mana_cost == ManaCost.parse("{W}")


class TestInterjectionTargeting:
    """Interjection should target a single creature on the battlefield."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = Interjection(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_non_creatures(self) -> None:
        game = create_game()
        req = Interjection(owner=None).get_targets(game)[0]

        creature = Creature(name="Helpful Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Not Actually A Creature")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestInterjectionResolution:
    """Interjection should grant +2/+2 and first strike until end of turn."""

    def test_target_gets_plus_two_plus_two_and_first_strike(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Valiant Student",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(target)
        card = Interjection(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.on_resolve(game)

        assert target.power == 4
        assert target.toughness == 4
        assert Keyword.FIRST_STRIKE in target.keywords

    def test_granted_bonus_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Valiant Student",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(target)
        card = Interjection(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.on_resolve(game)
        assert target.power == 4
        assert Keyword.FIRST_STRIKE in target.keywords

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert target.power == 2
        assert target.toughness == 2
        assert Keyword.FIRST_STRIKE not in target.keywords

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Valiant Student",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(target)

        Interjection(owner=p1, controller=p1).on_resolve(game)

        assert target.power == 2
        assert target.toughness == 2
        assert Keyword.FIRST_STRIKE not in target.keywords
