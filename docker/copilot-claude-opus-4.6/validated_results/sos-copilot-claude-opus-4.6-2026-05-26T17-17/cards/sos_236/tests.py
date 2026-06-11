"""Tests for SOS 236 — Suspend Aggression.

Suspend Aggression is a {1}{R}{W} Instant.
Oracle: Exile target nonland permanent and the top card of your library.
For each of those cards, its owner may play it until the end of their next turn.
"""

from __future__ import annotations

from cards.sos.sos_236.card_impl import SuspendAggression
from engine.card import Creature, Instant
from engine.types import (
    CardType,
    ManaCost,
    TargetRequirement,
    Zone,
)
from test_utils import create_game


class TestSuspendAggressionProperties:
    """Static card data should match the SOS 236 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(SuspendAggression(owner=None), Instant)

    def test_name(self) -> None:
        assert SuspendAggression(owner=None).name == "Suspend Aggression"

    def test_mana_cost(self) -> None:
        assert SuspendAggression(owner=None).mana_cost == ManaCost.parse("{1}{R}{W}")


class TestSuspendAggressionTargeting:
    """get_targets() should require one nonland permanent target."""

    def test_returns_target_requirement(self) -> None:
        game = create_game()
        reqs = SuspendAggression(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) >= 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = SuspendAggression(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD

    def test_target_rejects_land(self) -> None:
        """Lands should not be valid targets."""
        game = create_game()
        req = SuspendAggression(owner=None).get_targets(game)[0]
        from engine.card import CardImpl
        land = CardImpl(name="Forest")
        land.card_types = {CardType.LAND}
        assert req.filter_fn(land) is False

    def test_target_accepts_creature(self) -> None:
        game = create_game()
        req = SuspendAggression(owner=None).get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True


class TestSuspendAggressionResolution:
    """on_resolve exiles the target and top card of library, giving
    impulsive play access until end of owner's next turn."""

    def test_target_is_exiled(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = SuspendAggression(owner=p1, controller=p1)

        bear = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        # Bear should no longer be on the battlefield
        bf_cards = game.get_battlefield(p1).get_all()
        assert bear not in bf_cards

    def test_top_card_of_library_is_exiled(self) -> None:
        game = create_game()
        p1 = game.players[0]

        # Put a card on top of library
        filler = Creature(name="Filler", owner=p1, base_power=1, base_toughness=1)
        p1.zones[Zone.LIBRARY].add(filler)

        bear = Creature(
            name="Target Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = SuspendAggression(owner=p1, controller=p1)
        spell.chosen_targets = [bear]

        lib_count_before = len(p1.zones[Zone.LIBRARY].get_all())
        spell.on_resolve(game)
        lib_count_after = len(p1.zones[Zone.LIBRARY].get_all())

        # Library should lose a card (the top card was exiled)
        assert lib_count_after == lib_count_before - 1

    def test_no_target_is_noop(self) -> None:
        """Resolution with no valid target should not raise."""
        game = create_game()
        p1 = game.players[0]
        spell = SuspendAggression(owner=p1, controller=p1)
        spell.on_resolve(game)
