"""Tests for SOS 240 — Vibrant Outburst.

{U}{R} Instant
Vibrant Outburst deals 3 damage to any target. Tap up to one target creature.
"""

from __future__ import annotations

from cards.sos.sos_240.card_impl import VibrantOutburst
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from test_utils import create_game


class TestVibrantOutburstProperties:
    """Static card data should match the SOS 240 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(VibrantOutburst(owner=None), Instant)

    def test_name(self) -> None:
        assert VibrantOutburst(owner=None).name == "Vibrant Outburst"

    def test_mana_cost(self) -> None:
        assert VibrantOutburst(owner=None).mana_cost == ManaCost.parse("{U}{R}")


class TestVibrantOutburstTargeting:
    """get_targets() should have two target requirements: any target + creature."""

    def test_returns_two_target_requirements(self) -> None:
        game = create_game()
        reqs = VibrantOutburst(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 2

    def test_first_target_accepts_any(self) -> None:
        """First target (damage) accepts any target."""
        game = create_game()
        req = VibrantOutburst(owner=None).get_targets(game)[0]
        assert isinstance(req, TargetRequirement)
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True

    def test_second_target_accepts_creature(self) -> None:
        """Second target (tap) requires a creature."""
        game = create_game()
        req = VibrantOutburst(owner=None).get_targets(game)[1]
        assert isinstance(req, TargetRequirement)
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True


class TestVibrantOutburstResolution:
    """on_resolve deals 3 damage and taps up to one creature."""

    def test_deals_three_damage_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = VibrantOutburst(owner=p1, controller=p1)

        bear = Creature(
            name="Target Bear",
            owner=p1,
            controller=p1,
            base_power=4,
            base_toughness=4,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell.chosen_targets = [bear, None]  # second target optional
        spell.on_resolve(game)
        assert bear.damage_taken == 3

    def test_deals_three_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = VibrantOutburst(owner=p1, controller=p1)

        spell.chosen_targets = [p2, None]
        life_before = p2.life
        spell.on_resolve(game)
        assert p2.life == life_before - 3

    def test_taps_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = VibrantOutburst(owner=p1, controller=p1)

        blocker = Creature(
            name="Blocker",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        blocker.card_types = {CardType.CREATURE}
        blocker.tapped = False
        game.get_battlefield(p2).add(blocker)

        spell.chosen_targets = [p2, blocker]
        spell.on_resolve(game)
        assert blocker.tapped is True

    def test_no_tap_target_is_valid(self) -> None:
        """Can choose zero creatures to tap (up to one)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = VibrantOutburst(owner=p1, controller=p1)

        spell.chosen_targets = [p2, None]
        life_before = p2.life
        spell.on_resolve(game)
        # Should still deal damage without error
        assert p2.life == life_before - 3

    def test_no_target_is_noop(self) -> None:
        """Resolution with no valid target should not raise."""
        game = create_game()
        p1 = game.players[0]
        spell = VibrantOutburst(owner=p1, controller=p1)
        spell.on_resolve(game)
