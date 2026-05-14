"""Audited tests for FDN 163 — Self-Reflection."""

from __future__ import annotations

from card_impl import SelfReflection
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from tests.test_utils import create_game


class TestSelfReflectionBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = SelfReflection(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = SelfReflection(owner=None)
        assert card.name == "Self-Reflection"

    def test_mana_cost(self) -> None:
        card = SelfReflection(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{U}{U}")

    def test_has_flashback_cost(self) -> None:
        card = SelfReflection(owner=None)
        assert hasattr(card, "flashback_cost")
        assert card.flashback_cost == ManaCost.parse("{3}{U}")


class TestSelfReflectionResolve:
    """Create a token copy of target creature you control."""

    def test_creates_token_copy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        spell = SelfReflection(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        bear_count = sum(1 for c in bf if getattr(c, "name", "") == "Bear")
        assert bear_count >= 2

    def test_token_is_marked_as_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        spell = SelfReflection(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        assert len(tokens) >= 1

    def test_no_target_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = SelfReflection(owner=p1, controller=p1)
        spell.chosen_targets = [None]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        assert len(bf) == 0
