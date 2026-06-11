"""Tests for SOS 204 — Molten Note.

Sorcery {X}{R}{W}
Molten Note deals damage to target creature equal to the amount of mana spent
to cast this spell. Untap all creatures you control.
Flashback {6}{R}{W}
"""

from __future__ import annotations

import pytest

from cards.sos.sos_204.card_impl import MoltenNote
from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestMoltenNoteProperties:
    """Static card data should match the SOS 204 spec."""

    def test_is_sorcery(self) -> None:
        card = MoltenNote(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = MoltenNote(owner=None)
        assert card.name == "Molten Note"

    def test_mana_cost(self) -> None:
        card = MoltenNote(owner=None)
        assert card.mana_cost == ManaCost.parse("{X}{R}{W}")

    def test_has_flashback(self) -> None:
        card = MoltenNote(owner=None)
        assert card.keywords & Keyword.FLASHBACK


class TestMoltenNoteTargeting:
    """Targets a creature."""

    def test_requires_creature_target(self) -> None:
        game = create_game()
        card = MoltenNote(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) >= 1
        assert reqs[0].zone == Zone.BATTLEFIELD


class TestMoltenNoteResolution:
    """Deals damage equal to mana spent; untaps all your creatures."""

    def test_deals_damage_equal_to_mana_spent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MoltenNote(owner=p1, controller=p1)
        # Total mana spent = X + R + W. If X=3, total = 5
        card.mana_spent = 5
        card.x_value = 3
        target = Creature(name="Big Bear", owner=p2, controller=p2,
                          base_power=4, base_toughness=6)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        assert target.damage_marked == 5

    def test_deals_damage_with_x_zero(self) -> None:
        """With X=0, mana spent is just R+W = 2."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MoltenNote(owner=p1, controller=p1)
        card.mana_spent = 2
        card.x_value = 0
        target = Creature(name="Small Bear", owner=p2, controller=p2,
                          base_power=2, base_toughness=3)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        assert target.damage_marked == 2

    def test_untaps_all_creatures_you_control(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MoltenNote(owner=p1, controller=p1)
        card.mana_spent = 4
        card.x_value = 2
        # Create tapped creatures for p1
        c1 = Creature(name="Tapped 1", owner=p1, controller=p1, base_power=2, base_toughness=2)
        c1.is_tapped = True
        c2 = Creature(name="Tapped 2", owner=p1, controller=p1, base_power=3, base_toughness=3)
        c2.is_tapped = True
        game.get_battlefield(p1).add(c1)
        game.get_battlefield(p1).add(c2)
        # Target an opponent's creature
        target = Creature(name="Enemy", owner=p2, controller=p2,
                          base_power=5, base_toughness=5)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        # Both of p1's creatures should be untapped
        assert c1.is_tapped is False
        assert c2.is_tapped is False

    def test_does_not_untap_opponent_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MoltenNote(owner=p1, controller=p1)
        card.mana_spent = 3
        card.x_value = 1
        opp_creature = Creature(name="Opp Tapped", owner=p2, controller=p2,
                                base_power=2, base_toughness=2)
        opp_creature.is_tapped = True
        game.get_battlefield(p2).add(opp_creature)
        target = Creature(name="Target", owner=p2, controller=p2,
                          base_power=4, base_toughness=4)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        assert opp_creature.is_tapped is True


class TestMoltenNoteFlashback:
    """Flashback {6}{R}{W} — can be cast from graveyard."""

    def test_flashback_cost(self) -> None:
        card = MoltenNote(owner=None)
        assert card.flashback_cost == ManaCost.parse("{6}{R}{W}")

    def test_flashback_mana_spent_is_eight(self) -> None:
        """When cast for flashback {6}{R}{W}, total mana spent is 8."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MoltenNote(owner=p1, controller=p1)
        card.mana_spent = 8  # 6+R+W
        target = Creature(name="Target", owner=p2, controller=p2,
                          base_power=5, base_toughness=10)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        assert target.damage_marked == 8
