"""Audited tests for FDN 241 — Heroic Reinforcements."""

from __future__ import annotations

from card_impl import HeroicReinforcements
from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost
from tests.test_utils import create_game


class TestHeroicReinforcementsBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = HeroicReinforcements(owner=None)
        assert card.name == "Heroic Reinforcements"

    def test_mana_cost(self) -> None:
        card = HeroicReinforcements(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{R}{W}")

    def test_is_sorcery(self) -> None:
        card = HeroicReinforcements(owner=None)
        assert isinstance(card, Sorcery)


class TestHeroicReinforcementsResolve:
    """Create 2 tokens, pump +1/+1 and haste."""

    def test_creates_two_soldier_tokens(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = HeroicReinforcements(owner=p1, controller=p1)
        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, "is_token", False)]
        assert len(tokens) == 2
        for t in tokens:
            assert t.name == "Soldier"

    def test_grants_plus_1_plus_1(self) -> None:
        game = create_game()
        p1 = game.players[0]
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)
        spell = HeroicReinforcements(owner=p1, controller=p1)
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c1.modified_power == 3
        assert c1.modified_toughness == 3

    def test_grants_haste(self) -> None:
        game = create_game()
        p1 = game.players[0]
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)
        spell = HeroicReinforcements(owner=p1, controller=p1)
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.HASTE & c1.keywords

