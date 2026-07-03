"""Tests for SOS 64 — Procrastinate."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_64.card_impl import Procrastinate
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.game import untap
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


def _stun_count(permanent: Creature) -> int:
    return max(permanent.counters.get("stun", 0), getattr(permanent, "stun_counters", 0))


class TestProcrastinateProperties:
    """Static card data should match the SOS 64 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(Procrastinate(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = Procrastinate(owner=None)
        assert card.name == "Procrastinate"
        assert card.mana_cost == ManaCost.parse("{X}{U}")


class TestProcrastinateTargeting:
    """Procrastinate should target a creature on the battlefield."""

    def test_returns_a_single_creature_target_requirement(self) -> None:
        game = create_game()
        reqs = Procrastinate(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = Procrastinate(owner=None).get_targets(game)[0]
        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Campus Notes")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestProcrastinateResolution:
    """Procrastinate should tap the target and add twice X stun counters."""

    def test_x_zero_still_taps_the_target_but_adds_no_stun_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Distracted Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = Procrastinate(owner=p1, controller=p1)
        spell.x_value = 0  # type: ignore[attr-defined]
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert target.is_tapped is True
        assert _stun_count(target) == 0

    def test_x_three_taps_the_target_and_adds_six_stun_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Overdue Student",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = Procrastinate(owner=p1, controller=p1)
        spell.x_value = 3  # type: ignore[attr-defined]
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert target.is_tapped is True
        assert _stun_count(target) == 6

    def test_a_stunned_target_stays_tapped_when_it_next_tries_to_untap(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Late for Class",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = Procrastinate(owner=p1, controller=p1)
        spell.x_value = 2  # type: ignore[attr-defined]
        spell.chosen_targets = [target]

        spell.on_resolve(game)
        untapped = untap(game, target)

        assert untapped is False
        assert target.is_tapped is True
        assert _stun_count(target) == 3
