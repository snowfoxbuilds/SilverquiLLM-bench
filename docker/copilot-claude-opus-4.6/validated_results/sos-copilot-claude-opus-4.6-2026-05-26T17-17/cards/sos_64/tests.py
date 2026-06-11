"""Tests for SOS 64 — Procrastinate.

A sorcery for {X}{U} that taps target creature and puts twice X stun counters on it.
"""

from __future__ import annotations

from cards.sos.sos_64.card_impl import Procrastinate
from engine.card import Creature, Sorcery
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class TestProcrastinateProperties:
    """Static card data should match the SOS 64 spec."""

    def test_is_sorcery(self) -> None:
        card = Procrastinate(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        assert Procrastinate(owner=None).name == "Procrastinate"

    def test_mana_cost(self) -> None:
        assert Procrastinate(owner=None).mana_cost == ManaCost.parse("{X}{U}")


class TestProcrastinateTargeting:
    """Targets a single creature."""

    def test_requires_creature_target(self) -> None:
        game = create_game()
        card = Procrastinate(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_accepts_creature(self) -> None:
        game = create_game()
        card = Procrastinate(owner=None)
        req = card.get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True


class TestProcrastinateResolution:
    """on_resolve taps target and puts 2X stun counters on it."""

    def test_taps_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        target.tapped = False
        game.get_battlefield(p2).add(target)

        spell = Procrastinate(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.x_value = 2
        spell.on_resolve(game)
        assert target.tapped is True

    def test_puts_twice_x_stun_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        target.tapped = False
        target.stun_counters = 0
        game.get_battlefield(p2).add(target)

        spell = Procrastinate(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.x_value = 3
        spell.on_resolve(game)
        assert target.stun_counters == 6  # 2 * 3 = 6

    def test_x_zero_taps_but_no_stun_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        target.tapped = False
        target.stun_counters = 0
        game.get_battlefield(p2).add(target)

        spell = Procrastinate(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.x_value = 0
        spell.on_resolve(game)
        assert target.tapped is True
        assert target.stun_counters == 0

    def test_x_one_puts_two_stun_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        target.tapped = False
        target.stun_counters = 0
        game.get_battlefield(p2).add(target)

        spell = Procrastinate(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.x_value = 1
        spell.on_resolve(game)
        assert target.stun_counters == 2
