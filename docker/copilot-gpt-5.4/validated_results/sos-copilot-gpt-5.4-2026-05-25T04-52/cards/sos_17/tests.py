"""Tests for SOS 17 — Group Project."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_17.card_impl import GroupProject
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, ManaCost, Phase, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestGroupProjectProperties:
    """Static card data should match the SOS 17 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(GroupProject(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = GroupProject(owner=None)
        assert card.name == "Group Project"
        assert card.mana_cost == ManaCost.parse("{1}{W}")


class TestGroupProjectResolution:
    """Group Project should make a Spirit token and support flashback."""

    def test_on_resolve_creates_a_red_and_white_2_2_spirit_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GroupProject(owner=p1, controller=p1)

        card.on_resolve(game)

        permanents = game.get_battlefield(p1).get_all()
        assert len(permanents) == 1

        token = permanents[0]
        assert isinstance(token, Creature)
        assert token.is_token is True
        assert token.power == 2
        assert token.toughness == 2
        assert "Spirit" in token.subtypes
        assert get_colors(token) == {Color.RED, Color.WHITE}

    def test_flashback_cast_from_graveyard_taps_three_untapped_creatures_you_control_and_exiles_on_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        creature_a = Creature(name="Student A", owner=p1, controller=p1, base_power=2, base_toughness=2)
        creature_b = Creature(name="Student B", owner=p1, controller=p1, base_power=2, base_toughness=2)
        creature_c = Creature(name="Student C", owner=p1, controller=p1, base_power=2, base_toughness=2)
        spell = GroupProject(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[creature_a, creature_b, creature_c],
            graveyard=[spell],
        )

        cast_spell_paid(game, p1, spell, from_zone=Zone.GRAVEYARD)

        assert creature_a.is_tapped is True
        assert creature_b.is_tapped is True
        assert creature_c.is_tapped is True
        assert game.stack.peek().source is spell
        assert not game.get_graveyard(p1).contains(spell)

        resolve_top(game)

        spirits = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if "Spirit" in getattr(permanent, "subtypes", set())
        ]
        assert len(spirits) == 1
        assert game.get_exile(p1).contains(spell)

    def test_flashback_cast_requires_three_untapped_creatures_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.phase = Phase.PRECOMBAT_MAIN
        creature_a = Creature(name="Student A", owner=p1, controller=p1, base_power=2, base_toughness=2)
        creature_b = Creature(name="Student B", owner=p1, controller=p1, base_power=2, base_toughness=2)
        tapped_creature = Creature(
            name="Already Busy",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        tapped_creature.is_tapped = True
        opponents_creature = Creature(
            name="Opponent's Student",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        spell = GroupProject(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[creature_a, creature_b, tapped_creature],
            graveyard=[spell],
        )
        game.get_battlefield(p2).add(opponents_creature)

        with pytest.raises(CastingError):
            cast_spell_paid(game, p1, spell, from_zone=Zone.GRAVEYARD)

        assert creature_a.is_tapped is False
        assert creature_b.is_tapped is False
        assert tapped_creature.is_tapped is True
        assert opponents_creature.is_tapped is False
        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(spell)

