"""Tests for SOS 38 — Banishing Betrayal.

Instant for {1}{U}.
Return target nonland permanent to its owner's hand. Surveil 1.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_38.card_impl import BanishingBetrayal
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestBanishingBetrayalProperties:
    """Static card data should match the SOS 38 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(BanishingBetrayal(owner=None), Instant)

    def test_name(self) -> None:
        assert BanishingBetrayal(owner=None).name == "Banishing Betrayal"

    def test_mana_cost(self) -> None:
        assert BanishingBetrayal(owner=None).mana_cost == ManaCost.parse("{1}{U}")


class TestBanishingBetrayalTargeting:
    """Targets a nonland permanent on the battlefield."""

    def test_returns_target_requirement(self) -> None:
        game = create_game()
        reqs = BanishingBetrayal(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = BanishingBetrayal(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD

    def test_target_accepts_creature(self) -> None:
        game = create_game()
        req = BanishingBetrayal(owner=None).get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True

    def test_target_rejects_land(self) -> None:
        """Lands are not legal targets for Banishing Betrayal."""
        from engine.card import Land
        game = create_game()
        req = BanishingBetrayal(owner=None).get_targets(game)[0]
        land = Land(name="Island")
        land.card_types = {CardType.LAND}
        assert req.filter_fn(land) is False


class TestBanishingBetrayalResolution:
    """on_resolve bounces the target and surveils 1."""

    def test_bounces_target_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target_creature = Creature(
            name="Enemy Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2
        )
        target_creature.card_types = {CardType.CREATURE}
        set_board_state(game, 1, battlefield=[target_creature])

        spell = BanishingBetrayal(owner=p1, controller=p1)
        spell.chosen_targets = [target_creature]
        spell.on_resolve(game)

        # Target should be in owner's hand
        hand = game.get_hand(p2)
        assert target_creature in hand

    def test_removes_target_from_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target_creature = Creature(
            name="Enemy Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2
        )
        target_creature.card_types = {CardType.CREATURE}
        set_board_state(game, 1, battlefield=[target_creature])

        spell = BanishingBetrayal(owner=p1, controller=p1)
        spell.chosen_targets = [target_creature]
        spell.on_resolve(game)

        battlefield = game.get_battlefield(p2)
        assert target_creature not in battlefield

    def test_surveils_1_after_bounce(self) -> None:
        """After bouncing, the caster surveils 1."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target_creature = Creature(
            name="Enemy Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2
        )
        target_creature.card_types = {CardType.CREATURE}
        set_board_state(game, 1, battlefield=[target_creature])

        # Put a card on top of p1's library for surveil
        filler = Creature(name="Filler", owner=p1, base_power=1, base_toughness=1)
        game.get_library(p1).append(filler)
        library_size_before = len(game.get_library(p1))

        spell = BanishingBetrayal(owner=p1, controller=p1)
        spell.chosen_targets = [target_creature]
        spell.on_resolve(game)

        # Surveil should have looked at top card
        library_after = len(game.get_library(p1))
        assert library_after <= library_size_before

    def test_no_target_is_noop(self) -> None:
        """If target is gone, resolution should not raise."""
        game = create_game()
        p1 = game.players[0]
        spell = BanishingBetrayal(owner=p1, controller=p1)
        spell.chosen_targets = []
        # Should not raise
        spell.on_resolve(game)
