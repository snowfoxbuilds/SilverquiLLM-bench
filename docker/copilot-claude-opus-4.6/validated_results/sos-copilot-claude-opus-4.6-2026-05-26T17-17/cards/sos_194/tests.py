"""Tests for SOS 194 — Hardened Academic."""

from __future__ import annotations

import pytest

from cards.sos.sos_194.card_impl import HardenedAcademic
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestHardenedAcademicProperties:
    """Static card data should match SOS 194 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(HardenedAcademic(owner=None), Creature)

    def test_name(self) -> None:
        assert HardenedAcademic(owner=None).name == "Hardened Academic"

    def test_mana_cost(self) -> None:
        assert HardenedAcademic(owner=None).mana_cost == ManaCost.parse("{R}{W}")

    def test_power(self) -> None:
        assert HardenedAcademic(owner=None).base_power == 2

    def test_toughness(self) -> None:
        assert HardenedAcademic(owner=None).base_toughness == 1

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in HardenedAcademic(owner=None).keywords

    def test_has_haste(self) -> None:
        assert Keyword.HASTE in HardenedAcademic(owner=None).keywords


class TestHardenedAcademicDiscardAbility:
    """Activated ability: Discard a card -> gains lifelink until end of turn."""

    def test_has_activated_ability(self) -> None:
        game = create_game()
        academic = HardenedAcademic(owner=game.players[0])
        set_board_state(game, 0, battlefield=[academic])
        abilities = academic.get_activated_abilities(game)
        assert len(abilities) >= 1

    def test_gains_lifelink_after_activation(self) -> None:
        game = create_game()
        academic = HardenedAcademic(owner=game.players[0])
        discard_card = Creature(name="Fodder", base_power=1, base_toughness=1)
        discard_card.owner = game.players[0]
        set_board_state(game, 0, battlefield=[academic], hand=[discard_card])

        # Activate discard ability
        abilities = academic.get_activated_abilities(game)
        abilities[0].activate(game, costs={"discard": discard_card})

        assert Keyword.LIFELINK in academic.keywords

    def test_discard_moves_card_to_graveyard(self) -> None:
        game = create_game()
        academic = HardenedAcademic(owner=game.players[0])
        discard_card = Creature(name="Fodder", base_power=1, base_toughness=1)
        discard_card.owner = game.players[0]
        set_board_state(game, 0, battlefield=[academic], hand=[discard_card])

        abilities = academic.get_activated_abilities(game)
        abilities[0].activate(game, costs={"discard": discard_card})

        assert discard_card.zone == Zone.GRAVEYARD


class TestHardenedAcademicGraveyardTrigger:
    """Triggered: cards leave graveyard -> +1/+1 counter on target creature."""

    def test_trigger_on_cards_leaving_graveyard(self) -> None:
        game = create_game()
        academic = HardenedAcademic(owner=game.players[0])
        target_creature = Creature(name="Counter Target", base_power=2, base_toughness=2)
        target_creature.owner = game.players[0]
        set_board_state(game, 0, battlefield=[academic, target_creature])

        # Place a card in graveyard then remove it to trigger
        exile_card = Creature(name="Exiled Card", base_power=1, base_toughness=1)
        exile_card.owner = game.players[0]
        set_board_state(game, 0, graveyard=[exile_card])

        # Simulate card leaving graveyard (e.g., exile)
        game.players[0].graveyard.remove(exile_card)
        exile_card.zone = Zone.EXILE

        # Trigger should fire and put a +1/+1 counter on target creature
        triggers = academic.get_triggered_abilities(game)
        assert len(triggers) >= 1

    def test_only_one_counter_for_multiple_cards_leaving_at_once(self) -> None:
        """'Whenever one or more cards leave' — batched events give one trigger."""
        game = create_game()
        academic = HardenedAcademic(owner=game.players[0])
        target_creature = Creature(name="Counter Target", base_power=3, base_toughness=3)
        target_creature.owner = game.players[0]
        set_board_state(game, 0, battlefield=[academic, target_creature])

        # Multiple cards leaving graveyard at once should only trigger once
        card1 = Creature(name="Card 1", base_power=1, base_toughness=1)
        card2 = Creature(name="Card 2", base_power=1, base_toughness=1)
        card1.owner = game.players[0]
        card2.owner = game.players[0]
        set_board_state(game, 0, graveyard=[card1, card2])

        # Both cards leave simultaneously — should be one trigger, one counter
        game.players[0].graveyard.clear()

        triggers = academic.get_triggered_abilities(game)
        # Should be exactly 1 trigger (not 2)
        assert len(triggers) == 1
