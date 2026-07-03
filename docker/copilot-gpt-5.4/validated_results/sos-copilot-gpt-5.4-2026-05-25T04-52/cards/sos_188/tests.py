"""Tests for SOS 188 — Fix What's Broken."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_188.card_impl import FixWhatsBroken
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Artifact, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestFixWhatsBrokenProperties:
    """Static card data should match the SOS 188 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(FixWhatsBroken(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = FixWhatsBroken(owner=None)

        assert card.name == "Fix What's Broken"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")


class TestFixWhatsBrokenCasting:
    """Fix What's Broken should charge life as an additional casting cost."""

    def test_casting_pays_x_life_before_the_spell_resolves(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = FixWhatsBroken(owner=p1, controller=p1)
        spell.x_value = 2  # type: ignore[attr-defined]
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[spell],
            life=10,
            mana={
                ManaType.COLORLESS: 2,
                ManaType.WHITE: 1,
                ManaType.BLACK: 1,
            },
        )

        cast_spell_paid(game, p1, spell)

        assert p1.life == 8
        assert game.stack.peek().source is spell

    def test_cannot_be_cast_if_you_cannot_pay_the_chosen_x_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = FixWhatsBroken(owner=p1, controller=p1)
        spell.x_value = 3  # type: ignore[attr-defined]
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[spell],
            life=2,
            mana={
                ManaType.COLORLESS: 2,
                ManaType.WHITE: 1,
                ManaType.BLACK: 1,
            },
        )

        with pytest.raises(CastingError):
            cast_spell_paid(game, p1, spell)

        assert p1.life == 2
        assert game.get_hand(p1).contains(spell)


class TestFixWhatsBrokenResolution:
    """Fix What's Broken should reanimate artifact and creature cards with mana value X."""

    def test_on_resolve_returns_each_artifact_and_creature_card_with_mana_value_x(self) -> None:
        game = create_game()
        p1 = game.players[0]
        returned_artifact = Artifact(
            name="Recovered Engine",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}"),
        )
        returned_creature = Creature(
            name="Recovered Apprentice",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{W}"),
            base_power=2,
            base_toughness=2,
        )
        cheap_artifact = Artifact(
            name="Too Cheap",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}"),
        )
        expensive_creature = Creature(
            name="Too Expensive",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{3}"),
            base_power=3,
            base_toughness=3,
        )
        nonmatching_spell = Sorcery(
            name="Still a Spell",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{B}"),
        )
        set_board_state(
            game,
            0,
            graveyard=[
                returned_artifact,
                returned_creature,
                cheap_artifact,
                expensive_creature,
                nonmatching_spell,
            ],
        )
        spell = FixWhatsBroken(owner=p1, controller=p1)
        spell.x_value = 2  # type: ignore[attr-defined]

        spell.on_resolve(game)

        assert game.get_battlefield(p1).contains(returned_artifact)
        assert game.get_battlefield(p1).contains(returned_creature)
        assert not game.get_graveyard(p1).contains(returned_artifact)
        assert not game.get_graveyard(p1).contains(returned_creature)
        assert game.get_graveyard(p1).contains(cheap_artifact)
        assert game.get_graveyard(p1).contains(expensive_creature)
        assert game.get_graveyard(p1).contains(nonmatching_spell)
