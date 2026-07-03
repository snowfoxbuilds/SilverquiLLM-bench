"""Tests for SOS 7 — Antiquities on the Loose."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_7.card_impl import AntiquitiesOnTheLoose
from benchmarks.sos.workspace.engine.casting import (
    CastingError,
    cast_spell as cast_spell_paid,
    cast_spell_free,
    resolve_top,
)
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, ManaCost, ManaType, Phase, Zone
from benchmarks.sos.workspace.tests.test_utils import cast_spell, create_game, set_board_state


class TestAntiquitiesOnTheLooseProperties:
    """Static card data should match the SOS 7 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(AntiquitiesOnTheLoose(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = AntiquitiesOnTheLoose(owner=None)
        assert card.name == "Antiquities on the Loose"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")


class TestAntiquitiesOnTheLooseResolution:
    """The spell should create Spirit tokens and reward non-hand casting."""

    def test_on_resolve_creates_two_red_and_white_2_2_spirit_tokens(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AntiquitiesOnTheLoose(owner=p1, controller=p1)

        card.on_resolve(game)

        tokens = game.get_battlefield(p1).get_all()
        assert len(tokens) == 2
        for token in tokens:
            assert isinstance(token, Creature)
            assert token.is_token is True
            assert token.power == 2
            assert token.toughness == 2
            assert "Spirit" in token.subtypes
            assert get_colors(token) == {Color.RED, Color.WHITE}

    def test_cast_from_hand_does_not_add_counters_to_spirits(self) -> None:
        game = create_game()
        p1 = game.players[0]
        existing_spirit = Creature(
            name="Friendly Spirit",
            base_power=2,
            base_toughness=2,
            subtypes={"Spirit"},
        )
        existing_spirit.colors = {Color.RED, Color.WHITE}
        spell = AntiquitiesOnTheLoose(owner=p1, controller=p1)

        create_token(game, p1, existing_spirit)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.WHITE: 3},
        )

        cast_spell(game, 0, "Antiquities on the Loose")

        spirits = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if "Spirit" in getattr(permanent, "subtypes", set())
        ]
        assert len(spirits) == 3
        assert all(spirit.plus_one_counters == 0 for spirit in spirits)

    def test_graveyard_cast_puts_a_counter_on_each_spirit_you_control(self) -> None:
        game = create_game()
        p1 = game.players[0]
        existing_spirit = Creature(
            name="Old Spirit",
            base_power=2,
            base_toughness=2,
            subtypes={"Spirit"},
        )
        existing_spirit.colors = {Color.RED, Color.WHITE}
        non_spirit = Creature(name="Bear", base_power=2, base_toughness=2)
        spell = AntiquitiesOnTheLoose(owner=p1, controller=p1)

        create_token(game, p1, existing_spirit)
        set_board_state(game, 0, battlefield=[existing_spirit, non_spirit], graveyard=[spell])

        cast_spell_free(game, p1, spell, Zone.GRAVEYARD, exile_on_resolve=True)
        resolve_top(game)

        permanents = game.get_battlefield(p1).get_all()
        spirits = [
            permanent
            for permanent in permanents
            if "Spirit" in getattr(permanent, "subtypes", set())
        ]
        assert len(spirits) == 3
        assert all(spirit.plus_one_counters == 1 for spirit in spirits)
        assert non_spirit.plus_one_counters == 0
        assert game.get_exile(p1).contains(spell)

    def test_paid_flashback_cast_from_graveyard_uses_printed_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = AntiquitiesOnTheLoose(owner=p1, controller=p1)
        game.phase = Phase.PRECOMBAT_MAIN

        set_board_state(
            game,
            0,
            graveyard=[spell],
            mana={ManaType.WHITE: 3},
        )

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell_paid(game, p1, spell, from_zone=Zone.GRAVEYARD)

        assert game.get_graveyard(p1).contains(spell)
        assert p1.mana_pool.get(ManaType.WHITE) == 3

    def test_paid_flashback_cast_from_graveyard_exiles_on_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = AntiquitiesOnTheLoose(owner=p1, controller=p1)
        game.phase = Phase.PRECOMBAT_MAIN

        set_board_state(
            game,
            0,
            graveyard=[spell],
            mana={ManaType.WHITE: 6},
        )

        cast_spell_paid(game, p1, spell, from_zone=Zone.GRAVEYARD)

        assert game.stack.peek().source is spell
        assert not game.get_graveyard(p1).contains(spell)
        assert p1.mana_pool.get(ManaType.WHITE) == 0

        resolve_top(game)

        spirits = game.get_battlefield(p1).get_all()
        assert len(spirits) == 2
        assert all(spirit.plus_one_counters == 1 for spirit in spirits)
        assert game.get_exile(p1).contains(spell)
