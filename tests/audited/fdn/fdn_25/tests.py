"""Audited tests for FDN 25 — Sun-Blessed Healer."""

from __future__ import annotations

from card_impl import SunBlessedHealer
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestSunBlessedHealerBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = SunBlessedHealer(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SunBlessedHealer(owner=None)
        assert card.name == "Sun-Blessed Healer"

    def test_mana_cost(self) -> None:
        card = SunBlessedHealer(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}")

    def test_power_toughness(self) -> None:
        card = SunBlessedHealer(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 1

    def test_has_lifelink(self) -> None:
        card = SunBlessedHealer(owner=None)
        assert Keyword.LIFELINK in card.keywords

    def test_subtypes(self) -> None:
        card = SunBlessedHealer(owner=None)
        assert "Human" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_not_kicked_by_default(self) -> None:
        card = SunBlessedHealer(owner=None)
        assert card.kicked is False


class TestSunBlessedHealerETB:
    """When enters, if kicked, return target nonland permanent MV <= 2 from graveyard."""

    def test_kicked_returns_creature_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(name="Bear", mana_cost=ManaCost.parse("{1}{G}"),
                          base_power=2, base_toughness=2, owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(target)
        healer = SunBlessedHealer(owner=p1, controller=p1)
        healer.kicked = True
        healer.chosen_targets = [target]
        game.get_battlefield(p1).add(healer)
        healer.on_resolve(game)
        assert game.get_battlefield(p1).contains(target)

    def test_not_kicked_does_not_return(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(name="Bear", mana_cost=ManaCost.parse("{1}{G}"),
                          base_power=2, base_toughness=2, owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(target)
        healer = SunBlessedHealer(owner=p1, controller=p1)
        healer.kicked = False
        healer.on_resolve(game)
        assert not game.get_battlefield(p1).contains(target)

    def test_kicked_no_targets_does_not_error(self) -> None:
        game = create_game()
        p1 = game.players[0]
        healer = SunBlessedHealer(owner=p1, controller=p1)
        healer.kicked = True
        healer.chosen_targets = []
        healer.on_resolve(game)  # Should not raise

    def test_get_targets_empty_when_not_kicked(self) -> None:
        game = create_game()
        p1 = game.players[0]
        healer = SunBlessedHealer(owner=p1, controller=p1)
        healer.kicked = False
        assert healer.get_targets(game) == []

    def test_get_targets_nonempty_when_kicked(self) -> None:
        game = create_game()
        p1 = game.players[0]
        healer = SunBlessedHealer(owner=p1, controller=p1)
        healer.kicked = True
        targets = healer.get_targets(game)
        assert len(targets) == 1
