"""Tests for SOS 210 — Practiced Scrollsmith.

Creature — Dwarf Cleric (3/2) {R}{R/W}{W}
- First strike
- When this creature enters, exile target noncreature, nonland card from your graveyard.
  Until the end of your next turn, you may cast that card.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_210.card_impl import PracticedScrollsmith
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestPracticedScrollsmithProperties:
    """Static card properties match the spec."""

    def test_name(self) -> None:
        card = PracticedScrollsmith(owner=None)
        assert card.name == "Practiced Scrollsmith"

    def test_mana_cost(self) -> None:
        card = PracticedScrollsmith(owner=None)
        assert card.mana_cost == ManaCost.parse("{R}{R/W}{W}")

    def test_power_toughness(self) -> None:
        card = PracticedScrollsmith(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_is_creature(self) -> None:
        card = PracticedScrollsmith(owner=None)
        assert isinstance(card, Creature)

    def test_has_first_strike(self) -> None:
        card = PracticedScrollsmith(owner=None)
        assert Keyword.FIRST_STRIKE in card.keywords


class TestPracticedScrollsmithETB:
    """ETB: exile target noncreature nonland card from your GY, cast it until end of next turn."""

    def test_exiles_instant_from_own_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PracticedScrollsmith(owner=p1, controller=p1)

        target = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        target.card_types = {CardType.INSTANT}
        game.get_graveyard(p1).add(target)

        card.on_enter_battlefield(game, target=target)

        # Target should be exiled
        assert target not in game.get_graveyard(p1).get_all()
        assert target.zone == Zone.EXILE

    def test_cannot_target_creature_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PracticedScrollsmith(owner=p1, controller=p1)

        creature = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        game.get_graveyard(p1).add(creature)

        with pytest.raises(Exception):
            card.on_enter_battlefield(game, target=creature)

    def test_cannot_target_land_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PracticedScrollsmith(owner=p1, controller=p1)

        land = Creature(name="Mountain", owner=p1, controller=p1, base_power=0, base_toughness=0)
        land.card_types = {CardType.LAND}
        game.get_graveyard(p1).add(land)

        with pytest.raises(Exception):
            card.on_enter_battlefield(game, target=land)

    def test_cannot_target_opponent_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = PracticedScrollsmith(owner=p1, controller=p1)

        opp_spell = Instant(name="Counterspell", owner=p2, controller=p2)
        opp_spell.card_types = {CardType.INSTANT}
        game.get_graveyard(p2).add(opp_spell)

        with pytest.raises(Exception):
            card.on_enter_battlefield(game, target=opp_spell)

    def test_exiled_card_is_castable(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PracticedScrollsmith(owner=p1, controller=p1)

        target = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        target.card_types = {CardType.INSTANT}
        game.get_graveyard(p1).add(target)

        card.on_enter_battlefield(game, target=target)

        # The exiled card should be marked as castable
        assert target.can_be_cast is True

    def test_cast_permission_expires_end_of_next_turn(self) -> None:
        """The card can only be cast until end of your next turn."""
        game = create_game()
        p1 = game.players[0]
        card = PracticedScrollsmith(owner=p1, controller=p1)

        target = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        target.card_types = {CardType.INSTANT}
        game.get_graveyard(p1).add(target)

        card.on_enter_battlefield(game, target=target)

        # After expiry (simulated by advancing past next turn end)
        card.on_turn_end_cleanup(game, turns_passed=2)

        assert target.can_be_cast is False
