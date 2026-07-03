"""Tests for SOS 137 — Zealous Lorecaster.

A {5}{R} 4/4 Creature — Giant Sorcerer with ETB: return target instant or
sorcery card from your graveyard to your hand.
"""

from __future__ import annotations

from cards.sos.sos_137.card_impl import ZealousLorecaster
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestZealousLorecasterProperties:
    """Static card data should match the SOS 137 spec."""

    def test_is_creature(self) -> None:
        card = ZealousLorecaster(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ZealousLorecaster(owner=None)
        assert card.name == "Zealous Lorecaster"

    def test_mana_cost(self) -> None:
        card = ZealousLorecaster(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{R}")

    def test_power_toughness(self) -> None:
        card = ZealousLorecaster(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4


class TestZealousLorecasterETB:
    """When this creature enters, return target instant or sorcery from graveyard to hand."""

    def test_etb_returns_instant_from_graveyard_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]

        # Put an instant in the graveyard
        bolt = Instant(name="Lightning Bolt", owner=p1)
        bolt.card_types = {CardType.INSTANT}
        game.get_graveyard(p1).add(bolt)

        card = ZealousLorecaster(owner=p1, controller=p1)
        card.chosen_targets = [bolt]
        card.on_enter_battlefield(game)

        # The instant should now be in hand
        hand_cards = game.get_hand(p1).get_all()
        assert bolt in hand_cards

        # And removed from graveyard
        gy_cards = game.get_graveyard(p1).get_all()
        assert bolt not in gy_cards

    def test_etb_returns_sorcery_from_graveyard_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]

        # Put a sorcery in the graveyard
        spell = Sorcery(name="Divination", owner=p1)
        spell.card_types = {CardType.SORCERY}
        game.get_graveyard(p1).add(spell)

        card = ZealousLorecaster(owner=p1, controller=p1)
        card.chosen_targets = [spell]
        card.on_enter_battlefield(game)

        hand_cards = game.get_hand(p1).get_all()
        assert spell in hand_cards

    def test_etb_target_must_be_instant_or_sorcery(self) -> None:
        """The ETB trigger should only target instants/sorceries in graveyard."""
        game = create_game()
        p1 = game.players[0]

        card = ZealousLorecaster(owner=p1, controller=p1)
        # Check targeting requirements
        reqs = card.get_etb_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        req = reqs[0]
        assert req.zone == Zone.GRAVEYARD

        # Filter should accept instant
        instant = Instant(name="Shock", owner=p1)
        instant.card_types = {CardType.INSTANT}
        assert req.filter_fn(instant) is True

        # Filter should reject creature
        creature = Creature(name="Bear", owner=p1, base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is False

    def test_etb_no_target_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ZealousLorecaster(owner=p1, controller=p1)
        # No target — should not raise
        card.on_enter_battlefield(game)
