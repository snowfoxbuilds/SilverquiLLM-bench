"""Tests for SOS 239 — Traumatic Critique.

{X}{U}{R} Instant
Traumatic Critique deals X damage to any target. Draw two cards, then discard a card.
"""

from __future__ import annotations

from cards.sos.sos_239.card_impl import TraumaticCritique
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from test_utils import create_game


class TestTraumaticCritiqueProperties:
    """Static card data should match the SOS 239 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(TraumaticCritique(owner=None), Instant)

    def test_name(self) -> None:
        assert TraumaticCritique(owner=None).name == "Traumatic Critique"

    def test_mana_cost(self) -> None:
        assert TraumaticCritique(owner=None).mana_cost == ManaCost.parse("{X}{U}{R}")


class TestTraumaticCritiqueTargeting:
    """get_targets() should advertise a single 'any target' requirement."""

    def test_returns_target_requirement(self) -> None:
        game = create_game()
        reqs = TraumaticCritique(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_accepts_creature(self) -> None:
        game = create_game()
        req = TraumaticCritique(owner=None).get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True

    def test_target_accepts_player(self) -> None:
        game = create_game()
        req = TraumaticCritique(owner=None).get_targets(game)[0]
        p1 = game.players[0]
        assert req.filter_fn(p1) is True


class TestTraumaticCritiqueResolution:
    """on_resolve deals X damage and draws 2, discards 1."""

    def test_deals_x_damage_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TraumaticCritique(owner=p1, controller=p1)

        bear = Creature(
            name="Target Bear",
            owner=p1,
            controller=p1,
            base_power=5,
            base_toughness=5,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell.chosen_targets = [bear]
        spell.x_value = 3
        spell.on_resolve(game)

        assert bear.damage_taken == 3

    def test_deals_x_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TraumaticCritique(owner=p1, controller=p1)

        spell.chosen_targets = [p2]
        spell.x_value = 4
        life_before = p2.life
        spell.on_resolve(game)

        assert p2.life == life_before - 4

    def test_draws_two_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put cards in library to draw
        for i in range(5):
            filler = Creature(name=f"Filler{i}", owner=p1, base_power=1, base_toughness=1)
            p1.zones[Zone.LIBRARY].add(filler)

        spell = TraumaticCritique(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.x_value = 0

        hand_before = len(p1.zones[Zone.HAND].get_all())
        spell.on_resolve(game)

        # Drew 2, discarded 1 → net +1 in hand
        hand_after = len(p1.zones[Zone.HAND].get_all())
        assert hand_after >= hand_before + 1

    def test_x_zero_deals_no_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TraumaticCritique(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.x_value = 0

        life_before = p2.life
        spell.on_resolve(game)
        assert p2.life == life_before

    def test_no_target_is_noop(self) -> None:
        """Resolution with no valid target should not raise."""
        game = create_game()
        p1 = game.players[0]
        spell = TraumaticCritique(owner=p1, controller=p1)
        spell.on_resolve(game)
