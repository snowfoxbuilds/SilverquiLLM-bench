"""Tests for SOS 199 — Lluwen, Exchange Student // Pest Friend."""

from __future__ import annotations

import pytest

from cards.sos.sos_199.card_impl import LluwenExchangeStudentPestFriend
from engine.card import Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestLluwenProperties:
    """Static card data should match the SOS 199 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(LluwenExchangeStudentPestFriend(owner=None), Creature)

    def test_name(self) -> None:
        card = LluwenExchangeStudentPestFriend(owner=None)
        assert card.name == "Lluwen, Exchange Student"

    def test_mana_cost(self) -> None:
        card = LluwenExchangeStudentPestFriend(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{B}{G}")

    def test_power_toughness(self) -> None:
        card = LluwenExchangeStudentPestFriend(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_is_legendary(self) -> None:
        card = LluwenExchangeStudentPestFriend(owner=None)
        assert card.is_legendary is True


class TestLluwenEntersPrepared:
    """Lluwen enters the battlefield prepared."""

    def test_enters_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]

        lluwen = LluwenExchangeStudentPestFriend(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lluwen)
        lluwen.on_enter_battlefield(game)

        assert lluwen.is_prepared is True


class TestLluwenActivatedAbility:
    """Exile a creature card from graveyard to become prepared again."""

    def test_exile_creature_to_become_prepared(self) -> None:
        """Exiling a creature card from graveyard makes Lluwen prepared."""
        game = create_game()
        p1 = game.players[0]

        lluwen = LluwenExchangeStudentPestFriend(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lluwen)
        lluwen.is_prepared = False

        # Put a creature in graveyard
        dead_bear = Creature(name="Dead Bear", owner=p1, base_power=2, base_toughness=2)
        dead_bear.card_types = {CardType.CREATURE}
        game.get_graveyard(p1).add(dead_bear)

        lluwen.activate_ability(game, target=dead_bear)

        assert lluwen.is_prepared is True
        assert dead_bear not in game.get_graveyard(p1)
        assert dead_bear in game.get_exile(p1)

    def test_cannot_activate_without_creature_in_graveyard(self) -> None:
        """Cannot activate if no creature card in graveyard."""
        game = create_game()
        p1 = game.players[0]

        lluwen = LluwenExchangeStudentPestFriend(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lluwen)
        lluwen.is_prepared = False

        # No creatures in graveyard
        assert lluwen.can_activate_ability(game) is False

    def test_sorcery_speed_only(self) -> None:
        """Activation is sorcery speed only."""
        game = create_game()
        p1 = game.players[0]

        lluwen = LluwenExchangeStudentPestFriend(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lluwen)

        assert lluwen.activation_timing == "sorcery"

    def test_cast_prepared_spell_unprepares(self) -> None:
        """Casting the Pest Friend copy unprepares Lluwen."""
        game = create_game()
        p1 = game.players[0]

        lluwen = LluwenExchangeStudentPestFriend(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lluwen)
        lluwen.on_enter_battlefield(game)
        assert lluwen.is_prepared is True

        set_board_state(game, 0, mana={ManaType.BLACK: 1, ManaType.GREEN: 1})
        lluwen.cast_prepared_spell(game)

        assert lluwen.is_prepared is False
