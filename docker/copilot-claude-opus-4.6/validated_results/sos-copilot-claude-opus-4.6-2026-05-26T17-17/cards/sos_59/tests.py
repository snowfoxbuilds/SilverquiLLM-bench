"""Tests for SOS 59 — Matterbending Mage."""

from __future__ import annotations

import pytest

from cards.sos.sos_59.card_impl import MatterbendingMage
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestMatterbendingMageProperties:
    """Static card data should match the SOS 59 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(MatterbendingMage(owner=None), Creature)

    def test_name(self) -> None:
        assert MatterbendingMage(owner=None).name == "Matterbending Mage"

    def test_mana_cost(self) -> None:
        assert MatterbendingMage(owner=None).mana_cost == ManaCost.parse("{2}{U}")

    def test_power_and_toughness(self) -> None:
        card = MatterbendingMage(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes_include_human_wizard(self) -> None:
        card = MatterbendingMage(owner=None)
        assert "Human" in card.subtypes
        assert "Wizard" in card.subtypes


class TestMatterbendingMageETB:
    """When this creature enters, return up to one other target creature to hand."""

    def test_bounces_target_creature_on_enter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Enemy Bear", owner=p2, controller=p2,
                          base_power=2, base_toughness=2)
        target.card_types = {CardType.CREATURE}
        set_board_state(game, 1, battlefield=[target])

        mage = MatterbendingMage(owner=p1, controller=p1)
        mage.chosen_targets = [target]
        mage.on_enter_battlefield(game)

        # Target should be returned to owner's hand
        assert target.zone == Zone.HAND

    def test_up_to_one_allows_no_target(self) -> None:
        """'Up to one' means you can choose zero targets — no-op is valid."""
        game = create_game()
        p1 = game.players[0]

        mage = MatterbendingMage(owner=p1, controller=p1)
        mage.chosen_targets = []
        # Should not raise
        mage.on_enter_battlefield(game)

    def test_cannot_target_self(self) -> None:
        """Must target 'another' creature — cannot bounce itself."""
        game = create_game()
        p1 = game.players[0]

        mage = MatterbendingMage(owner=p1, controller=p1)
        mage.card_types = {CardType.CREATURE}
        set_board_state(game, 0, battlefield=[mage])

        reqs = mage.get_targets(game)
        # The filter should reject self
        assert len(reqs) >= 1
        assert reqs[0].filter_fn(mage) is False


class TestMatterbendingMageUnblockable:
    """Whenever you cast a spell with {X} in its mana cost, can't be blocked."""

    def test_becomes_unblockable_after_x_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]

        mage = MatterbendingMage(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[mage])

        # Simulate casting a spell with X in its cost
        mage.on_x_spell_cast(game)

        assert mage.cant_be_blocked is True

    def test_unblockable_lasts_only_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]

        mage = MatterbendingMage(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[mage])

        mage.on_x_spell_cast(game)
        assert mage.cant_be_blocked is True

        # At end of turn / cleanup, the effect should expire
        game.end_turn()
        assert mage.cant_be_blocked is False
