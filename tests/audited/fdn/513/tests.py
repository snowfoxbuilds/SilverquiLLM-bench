"""Audited tests for Quick Study (FDN collector number 513)."""

from __future__ import annotations

import pytest

from card_impl import QuickStudy

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)


from engine.card import CardImpl


@pytest.mark.basic
class TestQuickStudyProperties:
    def test_is_instant(self):
        card = QuickStudy()
        assert isinstance(card, Instant)

    def test_name(self):
        card = QuickStudy()
        assert card.name == "Quick Study"


@pytest.mark.ability
class TestQuickStudyResolution:
    def test_draws_two_cards(self):
        game = create_game()
        p1 = game.players[0]
        # Put cards in library
        for i in range(5):
            c = CardImpl(name=f"Card{i}", owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        spell = QuickStudy(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1, ManaType.COLORLESS: 2})
        initial_hand_size = len(list(p1.zones[Zone.HAND].get_all()))
        cast_spell(game, 0, "Quick Study")
        # Spell itself leaves hand, then 2 cards drawn
        final_hand_size = len(list(p1.zones[Zone.HAND].get_all()))
        assert final_hand_size == initial_hand_size - 1 + 2


@pytest.mark.basic
class TestQuickStudyNoTargets:
    def test_no_targets_required(self):
        game = create_game()
        card = QuickStudy()
        targets = card.get_targets(game)
        assert targets == []
