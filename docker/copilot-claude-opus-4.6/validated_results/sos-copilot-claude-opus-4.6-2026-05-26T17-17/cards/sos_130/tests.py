"""Tests for SOS 130 — Steal the Show.

Sorcery (2R). Choose one or both:
- Target player discards any number of cards, then draws that many.
- Deals damage equal to # instant/sorcery cards in your graveyard to target creature/planeswalker.
"""

from __future__ import annotations

from cards.sos.sos_130.card_impl import StealTheShow
from engine.card import Creature, Sorcery, Instant
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestStealTheShowProperties:
    """Static card data should match the SOS 130 spec."""

    def test_name(self) -> None:
        card = StealTheShow(owner=None)
        assert card.name == "Steal the Show"

    def test_is_sorcery(self) -> None:
        card = StealTheShow(owner=None)
        assert isinstance(card, Sorcery)

    def test_mana_cost(self) -> None:
        card = StealTheShow(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{R}")


class TestStealTheShowModeOne:
    """Mode 1: Target player discards any number of cards, then draws that many."""

    def test_player_discards_and_draws_equal_number(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = StealTheShow(owner=p1, controller=p1)
        # Give target player hand cards
        hand_cards = [
            Creature(name=f"HandCard{i}", base_power=1, base_toughness=1)
            for i in range(3)
        ]
        lib_cards = [
            Creature(name=f"LibCard{i}", base_power=1, base_toughness=1)
            for i in range(5)
        ]
        set_board_state(game, 0, hand=hand_cards)
        game.players[0].library = lib_cards
        # Choose mode 1, target self, discard 2 cards
        spell.chosen_modes = [1]
        spell.chosen_targets = [p1]
        spell.discard_count = 2
        spell.on_resolve(game)
        # Should still have 3 cards in hand (discarded 2, drew 2, kept 1 original)
        assert len(game.get_hand(p1)) == 3

    def test_discard_zero_draws_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = StealTheShow(owner=p1, controller=p1)
        hand_cards = [
            Creature(name="Card1", base_power=1, base_toughness=1)
        ]
        set_board_state(game, 0, hand=hand_cards)
        spell.chosen_modes = [1]
        spell.chosen_targets = [p1]
        spell.discard_count = 0
        spell.on_resolve(game)
        # Hand should remain unchanged
        assert len(game.get_hand(p1)) == 1


class TestStealTheShowModeTwo:
    """Mode 2: Deal damage equal to instant/sorcery cards in graveyard."""

    def test_deals_damage_equal_to_instant_sorcery_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = StealTheShow(owner=p1, controller=p1)
        # Put instant/sorcery cards in graveyard
        instant1 = Instant(name="Bolt1", owner=p1)
        instant1.card_types = {CardType.INSTANT}
        sorcery1 = Sorcery(name="Rite1", owner=p1)
        sorcery1.card_types = {CardType.SORCERY}
        creature1 = Creature(name="Dead Bear", base_power=2, base_toughness=2)
        creature1.card_types = {CardType.CREATURE}
        set_board_state(game, 0, graveyard=[instant1, sorcery1, creature1])
        # Target enemy creature with 5 toughness
        target = Creature(name="BigBoy", owner=game.players[1],
                          controller=game.players[1],
                          base_power=3, base_toughness=5)
        set_board_state(game, 1, battlefield=[target])
        spell.chosen_modes = [2]
        spell.chosen_targets = [target]
        spell.on_resolve(game)
        # Should deal 2 damage (1 instant + 1 sorcery in graveyard)
        assert target.damage_taken == 2

    def test_zero_instants_sorceries_deals_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = StealTheShow(owner=p1, controller=p1)
        # Only creatures in graveyard
        creature1 = Creature(name="Dead Bear", base_power=2, base_toughness=2)
        creature1.card_types = {CardType.CREATURE}
        set_board_state(game, 0, graveyard=[creature1])
        target = Creature(name="Target", owner=game.players[1],
                          controller=game.players[1],
                          base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target])
        spell.chosen_modes = [2]
        spell.chosen_targets = [target]
        spell.on_resolve(game)
        # Should deal 0 damage
        assert target.damage_taken == 0


class TestStealTheShowBothModes:
    """Both modes chosen together."""

    def test_both_modes_apply(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = StealTheShow(owner=p1, controller=p1)
        # Setup graveyard with instants/sorceries
        instant1 = Instant(name="Bolt1", owner=p1)
        instant1.card_types = {CardType.INSTANT}
        set_board_state(game, 0, graveyard=[instant1])
        # Hand for mode 1
        hand_cards = [
            Creature(name=f"H{i}", base_power=1, base_toughness=1)
            for i in range(2)
        ]
        set_board_state(game, 0, hand=hand_cards)
        game.players[0].library = [
            Creature(name=f"L{i}", base_power=1, base_toughness=1)
            for i in range(5)
        ]
        # Target creature for mode 2
        target = Creature(name="Victim", owner=p2, controller=p2,
                          base_power=2, base_toughness=3)
        set_board_state(game, 1, battlefield=[target])
        spell.chosen_modes = [1, 2]
        spell.chosen_targets = [p1, target]
        spell.discard_count = 1
        spell.on_resolve(game)
        # Mode 2: should deal 1 damage (1 instant in graveyard)
        assert target.damage_taken >= 1
