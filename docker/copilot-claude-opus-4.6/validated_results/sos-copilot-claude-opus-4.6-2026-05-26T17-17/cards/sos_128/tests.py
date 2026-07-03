"""Tests for SOS 128 — Rubble Rouser.

A 2R creature (1/4) with:
- ETB: may discard a card, if you do draw a card.
- {T}, Exile a card from graveyard: Add {R}. When you do, deals 1 damage to each opponent.
"""

from __future__ import annotations

from cards.sos.sos_128.card_impl import RubbleRouser
from engine.card import Creature
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestRubbleRouserProperties:
    """Static card data should match the SOS 128 spec."""

    def test_name(self) -> None:
        card = RubbleRouser(owner=None)
        assert card.name == "Rubble Rouser"

    def test_is_creature(self) -> None:
        card = RubbleRouser(owner=None)
        assert isinstance(card, Creature)

    def test_mana_cost(self) -> None:
        card = RubbleRouser(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{R}")

    def test_power_and_toughness(self) -> None:
        card = RubbleRouser(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 4


class TestRubbleRouserETB:
    """ETB trigger: may discard a card to draw a card (looting)."""

    def test_etb_discard_then_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RubbleRouser(owner=p1, controller=p1)
        # Give the player a hand card to discard
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[filler],
                        mana={ManaType.RED: 1, ManaType.COLORLESS: 2})
        # Put some cards in library for draw
        game.players[0].library = [
            Creature(name="LibCard", base_power=1, base_toughness=1)
        ]
        card.on_enter_battlefield(game, chose_discard=True)
        # After discarding 1 and drawing 1, hand size should remain same
        # The filler should be in graveyard
        graveyard_names = [c.name for c in game.get_graveyard(p1)]
        assert "Filler" in graveyard_names

    def test_etb_may_choose_not_to_discard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RubbleRouser(owner=p1, controller=p1)
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[filler])
        hand_size_before = len(game.get_hand(p1))
        card.on_enter_battlefield(game, chose_discard=False)
        # Hand should not change if we choose not to discard
        assert len(game.get_hand(p1)) == hand_size_before


class TestRubbleRouserManaAbility:
    """Tap + exile from graveyard: Add R, deal 1 to each opponent."""

    def test_tap_exile_adds_red_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RubbleRouser(owner=p1, controller=p1)
        # Put a card in graveyard to exile
        graveyard_card = Creature(name="Dead Thing", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[card], graveyard=[graveyard_card])
        card.tapped = False
        card.activate_mana_ability(game, exile_target=graveyard_card)
        # Card should now be tapped
        assert card.tapped is True
        # Graveyard card should be exiled (removed from graveyard)
        graveyard_names = [c.name for c in game.get_graveyard(p1)]
        assert "Dead Thing" not in graveyard_names

    def test_tap_exile_deals_1_damage_to_opponents(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RubbleRouser(owner=p1, controller=p1)
        graveyard_card = Creature(name="Dead Thing", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[card], graveyard=[graveyard_card])
        set_board_state(game, 1, life=20)
        card.tapped = False
        card.activate_mana_ability(game, exile_target=graveyard_card)
        # Opponent should have taken 1 damage
        assert p2.life == 19
