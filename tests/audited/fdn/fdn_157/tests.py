"""Audited tests for FDN 157 — Lightshell Duo."""

from __future__ import annotations

from card_impl import LightshellDuo
from engine.card import CardImpl, Creature
from engine.types import Keyword, ManaCost, Zone
from tests.test_utils import create_game


class TestLightshellDuoBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = LightshellDuo(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = LightshellDuo(owner=None)
        assert card.name == "Lightshell Duo"

    def test_mana_cost(self) -> None:
        card = LightshellDuo(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{U}")

    def test_power_toughness(self) -> None:
        card = LightshellDuo(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_has_prowess(self) -> None:
        card = LightshellDuo(owner=None)
        assert Keyword.PROWESS in card.keywords

    def test_subtypes(self) -> None:
        card = LightshellDuo(owner=None)
        subtypes = card.subtypes
        assert "Otter" in subtypes


class TestLightshellDuoSurveil:
    """When this creature enters, surveil 2."""

    def test_surveil_puts_card_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        duo = LightshellDuo(owner=p1, controller=p1)
        duo.controller = p1
        # Put cards in library
        c1 = CardImpl(name="Card1", owner=p1)
        c2 = CardImpl(name="Card2", owner=p1)
        p1.zones[Zone.LIBRARY].add(c1)
        p1.zones[Zone.LIBRARY].add(c2)
        # Script: put both into graveyard (yes for both)
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(True)  # put Card2 in GY
            p1._script.append(True)  # put Card1 in GY
        duo.on_resolve(game)
        gy = list(p1.zones[Zone.GRAVEYARD].get_all())
        assert len(gy) >= 1  # At least one card surveiled to graveyard

    def test_surveil_can_keep_on_top(self) -> None:
        game = create_game()
        p1 = game.players[0]
        duo = LightshellDuo(owner=p1, controller=p1)
        duo.controller = p1
        c1 = CardImpl(name="Card1", owner=p1)
        c2 = CardImpl(name="Card2", owner=p1)
        p1.zones[Zone.LIBRARY].add(c1)
        p1.zones[Zone.LIBRARY].add(c2)
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(False)  # keep on top
            p1._script.append(False)  # keep on top
        duo.on_resolve(game)
        lib = list(p1.zones[Zone.LIBRARY].get_all())
        assert len(lib) == 2  # Both stayed
