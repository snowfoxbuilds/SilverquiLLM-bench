"""Tests for SOS 203 — Mind Roots.

Sorcery {1}{B}{G}
Target player discards two cards. Put up to one land card discarded this way
onto the battlefield tapped under your control.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_203.card_impl import MindRoots
from engine.card import Creature, Sorcery, CardImpl
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestMindRootsProperties:
    """Static card data should match the SOS 203 spec."""

    def test_is_sorcery(self) -> None:
        card = MindRoots(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = MindRoots(owner=None)
        assert card.name == "Mind Roots"

    def test_mana_cost(self) -> None:
        card = MindRoots(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{G}")


class TestMindRootsTargeting:
    """Targets a player."""

    def test_requires_player_target(self) -> None:
        game = create_game()
        card = MindRoots(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) >= 1


class TestMindRootsResolution:
    """Target player discards two; put up to one discarded land onto BF tapped."""

    def test_target_player_discards_two_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MindRoots(owner=p1, controller=p1)
        # Give p2 three cards in hand
        for i in range(3):
            c = Creature(name=f"Victim Card {i}", owner=p2, base_power=1, base_toughness=1)
            game.get_hand(p2).add(c)
        card.chosen_targets = [p2]
        hand_before = len(game.get_hand(p2).get_all())
        card.on_resolve(game)
        hand_after = len(game.get_hand(p2).get_all())
        assert hand_after == hand_before - 2

    def test_discards_only_one_if_player_has_one_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MindRoots(owner=p1, controller=p1)
        # Give p2 only one card
        c = Creature(name="Lone Card", owner=p2, base_power=1, base_toughness=1)
        game.get_hand(p2).add(c)
        card.chosen_targets = [p2]
        card.on_resolve(game)
        hand_after = len(game.get_hand(p2).get_all())
        assert hand_after == 0

    def test_land_discarded_goes_to_battlefield_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MindRoots(owner=p1, controller=p1)
        # Create a land card in p2's hand
        land = CardImpl(owner=p2, controller=p2)
        land.name = "Forest"
        land.card_types = {CardType.LAND}
        filler = Creature(name="Filler", owner=p2, base_power=1, base_toughness=1)
        game.get_hand(p2).add(land)
        game.get_hand(p2).add(filler)
        card.chosen_targets = [p2]
        card.on_resolve(game)
        # The land should be on p1's battlefield (under your control), tapped
        bf = game.get_battlefield(p1).get_all()
        lands = [c for c in bf if c.name == "Forest"]
        assert len(lands) == 1
        assert lands[0].is_tapped is True

    def test_land_goes_under_casters_control(self) -> None:
        """Land goes under the caster's control, not the target's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MindRoots(owner=p1, controller=p1)
        land = CardImpl(owner=p2, controller=p2)
        land.name = "Swamp"
        land.card_types = {CardType.LAND}
        filler = Creature(name="Filler", owner=p2, base_power=1, base_toughness=1)
        game.get_hand(p2).add(land)
        game.get_hand(p2).add(filler)
        card.chosen_targets = [p2]
        card.on_resolve(game)
        # Land on p1's battlefield
        bf_p1 = game.get_battlefield(p1).get_all()
        bf_p2 = game.get_battlefield(p2).get_all()
        assert any(c.name == "Swamp" for c in bf_p1)
        assert not any(c.name == "Swamp" for c in bf_p2)

    def test_no_land_discarded_nothing_put_on_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MindRoots(owner=p1, controller=p1)
        # Only non-land cards
        for i in range(2):
            c = Creature(name=f"Nonland {i}", owner=p2, base_power=1, base_toughness=1)
            game.get_hand(p2).add(c)
        card.chosen_targets = [p2]
        card.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        assert len(bf) == 0

    def test_up_to_one_land_when_two_lands_discarded(self) -> None:
        """If both discarded cards are lands, only put up to one on battlefield."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MindRoots(owner=p1, controller=p1)
        land1 = CardImpl(owner=p2, controller=p2)
        land1.name = "Forest"
        land1.card_types = {CardType.LAND}
        land2 = CardImpl(owner=p2, controller=p2)
        land2.name = "Mountain"
        land2.card_types = {CardType.LAND}
        game.get_hand(p2).add(land1)
        game.get_hand(p2).add(land2)
        card.chosen_targets = [p2]
        card.on_resolve(game)
        # At most one land on p1's battlefield
        bf = game.get_battlefield(p1).get_all()
        lands_on_bf = [c for c in bf if CardType.LAND in getattr(c, 'card_types', set())]
        assert len(lands_on_bf) <= 1
