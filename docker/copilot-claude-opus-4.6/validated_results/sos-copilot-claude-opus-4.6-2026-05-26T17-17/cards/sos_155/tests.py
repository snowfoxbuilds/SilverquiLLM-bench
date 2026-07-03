"""Tests for SOS 155 — Noxious Newt.

Creature — Salamander, 1/2 for {1}{G}.
Deathtouch.
{T}: Add {G}.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_155.card_impl import NoxiousNewt
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state


class TestNoxiousNewtProperties:
    """Static card data should match the SOS 155 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(NoxiousNewt(owner=None), Creature)

    def test_name(self) -> None:
        assert NoxiousNewt(owner=None).name == "Noxious Newt"

    def test_mana_cost(self) -> None:
        assert NoxiousNewt(owner=None).mana_cost == ManaCost.parse("{1}{G}")

    def test_power_toughness(self) -> None:
        card = NoxiousNewt(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 2

    def test_has_deathtouch(self) -> None:
        assert Keyword.DEATHTOUCH in NoxiousNewt(owner=None).keywords


class TestNoxiousNewtManaAbility:
    """{T}: Add {G} — a mana ability that taps to produce green mana."""

    def test_tap_produces_green_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        newt = NoxiousNewt(owner=p1, controller=p1)
        newt.is_tapped = False
        game.get_battlefield(p1).add(newt)

        newt.activate_mana_ability(game)
        # Should produce one green mana
        assert p1.mana_pool.get(ManaType.GREEN, 0) >= 1

    def test_tap_ability_taps_the_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        newt = NoxiousNewt(owner=p1, controller=p1)
        newt.is_tapped = False
        game.get_battlefield(p1).add(newt)

        newt.activate_mana_ability(game)
        assert newt.is_tapped is True

    def test_cannot_activate_when_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        newt = NoxiousNewt(owner=p1, controller=p1)
        newt.is_tapped = True
        game.get_battlefield(p1).add(newt)

        assert newt.can_activate_mana_ability(game) is False

    def test_cannot_activate_with_summoning_sickness(self) -> None:
        """Creatures with tap abilities can't use them the turn they enter
        unless they have haste."""
        game = create_game()
        p1 = game.players[0]
        newt = NoxiousNewt(owner=p1, controller=p1)
        newt.is_tapped = False
        newt.has_summoning_sickness = True
        game.get_battlefield(p1).add(newt)

        assert newt.can_activate_mana_ability(game) is False
