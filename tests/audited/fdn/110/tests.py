"""Audited tests for Quakestrider Ceratops (FDN collector number 110) — vanilla creature."""

from __future__ import annotations

import pytest

from card_impl import QuakestriderCeratops

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestQuakestriderCeratopsProperties:
    def test_is_creature(self) -> None:
        card = QuakestriderCeratops(name="Quakestrider Ceratops", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = QuakestriderCeratops(name="Quakestrider Ceratops", owner=None)
        assert card.name == "Quakestrider Ceratops"

    def test_power(self) -> None:
        card = QuakestriderCeratops(name="Quakestrider Ceratops", owner=None)
        assert card.power == 12

    def test_toughness(self) -> None:
        card = QuakestriderCeratops(name="Quakestrider Ceratops", owner=None)
        assert card.toughness == 8

    def test_has_dinosaur_subtype(self) -> None:
        card = QuakestriderCeratops(name="Quakestrider Ceratops", owner=None)
        assert "Dinosaur" in card.subtypes

    def test_no_keywords(self) -> None:
        card = QuakestriderCeratops(name="Quakestrider Ceratops", owner=None)
        assert card.keywords == Keyword(0)

    def test_mana_cost_cmc(self) -> None:
        """Quakestrider Ceratops costs {3}{G}{G}{G} — converted mana cost 6."""
        card = QuakestriderCeratops(name="Quakestrider Ceratops", owner=None)
        assert card.mana_cost.cmc == 6


@pytest.mark.behavior
class TestQuakestriderCeratopsBehavior:
    """Casting and combat behavior tests for Quakestrider Ceratops."""

    def test_can_be_cast_from_hand(self) -> None:
        """Quakestrider Ceratops can be cast from hand with sufficient mana."""
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType

        game = create_game()
        card = QuakestriderCeratops(name="Quakestrider Ceratops", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.GREEN: 6})
        cast_spell(game, 0, "Quakestrider Ceratops")
        bf = game.get_battlefield(game.players[0])
        assert card in bf.get_all()

    def test_has_summoning_sickness_when_cast(self) -> None:
        """A freshly cast creature has summoning sickness."""
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType

        game = create_game()
        card = QuakestriderCeratops(name="Quakestrider Ceratops", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.GREEN: 6})
        cast_spell(game, 0, "Quakestrider Ceratops")
        assert card.summoning_sick

    def test_deals_combat_damage_equal_to_power(self) -> None:
        """Quakestrider Ceratops deals 12 damage when attacking unblocked."""
        from tests.test_utils import create_game, set_board_state, declare_attackers
        from engine.combat import combat_damage_step

        game = create_game()
        card = QuakestriderCeratops(name="Quakestrider Ceratops", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        declare_attackers(game, ["Quakestrider Ceratops"])
        combat_damage_step(game)
        assert game.players[1].life == 20 - 12
