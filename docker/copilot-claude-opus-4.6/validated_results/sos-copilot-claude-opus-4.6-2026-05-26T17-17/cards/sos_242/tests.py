"""Tests for SOS 242 — Visionary's Dance.

Sorcery {5}{U}{R}
Create two 3/3 blue and red Elemental creature tokens with flying.
{2}, Discard this card: Look at the top two cards of your library.
Put one of them into your hand and the other into your graveyard.
"""

from __future__ import annotations

from cards.sos.sos_242.card_impl import VisionarysDance
from engine.card import Creature, Sorcery
from engine.types import Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestVisionarysDanceProperties:
    """Static card data should match the SOS 242 spec."""

    def test_name(self) -> None:
        card = VisionarysDance(owner=None)
        assert card.name == "Visionary's Dance"

    def test_mana_cost(self) -> None:
        card = VisionarysDance(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{U}{R}")

    def test_is_sorcery(self) -> None:
        card = VisionarysDance(owner=None)
        assert isinstance(card, Sorcery)


class TestVisionarysDanceTokenCreation:
    """Create two 3/3 blue and red Elemental creature tokens with flying."""

    def test_creates_two_tokens(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VisionarysDance(owner=p1, controller=p1)
        before = len(game.get_battlefield(p1).get_all())
        card.on_resolve(game)
        after = len(game.get_battlefield(p1).get_all())
        assert after - before == 2

    def test_tokens_are_3_3(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VisionarysDance(owner=p1, controller=p1)
        card.on_resolve(game)
        tokens = [
            c for c in game.get_battlefield(p1).get_all()
            if isinstance(c, Creature) and "Elemental" in getattr(c, "subtypes", set())
        ]
        assert len(tokens) == 2
        for tok in tokens:
            assert tok.base_power == 3
            assert tok.base_toughness == 3

    def test_tokens_have_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VisionarysDance(owner=p1, controller=p1)
        card.on_resolve(game)
        tokens = [
            c for c in game.get_battlefield(p1).get_all()
            if isinstance(c, Creature) and "Elemental" in getattr(c, "subtypes", set())
        ]
        for tok in tokens:
            assert Keyword.FLYING in tok.keywords


class TestVisionarysDanceChannelAbility:
    """Activated ability from hand: {2}, Discard this card: Look at the
    top two cards. Put one into hand, other into graveyard."""

    def test_channel_moves_one_card_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VisionarysDance(owner=p1, controller=p1)
        # Put two cards on top of library
        lib_card_1 = Creature(name="Card A", base_power=1, base_toughness=1)
        lib_card_2 = Creature(name="Card B", base_power=2, base_toughness=2)
        lib_card_1.owner = p1
        lib_card_2.owner = p1
        set_board_state(game, 0, hand=[card])
        p1.zones[Zone.LIBRARY].add(lib_card_1)
        p1.zones[Zone.LIBRARY].add(lib_card_2)
        # Activate the channel ability (choice index 0 = first card goes to hand)
        card.activate_channel(game, choice=0)
        hand_cards = p1.zones[Zone.HAND].get_all()
        graveyard_cards = p1.zones[Zone.GRAVEYARD].get_all()
        # One of the two library cards should be in hand, other in graveyard
        assert lib_card_1 in hand_cards or lib_card_2 in hand_cards
        assert lib_card_1 in graveyard_cards or lib_card_2 in graveyard_cards

    def test_channel_discards_this_card(self) -> None:
        """The card itself should end up in the graveyard after activation."""
        game = create_game()
        p1 = game.players[0]
        card = VisionarysDance(owner=p1, controller=p1)
        lib_card_1 = Creature(name="Card A", base_power=1, base_toughness=1)
        lib_card_2 = Creature(name="Card B", base_power=2, base_toughness=2)
        lib_card_1.owner = p1
        lib_card_2.owner = p1
        set_board_state(game, 0, hand=[card])
        p1.zones[Zone.LIBRARY].add(lib_card_1)
        p1.zones[Zone.LIBRARY].add(lib_card_2)
        card.activate_channel(game, choice=0)
        graveyard_cards = p1.zones[Zone.GRAVEYARD].get_all()
        assert card in graveyard_cards
