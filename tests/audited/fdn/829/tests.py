"""Audited tests for Inscription of Insight (FDN — synthetic dir 829)."""
from __future__ import annotations
import pytest
from card_impl import InscriptionOfInsight
from engine.card import Sorcery
from engine.types import ManaCost


@pytest.mark.basic
class TestInscriptionOfInsightBasic:
    def test_is_sorcery(self) -> None:
        card = InscriptionOfInsight()
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = InscriptionOfInsight()
        assert card.name == "Inscription of Insight"

    def test_mana_cost(self) -> None:
        card = InscriptionOfInsight()
        assert card.mana_cost == ManaCost.parse("{3}{U}")


@pytest.mark.ability
class TestInscriptionOfInsightModes:
    def test_has_three_modes(self) -> None:
        card = InscriptionOfInsight()
        modes = card.get_modes()
        assert len(modes) == 3

    def test_mode_names(self) -> None:
        card = InscriptionOfInsight()
        modes = card.get_modes()
        names = [m.name for m in modes]
        assert "Bounce" in names
        assert "Draw" in names
        assert "Token" in names


@pytest.mark.rules
class TestInscriptionOfInsightResolve:
    def test_bounce_mode_returns_creature_to_hand(self) -> None:
        """Mode 0: return target creature to owner's hand."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        p = game.players[0]
        target = Creature(name="Bounced", owner=p, base_power=1, base_toughness=1)
        target.controller = p
        set_board_state(game, 0, battlefield=[target])
        card = InscriptionOfInsight(owner=p)
        card.controller = p
        card.chosen_modes = [0]
        card.chosen_targets = [target]
        card.on_resolve(game)
        assert not game.get_battlefield(p).contains(target)
        hand_names = [c.name for c in p.zones[Zone.HAND].get_all()]
        assert "Bounced" in hand_names
