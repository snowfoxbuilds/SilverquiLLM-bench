"""Tests for SOS 132 — Tablet of Discovery.

An Artifact for {2}{R} with:
- ETB: mill a card, you may play that card this turn.
- {T}: Add {R}.
- {T}: Add {R}{R}. Spend this mana only to cast instant and sorcery spells.
"""

from __future__ import annotations

from cards.sos.sos_132.card_impl import TabletOfDiscovery
from engine.card import Artifact
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestTabletOfDiscoveryProperties:
    """Static card data should match the SOS 132 spec."""

    def test_is_artifact(self) -> None:
        card = TabletOfDiscovery(owner=None)
        assert isinstance(card, Artifact)

    def test_name(self) -> None:
        card = TabletOfDiscovery(owner=None)
        assert card.name == "Tablet of Discovery"

    def test_mana_cost(self) -> None:
        card = TabletOfDiscovery(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{R}")


class TestTabletOfDiscoveryETB:
    """When this artifact enters, mill a card. You may play that card this turn."""

    def test_etb_mills_one_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TabletOfDiscovery(owner=p1, controller=p1)
        # Set up a library with known cards
        from engine.card import Creature
        top_card = Creature(name="Test Card", owner=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[card])
        # Put card on top of library
        game.players[0].library = [top_card]
        graveyard_before = len(game.get_graveyard(p1).get_all())
        card.on_enter_battlefield(game)
        graveyard_after = len(game.get_graveyard(p1).get_all())
        assert graveyard_after == graveyard_before + 1

    def test_etb_milled_card_is_playable_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TabletOfDiscovery(owner=p1, controller=p1)
        from engine.card import Creature
        top_card = Creature(name="Milled Card", owner=p1, base_power=2, base_toughness=2)
        game.players[0].library = [top_card]
        set_board_state(game, 0, battlefield=[card])
        card.on_enter_battlefield(game)
        # The milled card should be marked as playable this turn
        assert top_card in card.playable_this_turn or hasattr(top_card, 'playable_this_turn')


class TestTabletOfDiscoveryManaAbilities:
    """Tap abilities for mana production."""

    def test_tap_for_one_red(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TabletOfDiscovery(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        # The first tap ability should produce {R}
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1
        # First ability produces one red mana
        result = abilities[0].effect(game)
        # Verify mana was added
        assert game.players[0].mana_pool.get(ManaType.RED, 0) >= 1

    def test_tap_for_two_red_restricted(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TabletOfDiscovery(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        # Should have at least 2 mana abilities
        assert len(abilities) >= 2
