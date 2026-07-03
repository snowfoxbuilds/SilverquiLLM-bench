"""Tests for SOS 158 — Planar Engineering."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_158.card_impl import PlanarEngineering
from benchmarks.sos.workspace.engine.basic_lands import Forest, Island, Plains, Swamp
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Land, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestPlanarEngineeringProperties:
    """Static card data should match the SOS 158 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(PlanarEngineering(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = PlanarEngineering(owner=None)

        assert card.name == "Planar Engineering"
        assert card.mana_cost == ManaCost.parse("{3}{G}")


class TestPlanarEngineeringCasting:
    """Planar Engineering should sacrifice lands and find four tapped basics."""

    def test_casting_it_sacrifices_two_lands_as_an_additional_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        land_a = Land(name="Campus A", owner=p1, controller=p1)
        land_b = Land(name="Campus B", owner=p1, controller=p1)
        spell = PlanarEngineering(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[land_a, land_b],
            hand=[spell],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 3},
        )
        p1._script.extend([land_a, land_b])

        cast_spell_paid(game, p1, spell)

        assert game.get_graveyard(p1).contains(land_a)
        assert game.get_graveyard(p1).contains(land_b)
        assert not game.get_battlefield(p1).contains(land_a)
        assert not game.get_battlefield(p1).contains(land_b)
        assert game.stack.peek().source is spell

    def test_resolving_it_puts_four_basic_lands_onto_the_battlefield_tapped_and_shuffles_the_rest(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        land_a = Land(name="Campus A", owner=p1, controller=p1)
        land_b = Land(name="Campus B", owner=p1, controller=p1)
        spell = PlanarEngineering(owner=p1, controller=p1)
        forest = Forest(owner=p1, controller=p1)
        island = Island(owner=p1, controller=p1)
        swamp = Swamp(owner=p1, controller=p1)
        plains = Plains(owner=p1, controller=p1)
        campus = Land(name="Crystal Campus", owner=p1, controller=p1)
        grotto = Land(name="Study Grotto", owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[land_a, land_b],
            hand=[spell],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 3},
        )
        for card in [campus, forest, island, swamp, plains, grotto]:
            game.get_library(p1).add(card)
        game.shuffle_history.clear()
        game.queue_shuffle_order(grotto, campus)
        p1._script.extend([land_a, land_b, forest, island, swamp, plains])

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        battlefield = game.get_battlefield(p1).get_all()
        for basic in [forest, island, swamp, plains]:
            assert basic in battlefield
            assert basic.is_tapped is True
            assert not game.get_library(p1).contains(basic)
        assert game.get_library(p1).get_all() == [grotto, campus]
        assert len(game.shuffle_history) == 1
        assert game.shuffle_history[-1].zone is Zone.LIBRARY

    def test_casting_without_two_lands_to_sacrifice_is_illegal(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        only_land = Land(name="Only Campus", owner=p1, controller=p1)
        spell = PlanarEngineering(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[only_land],
            hand=[spell],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 3},
        )

        with pytest.raises(CastingError):
            cast_spell_paid(game, p1, spell)

        assert game.get_battlefield(p1).contains(only_land)
        assert game.get_hand(p1).contains(spell)
        assert game.stack.is_empty()
