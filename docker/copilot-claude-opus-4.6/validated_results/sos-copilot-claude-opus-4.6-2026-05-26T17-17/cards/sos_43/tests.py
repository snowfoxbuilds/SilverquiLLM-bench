"""Tests for SOS 43 — Divergent Equation.

Divergent Equation costs {X}{X}{U}. Returns up to X target instant/sorcery
cards from your graveyard to hand. Then exiles itself.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_43.card_impl import DivergentEquation
from engine.card import Instant, Sorcery
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class TestDivergentEquationProperties:
    """Static card data should match the SOS 43 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(DivergentEquation(owner=None), Instant)

    def test_name(self) -> None:
        assert DivergentEquation(owner=None).name == "Divergent Equation"

    def test_mana_cost(self) -> None:
        assert DivergentEquation(owner=None).mana_cost == ManaCost.parse("{X}{X}{U}")


class TestDivergentEquationResolution:
    """on_resolve returns instant/sorcery cards from graveyard to hand."""

    def test_returns_instants_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}
        set_board_state(game, 0, graveyard=[bolt])

        spell = DivergentEquation(owner=p1, controller=p1)
        spell.x_value = 1
        spell.chosen_targets = [bolt]
        spell.on_resolve(game)

        # bolt should be in hand now
        hand_names = [c.name for c in game.get_hand(p1)]
        assert "Lightning Bolt" in hand_names

    def test_returns_sorceries_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]

        sorc = Sorcery(name="Divination", owner=p1, controller=p1)
        sorc.card_types = {CardType.SORCERY}
        set_board_state(game, 0, graveyard=[sorc])

        spell = DivergentEquation(owner=p1, controller=p1)
        spell.x_value = 1
        spell.chosen_targets = [sorc]
        spell.on_resolve(game)

        hand_names = [c.name for c in game.get_hand(p1)]
        assert "Divination" in hand_names

    def test_returns_multiple_cards_with_x_equals_2(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}
        sorc = Sorcery(name="Divination", owner=p1, controller=p1)
        sorc.card_types = {CardType.SORCERY}
        set_board_state(game, 0, graveyard=[bolt, sorc])

        spell = DivergentEquation(owner=p1, controller=p1)
        spell.x_value = 2
        spell.chosen_targets = [bolt, sorc]
        spell.on_resolve(game)

        hand_names = [c.name for c in game.get_hand(p1)]
        assert "Lightning Bolt" in hand_names
        assert "Divination" in hand_names

    def test_exiles_itself_after_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}
        set_board_state(game, 0, graveyard=[bolt])

        spell = DivergentEquation(owner=p1, controller=p1)
        spell.x_value = 1
        spell.chosen_targets = [bolt]
        spell.on_resolve(game)

        # Divergent Equation should be in exile
        exile_names = [c.name for c in game.get_exile(p1)]
        assert "Divergent Equation" in exile_names

    def test_x_zero_returns_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}
        set_board_state(game, 0, graveyard=[bolt])

        spell = DivergentEquation(owner=p1, controller=p1)
        spell.x_value = 0
        spell.chosen_targets = []
        spell.on_resolve(game)

        # Bolt stays in graveyard
        gy_names = [c.name for c in game.get_graveyard(p1)]
        assert "Lightning Bolt" in gy_names
