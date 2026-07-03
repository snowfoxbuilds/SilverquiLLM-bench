"""Tests for SOS 129 — Seize the Spoils."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_129.card_impl import SeizeTheSpoils
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestSeizeTheSpoilsProperties:
    """Static card data should match the SOS 129 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(SeizeTheSpoils(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = SeizeTheSpoils(owner=None)

        assert card.name == "Seize the Spoils"
        assert card.mana_cost == ManaCost.parse("{2}{R}")


class TestSeizeTheSpoilsCasting:
    """Seize the Spoils should require a discard when cast."""

    def test_casting_discards_a_card_before_the_spell_resolves(self) -> None:
        game = create_game()
        p1 = game.players[0]
        discard_card = CardImpl(name="Spare Notes", owner=p1, controller=p1)
        spell = SeizeTheSpoils(owner=p1, controller=p1)
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[spell, discard_card],
            mana={ManaType.COLORLESS: 2, ManaType.RED: 1},
        )
        p1._script.append(discard_card)

        cast_spell_paid(game, p1, spell)

        assert game.stack.peek().source is spell
        assert not game.get_hand(p1).contains(discard_card)
        assert game.get_graveyard(p1).contains(discard_card)

    def test_cannot_be_cast_without_another_card_to_discard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = SeizeTheSpoils(owner=p1, controller=p1)
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.COLORLESS: 2, ManaType.RED: 1},
        )

        with pytest.raises(CastingError):
            cast_spell_paid(game, p1, spell)

        assert game.get_hand(p1).contains(spell)


class TestSeizeTheSpoilsResolution:
    """Seize the Spoils should draw two cards and create a Treasure token."""

    def test_on_resolve_draws_two_cards_and_creates_a_treasure_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        draw_one = CardImpl(name="First Draft", owner=p1, controller=p1)
        draw_two = CardImpl(name="Second Draft", owner=p1, controller=p1)
        game.get_library(p1).add(draw_one)
        game.get_library(p1).add(draw_two)

        spell = SeizeTheSpoils(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert game.get_hand(p1).contains(draw_one)
        assert game.get_hand(p1).contains(draw_two)

        battlefield = game.get_battlefield(p1).get_all()
        assert len(battlefield) == 1
        token = battlefield[0]
        assert token.name == "Treasure"
        assert token.is_token is True
        assert CardType.ARTIFACT in token.card_types

    def test_paid_cast_still_draws_two_cards_and_leaves_the_spell_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        discard_card = CardImpl(name="Spare Notes", owner=p1, controller=p1)
        draw_one = CardImpl(name="First Draft", owner=p1, controller=p1)
        draw_two = CardImpl(name="Second Draft", owner=p1, controller=p1)
        spell = SeizeTheSpoils(owner=p1, controller=p1)
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[spell, discard_card],
            mana={ManaType.COLORLESS: 2, ManaType.RED: 1},
        )
        game.get_library(p1).add(draw_one)
        game.get_library(p1).add(draw_two)
        p1._script.append(discard_card)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert game.get_hand(p1).contains(draw_one)
        assert game.get_hand(p1).contains(draw_two)
        assert game.get_graveyard(p1).contains(discard_card)
        assert game.get_graveyard(p1).contains(spell)
